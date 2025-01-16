import logging
import numpy as np
import netsquid as ns
import netsquid.qubits.ketstates as ks
import netsquid.qubits.qubitapi as qapi

from utils import configure_parameters, get_fidelities
from qpu_entity import QPUNode
from fso_switch import FSOSwitch
from protocols import EntanglementProtocol


def setup_network(model_parameters):
    # Create nodes
    alice_node = QPUNode("AliceNode", correction=True)
    bob_node = QPUNode("BobNode")
    fsoswitch_node = FSOSwitch("bsm_fsoswitch", model_parameters)

    # Connect node-level ports
    alice_node.processor.ports["qout_hdr"].connect(fsoswitch_node.ports["qin0"])
    bob_node.processor.ports["qout_hdr"].connect(fsoswitch_node.ports["qin1"])
    fsoswitch_node.ports["cout0"].connect(alice_node.processor.ports["correction"])
    fsoswitch_node.ports["cout1"].connect(bob_node.processor.ports["correction"])

    return alice_node, bob_node, fsoswitch_node


def single_sim(
    total_runs, switch_routing, fso_depolar_rates, qpu_depolar_rate, loss_probs
):
    results = []
    for fso_drate in fso_depolar_rates:
        for loss_prob in loss_probs:
            model_params = configure_parameters(fso_drate, loss_prob)
            result = batch_run(
                model_params, qpu_depolar_rate, switch_routing, total_runs
            )
            results.append(result)
    return results


def single_run(model_parameters, qpu_depolar_rate, switch_routing):
    """
    Run a single quantum simulation with specified configurations and collect results.

    Parameters
    ----------
    model_parameters : dict
        Configuration parameters for the FSO switch model.
    qpu_depolar_rate : float
        Depolarization rate for the QPU entities.
    switch_routing : dict
        Routing table for the FSO switch, defining how quantum information is routed.

    Returns
    -------
    tuple
        A tuple containing the simulation status, fidelity, and simulation time.
        Example: (status, fidelity, simtime)
    """
    # Initialize simulation
    ns.sim_reset()
    alice_node, bob_node, fsoswitch_node = setup_network(model_parameters)

    # Create and start the simulation protocol
    protocol = EntanglementProtocol(
        alice_node, bob_node, fsoswitch_node, switch_routing
    )
    protocol.start()

    # Run the simulation
    ns.sim_run()
    print(
        f"[QPU] Status: {alice_node.processor.status} | queue: {alice_node.get_queue()}"
    )
    fidelity = get_fidelities(alice_node, bob_node)
    print(f"FIDELITY: {fidelity}")

    # Return results
    return (protocol.results, fidelity)


# Runs the simulation several times, determined by the batch size.
def batch_run(model_parameters, qpu_depolar_rate, switch_routing, batch_size):
    """
    Run multiple quantum simulations with specified configurations and collect results.

    Parameters
    ----------
    model_parameters : dict
        Configuration parameters for the FSO switch model.
    qpu_depolar_rate : float
        Depolarization rate for the QPU entities.
    switch_routing : dict
        Routing table for the FSO switch.
    batch_size : int
        Number of simulation runs in the batch.

    Returns
    -------
    list[tuple]
        A list of tuples containing the simulation status and fidelity for each run.
    """
    results = []
    for _ in range(batch_size):
        res = single_run(model_parameters, qpu_depolar_rate, switch_routing)
        results.append(res)

    return results
