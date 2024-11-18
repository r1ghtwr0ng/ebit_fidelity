# Imports section
import logging
import netsquid as ns

# Import from own code
from qpu_entity import QPUEntity
from fso_switch import FSOSwitch
from fidelity_calculator import FidelityCalculator

# from netsquid.examples.repeater_chain import FibreDepolarizeModel
# from netsquid.components.models import FibreDelayModel, FibreLossModel


# ---- CLASSES ----
def run():
    # Reset simulation
    ns.sim_reset()

    # Create a fidelity calculator component
    calculator = FidelityCalculator("calculator")

    # Integration with the FSOSwitch
    alice = QPUEntity("AliceQPU", correction=False)
    bob = QPUEntity("BobQPU", correction=True)

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
    logging.debug("Starting simulation")
    stats = ns.sim_run()
    logging.debug(stats)

    return calculator.get_fidelities()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    result = []
    for i in range(10):
        logging.debug(f"Starting Run {i}")
        ret = run()
        result += ret

    logging.info(result)
