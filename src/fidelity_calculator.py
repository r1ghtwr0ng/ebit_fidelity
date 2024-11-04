# Imports section
import logging
import numpy as np

from netsquid.components.component import Message
from netsquid.components.component import Component
from netsquid.qubits import qubitapi as qapi
import netsquid.qubits.ketstates as ks

class FidelityCalculator(Component):
    def __init__(self, name):
        logging.debug(f"(FidelityCalc | {self.name}) Logging check in __init__")
        super().__init__(name, port_names=["qin0", "qin1", "qout0", "qout1"]) 
        self.__fidelity_arr = []
        self.__qubit_slots = {"qin0": None, "qin1": None}
        self.__setup_handlers()

    def __setup_handlers(self):
        """Set port handlers."""
        self.ports["qin0"].bind_input_handler(lambda msg: self.measure_or_store(msg, "qin0"))
        self.ports["qin1"].bind_input_handler(lambda msg: self.measure_or_store(msg, "qin1"))

    # Fidelity array getter
    def get_fidelities(self):
        return self.__fidelity_arr

    # Upon receival of a new qubit, store in the appropriate slot and determine what to do
    def measure_or_store(self, msg, port):
        logging.debug(f"(FidelityCalc | {self.name}) Received qubit on port {port}")
        inbound_qubit = msg.items[0] 
        if port not in self.__qubit_slots:
            logging.error(f"(FidelityCalculator | {self.name}) Received qubit from unexpected port: {port}")
            return
        elif self.__qubit_slots[port]:
            logging.debug(f"(FidelityCalculator | {self.name}) Inbound qubit on port {port} replaces existing qubit")

        self.__qubit_slots[port] = inbound_qubit
        if self.__qubit_slots['qin0'] is None or self.__qubit_slots['qin1'] is None:
            logging.debug(f"(FidelityCalc | {self.name}) one qubit is loaded into the slots {self.__qubit_slots}")
        else:
            fidelity = self.calculate_fidelity(self.__qubit_slots['qin0'], self.__qubit_slots['qin1'])
            # TODO send of fidelity result to main box listener
            logging.debug(f"(FidelityCalc | {self.name}) Fidelity output: {fidelity}")
            self.__fidelity_arr.append(fidelity)
            self.return_qubits()

    # Return the qubits to their respective nodes and remove them from the slots
    def return_qubits(self):
        """
        Returns the qubits to their original owners (Alice and Bob).
        """
        logging.debug(f"(FidelityCalc.return_qubits | {self.name}) Returning qubits to Alice and Bob")

        # Pop the qubits off the slots
        q0 = self.__qubit_slots.pop('qin0')
        q1 = self.__qubit_slots.pop('qin1')

        # Create messages and send them off via the output ports
        header = 'fidelity'
        msg0 = Message(q0, header=header)
        msg1 = Message(q1, header=header)
        self.ports['qout0'].tx_output(msg0)
        self.ports['qout1'].tx_output(msg1)

    @staticmethod
    def calculate_fidelity(qubit0, qubit1):
        """
        Calculates and prints the fidelity between the two qubits
        """
        # TODO fix the issue where 11 is interpreted as state 2
        try:
            fidelities = {
                '00': qapi.fidelity([qubit0, qubit1], np.array([1, 0, 0, 0]), squared=True),
                '11': qapi.fidelity([qubit0, qubit1], np.array([0, 0, 0, 1]), squared=True),
                'B00': qapi.fidelity([qubit0, qubit1], ks.b00, squared=True),
                'B01': qapi.fidelity([qubit0, qubit1], ks.b01, squared=True),
                'B10': qapi.fidelity([qubit0, qubit1], ks.b10, squared=True),
                'B11': qapi.fidelity([qubit0, qubit1], ks.b11, squared=True)
            }
            logging.debug(f"(FidelityCalc) Fidelities output: {fidelities}")
            return fidelities['B00']
        except Exception as e:
            logging.error(f"(FidelityCalculator.calculate_fidelity) Error calculating fidelity: {e}")

