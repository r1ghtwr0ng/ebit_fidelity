# Imports section
import logging

from netsquid.components.component import Component
from netsquid.qubits import qubitapi as qapi
import netsquid.qubits.ketstates as ks

# ---- CLASSES ----
class FidelityCalculator(Component):
    def __init__(self, name):
        logging.debug(f"(FidelityCalc | {self.name}) Logging check in __init__")
        super().__init__(name, port_names=["qin0", "qin1", "qout0", "qout1"])
        self.qubit_slot = None
        self._setup_handlers()

    def _setup_handlers(self):
        """Set port handlers."""
        self.ports["qin0"].bind_input_handler(lambda msg: self.measure_or_store(msg, "qin0"))
        self.ports["qin1"].bind_input_handler(lambda msg: self.measure_or_store(msg, "qin1"))

    def measure_or_store(self, msg, port):
        logging.debug(f"(FidelityCalc | {self.name}) Received qubit on port {port}")
        inbound_qubit = msg.items[0] 
        if self.qubit_slot is None:
            self.qubit_slot = inbound_qubit # Move the qubit in the qubit slot
        else:
            # TODO fidelity measurement and return qubits to Alice and Bob
            logging.debug(f"(FidelityCalc | {self.name}) Starting fidelity measurement")
            fidelity = self.calculate_fidelity(self.qubit_slot, inbound_qubit)
            logging.debug(f"(FidelityCalc | {self.name}) Fidelity output: {fidelity}")
            # TODO send this over back to the channels
            pass

    def return_qubits(self):
        """
        Returns the qubits to their original owners (Alice and Bob).
        """
        # TODO implement qubit return mechanism
        # Here we would implement logic to return the qubits to Alice and Bob.
        # This may involve reconnecting to their respective processors or queues.
        # Placeholder print statement as example:
        logging.debug(f"(FidelityCalc.return_qubits | {self.name}) Returning qubits to Alice and Bob")
        # Clear the stored qubits after returning them
        self.alice_qubit = None
        self.bob_qubit = None
        
    @staticmethod
    def calculate_fidelity(qubit0, qubit1):
        """
        Calculates and prints the fidelity between the two qubits
        """
        try:
            fidelities = {
                'B00': qapi.fidelity([qubit0, qubit1], ks.b00, squared=True),
                'B01': qapi.fidelity([qubit0, qubit1], ks.b01, squared=True),
                'B10': qapi.fidelity([qubit0, qubit1], ks.b10, squared=True),
                'B11': qapi.fidelity([qubit0, qubit1], ks.b11, squared=True)
            }
            logging.info(f"(FidelityCalculator.calculate_fidelity) Fidelities output: {fidelities}")
        except Exception as e:
            logging.error(f"(FidelityCalculator.calculate_fidelity) Error calculating fidelity: {e}")

