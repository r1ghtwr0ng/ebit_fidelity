import gc
import logging
import pandas as pd
import netsquid as ns

from multiprocessing import Pool, Manager

from qpu_node import QPUNode
from fso_switch import FSOSwitch
from protocols import ContinuousDistillationProtocol
from netsquid.protocols import Signals
from netsquid.nodes.network import Network
from netsquid.components import ClassicalChannel
from netsquid.nodes.connections import DirectConnection
from netsquid.components.models.delaymodels import FibreDelayModel


def setup_network(
    dampening_parameter,
    routing,
    ideal_switch,
    ideal_qpu,
    visibility,
):
    network = Network("switch_test_network")
    # Testing detector induced losses

    # Determine herald ports depending on switch configuration
    long_paths = routing == {"qin0": "qout2", "qin1": "qout1", "qin2": "qout0"}
    if long_paths:
        herald_ports = ["qout0", "qout2"]
    else:
        herald_ports = [routing["qin0"], routing["qin1"]]

    # Create nodes
    alice_node = QPUNode("AliceNode", ideal_qpu)
    bob_node = QPUNode("BobNode", ideal_qpu)
    fsoswitch_node = FSOSwitch(
        "bsm_fsoswitch",
        dampening_parameter,
        ideal_switch,
        herald_ports,
        visibility,
    )

    # Connect node-level ports
    alice_node.processor.ports["qout_hdr"].connect(fsoswitch_node.ports["qin0"])
    if long_paths:
        bob_node.processor.ports["qout_hdr"].connect(fsoswitch_node.ports["qin2"])
    else:
        bob_node.processor.ports["qout_hdr"].connect(fsoswitch_node.ports["qin1"])
    fsoswitch_node.ports["cout0"].connect(alice_node.ports["corrections"])
    fsoswitch_node.ports["cout1"].connect(bob_node.ports["corrections"])

    # Add nodes to network
    network.add_nodes(nodes=[alice_node, bob_node, fsoswitch_node])

    # Setup classical communication channel between nodes for entanglement distillation
    conn_cchannel = DirectConnection(
        "CChannelConn_AB",
        ClassicalChannel(
            "CChannel_A->B",
            length=0,
            models={"delay_model": FibreDelayModel(c=200e3)},
        ),
        ClassicalChannel(
            "CChannel_B->A",
            length=0,
            models={"delay_model": FibreDelayModel(c=200e3)},
        ),
    )

    # Add connection to network
    network.add_connection(alice_node, bob_node, connection=conn_cchannel)
    # TODO add quantum channel connections instead of direct port forwards

    return alice_node, bob_node, fsoswitch_node


def single_run(
    switch_routing,
    dampening_parameter,
    max_attempts,
    max_distillations,
    ideal_switch,
    ideal_qpu,
    depolar_rate,
    run,
):
    # Initialize simulatio
    ns.sim_reset()

    # Setup network connections
    alice_node, bob_node, fsoswitch_node = setup_network(
        routing=switch_routing,
        dampening_parameter=dampening_parameter,
        visibility=depolar_rate,
        ideal_switch=ideal_switch,
        ideal_qpu=ideal_qpu,
    )

    # Create and start the simulation protocol
    distill_proto = ContinuousDistillationProtocol(
        alice_node,
        bob_node,
        fsoswitch_node,
        switch_routing,
        max_attempts=max_attempts,
        max_distillations=max_distillations,
    )

    # Test
    distill_proto.start()

    # Run the simulation
    stats = ns.sim_run()
    quantum_ops = stats.data["quantum_ops_total"]
    simtime = ns.sim_time()

    # Get the protocol status
    protocol_status, full_events_dataframe = distill_proto.get_signal_result(
        Signals.FINISHED
    )
    logging.info(
        f"[Simulation] Continuous distill protocol returned: {protocol_status}"
    )

    # Make sure to reset the protocol
    distill_proto.reset()

    # Construct simulation statistics metadata dataframe
    run_id = f"{run}_{dampening_parameter}_{depolar_rate}"
    run_metadata = {
        "run": run,
        "depolar_rate": depolar_rate,
        "dampening_parameter": dampening_parameter,
        "run_id": run_id,
        "ideal_switch": ideal_switch,
        "ideal_qpu": ideal_qpu,
        "status": protocol_status,
        "simtime": simtime,
        "quantum_ops": quantum_ops,
    }
    run_metadata_df = pd.DataFrame([run_metadata])

    # Fill in the run information for the full dataframe
    full_events_dataframe["run"] = run
    full_events_dataframe["depolar_rate"] = depolar_rate
    full_events_dataframe["dampening_parameter"] = dampening_parameter
    full_events_dataframe["run_id"] = run_id

    # Return results
    return run_metadata_df, full_events_dataframe


