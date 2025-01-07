import logging
import numpy as np
import netsquid as ns
import netsquid.qubits.ketstates as ks
import netsquid.qubits.qubitapi as qapi

from qpu_entity import QPUNode
from fso_switch import FSOSwitch
from protocols import EntanglementProtocol


# Get two qubits at positions 0 for alice and bob and calculate their fidelities
def get_fidelities(alice, bob):
    """
    Calculate the fidelities of entangled qubits for Alice and Bob.

    Parameters
    ----------
    alice : QPUNode
        The QPU entity representing Alice.
    bob : QPUNode
        The QPU entity representing Bob.

    Returns
    -------
    tuple
        A tuple containing:
        - status (bool): True if both Alice and Bob have valid qubits, False otherwise.
        - fidelity (float): Fidelity of the Bell state |B00>.
    """
    status = alice.get_status() and bob.get_status()
    qubit0 = alice.get_qubit(0)
    qubit1 = bob.get_qubit(0)
    fidelities = {
        "|00>": qapi.fidelity([qubit0, qubit1], np.array([1, 0, 0, 0]), squared=True),
        "|11>": qapi.fidelity([qubit0, qubit1], np.array([0, 0, 0, 1]), squared=True),
        "B00": qapi.fidelity([qubit0, qubit1], ks.b00, squared=True),
        "B01": qapi.fidelity([qubit0, qubit1], ks.b01, squared=True),
        "B10": qapi.fidelity([qubit0, qubit1], ks.b10, squared=True),
        "B11": qapi.fidelity([qubit0, qubit1], ks.b11, squared=True),
    }

    if status:
        logging.debug(f"[GREPPABLE] Simulation output: {fidelities}")

    return status, fidelities["B00"]


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
    ns.sim_reset()

    # Create nodes
    alice_node = QPUNode("AliceNode", correction=True)
    bob_node = QPUNode("BobNode")
    fsoswitch_node = FSOSwitch("bsm_fsoswitch", model_parameters)

    # Connect node-level ports
    alice_node.processor.ports["qout_hdr"].connect(fsoswitch_node.ports["qin0"])
    bob_node.processor.ports["qout_hdr"].connect(fsoswitch_node.ports["qin1"])
    fsoswitch_node.ports["cout0"].connect(alice_node.processor.ports["correction"])
    fsoswitch_node.ports["cout1"].connect(bob_node.processor.ports["correction"])

    # Create and start the simulation protocol
    protocol = EntanglementProtocol(
        alice_node, bob_node, fsoswitch_node, switch_routing
    )
    protocol.start()

    # Run the simulation
    ns.sim_run()

    # Return results
    return protocol.results


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
