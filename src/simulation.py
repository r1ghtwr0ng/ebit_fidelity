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
    results = []
    for _ in range(batch_size):
        # Reset simulation
        ns.sim_reset()

        # Integration with the FSOSwitch
        alice = QPUEntity("AliceQPU", correction=False, depolar_rate=qpu_depolar_rate)
        bob = QPUEntity("BobQPU", correction=True, depolar_rate=qpu_depolar_rate)
        _charlie = QPUEntity("CharlieQPU", correction=True)  # TODO use 3 nodes

        # Connect QPU output ports to the switch input
        fsoswitch = FSOSwitch("bsm_fsoswitch", model_parameters)
        alice.processor.ports["qout_hdr"].connect(fsoswitch.ports["qin0"])
        bob.processor.ports["qout_hdr"].connect(fsoswitch.ports["qin1"])

        # Connect fsoswitch correction outputs to QPU correction inputs
        fsoswitch.ports["cout0"].connect(alice.processor.ports["correction"])
        fsoswitch.ports["cout1"].connect(bob.processor.ports["correction"])

        # TODO add quantum fibre channel between QPU and fsoswitch
        # Setup the routing table for the FSO switch
        fsoswitch.switch(switch_routing)

        # Start emit programs for both QPUEntities
        alice_req = 1
        bob_req = 2
        alice.register_id(alice_req)
        bob.register_id(bob_req)
        alice.emit()
        bob.emit()

        # Run simulation
        logging.debug("Starting simulation")
        stats = ns.sim_run()
        logging.debug(stats)

        # Unpack tuple return for debug purposes
        status, fidelity = get_fidelities(alice, bob)
        results.append((status, fidelity))
    return results
