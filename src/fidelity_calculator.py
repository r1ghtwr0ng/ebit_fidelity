# Imports section
import numpy as np
import netsquid as ns
import pydynaa
import logging

from collections import deque
from netsquid.qubits import Operator
from netsquid.components import Component
from netsquid.components import QuantumChannel, ClassicalChannel, Message
from netsquid.components.qprogram import QuantumProgram
from netsquid.components.qdetector import QuantumDetector
from netsquid.components.qprocessor import QuantumProcessor, PhysicalInstruction

import netsquid.qubits.ketstates as ks
from netsquid.qubits import qubitapi as qapi

# ---- CLASSES ----
class FidelityCalculator(Component):
    def __init__(self, name):
        logging.debug("(FidelityCalc) Logging check in __init__")
        super().__init__(name, port_names=["qin0", "qin1", "qout0", "qout1"])
        self.qubit_slot = None
        self._setup_handlers()

    def _setup_handlers(self):
        """Set port handlers."""
        self.ports["qin0"].bind_input_handler(lambda msg: self.measure_or_store(msg, "qin0"))
        self.ports["qin1"].bind_input_handler(lambda msg: self.measure_or_store(msg, "qin1"))

    def measure_or_store(self, msg, port):
        logging.debug(f"(FidelityCalc) Received qubit on port {port}")
        if self.qubit_slot is None:
            self.qubit_slot = msg.items[0] # Move the qubit in the qubit slot
        else:
            # TODO fidelity measurement and return qubits to Alice and Bob
            logging.debug("(FidelityCalc) Starting fidelity measurement")
            pass

    def return_qubits(self):
        """
        Returns the qubits to their original owners (Alice and Bob).
        """
        # TODO implement qubit return mechanism
        # Here we would implement logic to return the qubits to Alice and Bob.
        # This may involve reconnecting to their respective processors or queues.
        # Placeholder print statement as example:
        logging.debug("(FidelityCalc) Returning qubits to Alice and Bob")
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
            print("Fidelities:", fidelities)
        except Exception as e:
            print("Error calculating fidelity:", e)


