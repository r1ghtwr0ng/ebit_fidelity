import logging
import numpy as np
import netsquid as ns
import matplotlib as plt
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
        logging.info(f"[GREPPABLE] Simulation output: {fidelities}")

    return status, fidelities["B00"]


# Runs the simulation once.
def run(model_parameters):
    # Reset simulation
    ns.sim_reset()

    # Integration with the FSOSwitch
    alice = QPUEntity("AliceQPU", correction=False)
    bob = QPUEntity("BobQPU", correction=True)
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
    routing = {"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"}
    fsoswitch.switch(routing)

    # Start emit programs for both QPUEntities
    alice_req = 1
    bob_req = 2
    alice.register_id(alice_req)
    bob.register_id(bob_req)
    alice.emit()
    bob.emit()

    # Run simulation
    logging.info("Starting simulation")
    stats = ns.sim_run()
    logging.info(stats)

    return get_fidelities(alice, bob)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    model_parameters = {
        "short": {
            "init_loss": 0,
            "len_loss": 0,  # .25,
            "init_depolar": 0,
            "len_depolar": 0,
            "channel_len": 1,
        },
        "mid": {
            "init_loss": 0,
            "len_loss": 0,  # .25,
            "init_depolar": 0,
            "len_depolar": 0,
            "channel_len": 1.2,
        },
        "long": {
            "init_loss": 0,
            "len_loss": 0,  # .25,
            "init_depolar": 0,
            "len_depolar": 0,
            "channel_len": 1.4,
        },
    }
    result = []
    for i in range(100):
        logging.info(f"Starting Run {i}")
        status, fidelity = run(model_parameters)
        if status:
            result.append(fidelity)

    logging.info(f"Fidelities for successful results: {result}")
