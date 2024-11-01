# Imports section
import logging
import netsquid as ns

# from netsquid.examples.repeater_chain import FibreDepolarizeModel
# from netsquid.components.models import FibreDelayModel, FibreLossModel

# Import from own code
from qpu_entity import QPUEntity
from detector import BSMDetector
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
    alice = QPUEntity("AliceQPU", "X")
    bob = QPUEntity("BobQPU", "Z")

    # Connect QPU output ports to the detector input
    logging.debug("Initializing detector and binding ports")
    detector = BSMDetector("bsm_detector")
    alice.processor.ports['qout'].connect(detector.ports['qin0'])
    bob.processor.ports['qout'].connect(detector.ports['qin1'])
    
    # Connect QPUs to the fidelity calculation device
    logging.debug("Binding Alice and Bob ports to fidelity calculator")
    alice.processor.ports['qout0'].connect(calculator.ports['qin0'])
    bob.processor.ports['qout0'].connect(calculator.ports['qin1'])

    # Connect detector correction outputs to QPU correction inputs
    logging.debug("Binding fidelity calculator to Alice and Bob's ports")
    detector.ports['cout0'].connect(alice.processor.ports['correction'])
    detector.ports['cout1'].connect(bob.processor.ports['correction'])

    # TODO bind the calculator output ports back to the QPUEntity inputs
    # TODO handle inbound returning qubits from the fidelity calculation code
    # TODO add quantum fibre channel between QPU and detector

    # Start emit programs for both QPUEntities
    alice.emit()
    bob.emit()
        
    # Run simulation
    logging.debug("Starting simulation")
    stats = ns.sim_run()
    logging.debug(stats)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    for i in range(1):
        logging.debug(f"Starting Run {i}")
        run()
