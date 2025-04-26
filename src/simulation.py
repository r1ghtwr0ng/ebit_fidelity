import logging
import pandas as pd
import netsquid as ns

from multiprocessing import Pool

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
    detector_efficiency,
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
        "bsm_fsoswitch", detector_efficiency, dampening_parameter, ideal, herald_ports
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
    detector_efficiency,
    run,
):
    # Initialize simulatio
    ns.sim_reset()

    # Setup network connections
    alice_node, bob_node, fsoswitch_node = setup_network(
        routing=switch_routing,
        dampening_parameter=dampening_parameter,
        detector_efficiency=detector_efficiency,
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
    logging.info(f"[Simulation] Retry protocol returned: {protocol_status}")

    # Make sure to reset the protocol
    distill_proto.reset()

    # Construct simulation statistics metadata dataframe
    run_id = f"{run}_{dampening_parameter}_{detector_efficiency}"
    run_metadata = {
        "run": run,
        "detector_efficiency": detector_efficiency,
        "dampening_parameter": dampening_parameter,
        "run_id": run_id,
        "ideal": ideal,
        "status": protocol_status,
        "simtime": simtime,
        "quantum_ops": quantum_ops,
    }
    run_metadata_df = pd.DataFrame([run_metadata])

    # Fill in the run information for the full dataframe
    full_events_dataframe["run"] = run
    full_events_dataframe["detector_efficiency"] = detector_efficiency
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
    detector_efficiencies,
    max_attempts,
    max_distillations,
    workers,
):
    total_params = len(dampening_parameters) * len(detector_efficiencies)
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
            detector_eff,
            i * len(detector_efficiencies) + j,
        )
        for i, dampening_parameter in enumerate(dampening_parameters)
        for j, detector_eff in enumerate(detector_efficiencies)
    ]

    # Use multiprocessing to execute all parameter combinations
    with Pool(workers) as pool:
        results = pool.starmap(batch_proc, param_combinations)

        # Print progress update after completion
        print(
            f"[i] Processing complete: {total_params}/{total_params} parameter combinations"
        )

    # Unpack results
    all_event_dfs = []
    all_metadata_dfs = []

    for batch_event_dfs, batch_metadata_dfs in results:
        all_event_dfs.extend(batch_event_dfs)
        all_metadata_dfs.extend(batch_metadata_dfs)

    # Concatenate all dataframes into a single entity
    df_all_events = pd.concat(all_event_dfs, ignore_index=True)
    df_all_metadata = pd.concat(all_metadata_dfs, ignore_index=True)

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
    detector_eff,
    run_id,
):
    logging.info(
        f"[i] Processing combination {run_id}: dampening={dampening_parameter}, detector_eff={detector_eff}"
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
            detector_eff,
            batch_run_id,
        )
        batch_event_dfs.append(full_events_df)
        batch_metadata_dfs.append(run_metadata_df)

    return batch_event_dfs, batch_metadata_dfs
