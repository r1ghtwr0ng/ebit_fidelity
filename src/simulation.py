import logging
import pandas as pd
import netsquid as ns

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
    ideal,
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
    alice_node = QPUNode("AliceNode")
    bob_node = QPUNode("BobNode")
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
    ideal,
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
        ideal=ideal,
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


# TODO multiprocess this so kernel cleans up memory leaks
def batch_run(
    switch_routing,
    batch_size,
    ideal_switch,
    dampening_parameters,
    detector_efficiencies,
    max_attempts,
    max_distillations,
):
    all_event_dfs = []
    all_metadata_dfs = []
    for i, dampening_parameter in enumerate(dampening_parameters):
        print(f"[i] Progress: {i}/{len(dampening_parameters)}", end="\r")
        for j, detector_eff in enumerate(detector_efficiencies):
            for run_id in range(batch_size):
                run_metadata_df, full_events_df = single_run(
                    switch_routing,
                    dampening_parameter,
                    max_attempts,
                    max_distillations,
                    ideal_switch,
                    detector_eff,
                    run_id,
                )
                all_event_dfs.append(full_events_df)
                all_metadata_dfs.append(run_metadata_df)

    # Concatenate all dataframes into a single entity
    df_all_events = pd.concat(all_event_dfs, ignore_index=True)
    df_all_metadata = pd.concat(all_metadata_dfs, ignore_index=True)
    return df_all_metadata, df_all_events
