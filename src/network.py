import time
import logging
import numpy as np
import netsquid as ns
import netsquid.qubits.ketstates as ks
import netsquid.qubits.qubitapi as qapi

from qpu_entity import QPUEntity
from fso_switch import FSOSwitch
from fidelity_calculator import FidelityCalculator

# from netsquid.examples.repeater_chain import FibreDepolarizeModel
# from netsquid.components.models import FibreDelayModel, FibreLossModel


# Runs the simulation once.
def run():
    # Reset simulation
    ns.sim_reset()

    # Create a fidelity calculator component
    calculator = FidelityCalculator("calculator")

    # Integration with the FSOSwitch
    alice = QPUEntity("AliceQPU", correction=False)
    bob = QPUEntity("BobQPU", correction=True)
    _charlie = QPUEntity("CharlieQPU", correction=True)  # TODO use 3 nodes

    # Connect QPU output ports to the switch input
    fsoswitch = FSOSwitch("bsm_fsoswitch")
    alice.processor.ports["qout_hdr"].connect(fsoswitch.ports["qin0"])
    bob.processor.ports["qout_hdr"].connect(fsoswitch.ports["qin1"])

    # Connect QPUs to the fidelity calculation device
    alice.processor.ports["qout0_hdr"].connect(calculator.ports["qin0"])
    bob.processor.ports["qout0_hdr"].connect(calculator.ports["qin1"])

    # Connect fsoswitch correction outputs to QPU correction inputs
    fsoswitch.ports["cout0"].connect(alice.processor.ports["correction"])
    fsoswitch.ports["cout1"].connect(bob.processor.ports["correction"])

    calculator.ports["qout0"].connect(alice.processor.ports["qin0"])
    calculator.ports["qout1"].connect(bob.processor.ports["qin0"])

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
    logging.debug(stats)

    status = alice.get_status()
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

    return fidelities["B00"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    result = []
    for i in range(100):
        logging.info(f"Starting Run {i}")
        ret = run()
        result.append(ret)

    logging.info(result)
