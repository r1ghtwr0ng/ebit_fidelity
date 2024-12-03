import logging
import numpy as np
import netsquid as ns
import netsquid.qubits.ketstates as ks
import netsquid.qubits.qubitapi as qapi

from qpu_entity import QPUEntity
from fso_switch import FSOSwitch

# from netsquid.examples.repeater_chain import FibreDepolarizeModel
# from netsquid.components.models import FibreDelayModel, FibreLossModel


# Get two qubits at positions 0 for alice and bob and calculate their fidelities
def get_fidelities(alice, bob):
    """
    Calculate the fidelities of entangled qubits for Alice and Bob.

    Parameters
    ----------
    alice : QPUEntity
        The QPU entity representing Alice.
    bob : QPUEntity
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
        # Reset the simulation to avoid state carryover between runs.
        ns.sim_reset()

        # Initialize QPU entities with their respective depolarization rates and correction settings.
        alice = QPUEntity("AliceQPU", correction=False, depolar_rate=qpu_depolar_rate)
        bob = QPUEntity("BobQPU", correction=True, depolar_rate=qpu_depolar_rate)
        _charlie = QPUEntity("CharlieQPU", correction=True)

        # Create and configure the FSO switch for routing quantum information.
        fsoswitch = FSOSwitch("bsm_fsoswitch", model_parameters)
        alice.processor.ports["qout_hdr"].connect(fsoswitch.ports["qin0"])
        bob.processor.ports["qout_hdr"].connect(fsoswitch.ports["qin1"])

        # Connect the FSO switch's correction outputs to the QPU correction inputs.
        fsoswitch.ports["cout0"].connect(alice.processor.ports["correction"])
        fsoswitch.ports["cout1"].connect(bob.processor.ports["correction"])

        # TODO: Implement quantum fiber channels for enhanced realism.
        # Configure the routing table of the FSO switch.
        fsoswitch.switch(switch_routing)

        # Start the emit programs for Alice and Bob QPUs.
        alice_req = 1  # Unique identifier for Alice's request.
        bob_req = 2  # Unique identifier for Bob's request.
        alice.register_id(alice_req)
        bob.register_id(bob_req)
        alice.emit()
        bob.emit()

        # Run the simulation and log the process.
        logging.debug("Starting simulation")
        stats = ns.sim_run()
        simtime = ns.sim_time()

        # Extract and log simulation results for debugging purposes.
        status, fidelity = get_fidelities(alice, bob)
        results.append((status, fidelity, simtime))

    return results
