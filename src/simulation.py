import logging
import numpy as np
import netsquid as ns

from utils import record_results, switch_parameters, get_fidelities
from qpu_node import QPUNode
from fso_switch import FSOSwitch
from protocols import EntanglementRetryProto
from netsquid.protocols import Signals
from netsquid.nodes.network import Network
from netsquid.components import ClassicalChannel
from netsquid.nodes.connections import DirectConnection
from netsquid.components.models.delaymodels import FibreDelayModel


def setup_network(
    model_parameters,
    loss_prob,
    routing,
    qpu_dephase=0,
):
    network = Network("switch_test_network")
    # Testing detector induced losses
    det_eff = 1 - loss_prob

    # Determine herald ports depending on switch configuration
    long_paths = routing == {"qin0": "qout2", "qin1": "qout1", "qin2": "qout0"}
    if long_paths:
        herald_ports = ["qout0", "qout2"]
    else:
        herald_ports = [routing["qin0"], routing["qin1"]]

    # Create nodes
    alice_node = QPUNode("AliceNode", depolar_rate=qpu_dephase)
    bob_node = QPUNode("BobNode", depolar_rate=qpu_dephase)
    fsoswitch_node = FSOSwitch("bsm_fsoswitch", model_parameters, det_eff, herald_ports)

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
    # TODO add DataCollector object

    return alice_node, bob_node, fsoswitch_node


def single_run(
    model_parameters, qpu_depolar_rate, switch_routing, loss_prob, max_attempts
):
    # Initialize simulation
    ns.sim_reset()

    # Setup network connections
    alice_node, bob_node, fsoswitch_node = setup_network(
        model_parameters,
        loss_prob,
        routing=switch_routing,
    )

    # Create and start the simulation protocol
    retry_proto = EntanglementRetryProto(
        alice_node,
        bob_node,
        fsoswitch_node,
        switch_routing,
        max_attempts=max_attempts,
    )

    # TODO setup entanglement distillation protocol

    # Test
    retry_proto.reset()
    retry_proto.start()

    # Run the simulation
    stats = ns.sim_run()
    quantum_ops = stats.data["quantum_ops_total"]
    # print(f"SIMULATION STATISTICS: {stats}")
    simtime = ns.sim_time()

    # Get the protocol status
    protocol_status = retry_proto.get_signal_result(Signals.FINISHED)
    logging.info(f"[Simulation] Retry protocol returned: {protocol_status}")

    # Calculate ebit fidelity or set to 0.5 if attempt failed
    fidelity = (
        get_fidelities(alice_node, bob_node, qid_1=1, qid_2=1)
        if protocol_status
        else 0.5
    )
    logging.debug(f"FIDELITY: {fidelity}")

    # Return results
    return {
        "status": protocol_status,
        "attempts": retry_proto.attempts,
        "fidelity": fidelity,
        "simtime": simtime,
        "quantum_ops": quantum_ops,
    }


# Runs the simulation several times, determined by the batch size.
def batch_run(
    model_parameters,
    qpu_depolar_rate,
    switch_routing,
    batch_size,
    loss_prob,
    max_attempts,
):
    ret_results = {
        "status": 0,
        "attempts": 0,
        "fidelity": 0,
        "simtime": 0,
        "quantum_ops": 0,
        "entanglement_rate": 0,
    }
    full_results = {
        "status": np.zeros(batch_size, dtype="bool"),
        "attempts": np.zeros(batch_size, dtype="uint"),
        "fidelity": np.zeros(batch_size, dtype="float"),
        "simtime": np.zeros(batch_size, dtype="float"),
        "quantum_ops": np.zeros(batch_size, dtype="uint"),
        "entanglement_rate": np.zeros(batch_size, dtype="float"),
    }
    for i in range(batch_size):
        # Perform single run of the simulation and record the results into the dict
        run_results = single_run(
            model_parameters, qpu_depolar_rate, switch_routing, loss_prob, max_attempts
        )
        record_results(full_results, run_results, i, max_attempts)

    # Average calculations and return
    ret_results["status"] = np.average(full_results["status"])
    ret_results["attempts"] = np.average(full_results["attempts"])
    ret_results["fidelity"] = np.average(full_results["fidelity"])
    ret_results["simtime"] = np.average(full_results["simtime"])
    ret_results["quantum_ops"] = np.average(full_results["quantum_ops"])
    ret_results["entanglement_rate"] = np.average(full_results["entanglement_rate"])
    return ret_results
