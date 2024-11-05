# Imports section
import logging
import netsquid as ns

# from netsquid.examples.repeater_chain import FibreDepolarizeModel
# from netsquid.components.models import FibreDelayModel, FibreLossModel

# Import from own code
from qpu_entity import QPUEntity
from detectors import BSMDetector
from fidelity_calculator import FidelityCalculator


# ---- CLASSES ----
def run():
    # Reset simulation
    ns.sim_reset()

    # Create a fidelity calculator component
    logging.debug("Initializing fidelity calculator")
    calculator = FidelityCalculator("calculator")

    # Integration with the BSMDetector
    logging.debug("Initializing Alice and Bob entities")
    alice = QPUEntity("AliceQPU", correction=False)
    bob = QPUEntity("BobQPU", correction=True)

    # Connect QPU output ports to the detector input
    logging.debug("Initializing detector and binding ports")
    detector = BSMDetector("bsm_detector")
    alice.processor.ports["qout"].connect(detector.ports["qin0"])
    bob.processor.ports["qout"].connect(detector.ports["qin1"])

    # Connect QPUs to the fidelity calculation device
    logging.debug("Binding Alice and Bob ports to fidelity calculator")
    alice.processor.ports["qout0"].connect(calculator.ports["qin0"])
    bob.processor.ports["qout0"].connect(calculator.ports["qin1"])

    # Connect detector correction outputs to QPU correction inputs
    logging.debug("Binding detector output to Alice and Bob's correction ports")
    detector.ports["cout0"].connect(alice.processor.ports["correction"])
    detector.ports["cout1"].connect(bob.processor.ports["correction"])

    logging.debug("Binding fidelity calculator return to the QPU ports")
    calculator.ports["qout0"].connect(alice.processor.ports["qin0"])
    calculator.ports["qout1"].connect(bob.processor.ports["qin0"])

    # TODO add quantum fibre channel between QPU and detector
    # TODO refactor public methods to private where applicable

    # Start emit programs for both QPUEntities
    alice.emit()
    bob.emit()

    # Run simulation
    logging.debug("Starting simulation")
    stats = ns.sim_run()
    logging.debug(stats)

    return calculator.get_fidelities()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    result = []
    for i in range(1000):
        logging.debug(f"Starting Run {i}")
        ret = run()
        result += ret

    logging.info(result)