def batch_run(
    switch_routing,
    batch_size,
    ideal_switch,
    ideal_qpu,
    dampening_parameters,
    depolar_rates,
    max_attempts,
    max_distillations,
    workers,
):
    total_params = len(dampening_parameters) * len(depolar_rates)
    print(
        f"[i] Starting processing of {total_params} parameter combinations with {workers} workers"
    )

    # Prepare all parameter combinations
    param_combinations = [
        (
            batch_size,
            switch_routing,
            dampening_parameter,
            max_attempts,
            max_distillations,
            ideal_switch,
            ideal_qpu,
            depolar_rate,
            i * len(depolar_rates) + j,
        )
        for i, dampening_parameter in enumerate(dampening_parameters)
        for j, depolar_rate in enumerate(depolar_rates)
    ]

    # Use a custom processing method to ensure better memory management
    all_event_dfs = []
    all_metadata_dfs = []

    # Split parameter combinations into chunks to control parallel processing
    def process_chunk(chunk):
        # Create a new pool for each chunk to ensure clean process lifecycle
        with Pool(workers) as pool:
            chunk_results = pool.starmap(batch_proc, chunk)
            pool.close()
            pool.terminate()
            pool.join()

        # Collect results from this chunk
        chunk_event_dfs = []
        chunk_metadata_dfs = []
        for batch_event_dfs, batch_metadata_dfs in chunk_results:
            chunk_event_dfs.extend(batch_event_dfs)
            chunk_metadata_dfs.extend(batch_metadata_dfs)

        # Trigger garbage collection
        gc.collect()

        return chunk_event_dfs, chunk_metadata_dfs

    # Process parameters in smaller chunks
    chunk_size = max(1, len(param_combinations) // (workers * 2))
    for i in range(0, len(param_combinations), chunk_size):
        chunk = param_combinations[i : i + chunk_size]
        chunk_event_dfs, chunk_metadata_dfs = process_chunk(chunk)

        all_event_dfs.extend(chunk_event_dfs)
        all_metadata_dfs.extend(chunk_metadata_dfs)

        # Additional garbage collection between chunks
        gc.collect()

    # Concatenate all dataframes into a single entity
    df_all_events = pd.concat(all_event_dfs, ignore_index=True)
    df_all_metadata = pd.concat(all_metadata_dfs, ignore_index=True)

    # Final garbage collection
    gc.collect()

    # Print completion message
    print(
        f"[i] Processing complete: {total_params}/{total_params} parameter combinations"
    )

    return df_all_metadata, df_all_events


# Single worker process instance
def batch_proc(
    batch_size,
    switch_routing,
    dampening_parameter,
    max_attempts,
    max_distillations,
    ideal_switch,
    ideal_qpu,
    depolar_rate,
    run_id,
):
    logging.info(
        f"[i] Processing combination {run_id}: dampening={dampening_parameter}, depolar_rate={depolar_rate}"
    )
    batch_event_dfs = []
    batch_metadata_dfs = []
    for batch_run_id in range(batch_size):
        run_metadata_df, full_events_df = single_run(
            switch_routing,
            dampening_parameter,
            max_attempts,
            max_distillations,
            ideal_switch,
            ideal_qpu,
            depolar_rate,
            batch_run_id,
        )
        batch_event_dfs.append(full_events_df)
        batch_metadata_dfs.append(run_metadata_df)

    # Explicitly delete large objects and trigger garbage collection
    del run_metadata_df
    del full_events_df
    gc.collect()

    return batch_event_dfs, batch_metadata_dfs
