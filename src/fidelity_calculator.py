import logging
import numpy as np

from netsquid.components.component import Message
from netsquid.components.component import Component
from netsquid.qubits import qubitapi as qapi
import netsquid.qubits.ketstates as ks


class FidelityCalculator(Component):
    """
    Component that calculates the fidelity between two entangled qubits.

    This component receives qubits from two input ports, stores them temporarily,
    and calculates their fidelity once both qubits are available. The results
    are stored and returned via designated output ports.
    """

    def __init__(self, name):
        """
        Initialize the FidelityCalculator with the specified name, input and output ports, and handlers.

        Parameters
        ----------
        name : str
            Name of the fidelity calculator component, used for logging and identification.
        """
        logging.debug(f"(FidelityCalc | {self.name}) Logging check in __init__")
        super().__init__(name, port_names=["qin0", "qin1", "qout0", "qout1"])
        self.__fidelity_arr = []
        self.__qubit_slots = {"qin0": None, "qin1": None}
        self.__setup_handlers()

    def __setup_handlers(self):
        """Set up handlers for input ports to process incoming qubits."""
        self.ports["qin0"].bind_input_handler(
            lambda msg: self.measure_or_store(msg, "qin0")
        )
        self.ports["qin1"].bind_input_handler(
            lambda msg: self.measure_or_store(msg, "qin1")
        )

    def get_fidelities(self):
        """
        Retrieve the list of calculated fidelities.

        Returns
        -------
        list
            A list of fidelity values computed by the component.
        """
        return self.__fidelity_arr

    def measure_or_store(self, msg, port):
        """
        Process incoming qubits by storing them and calculating fidelity when both are present.

        Parameters
        ----------
        msg : Message
            The message containing the qubit.
        port : str
            The port on which the qubit was received ("qin0" or "qin1").
        """
        logging.debug(f"(FidelityCalc | {self.name}) Received qubit on port {port}")
        inbound_qubit = msg.items[0]

        if port not in self.__qubit_slots:
            logging.error(
                f"(FidelityCalculator | {self.name}) Received qubit from unexpected port: {port}"
            )
            return
        elif self.__qubit_slots[port]:
            logging.debug(
                f"(FidelityCalculator | {self.name}) Inbound qubit on port {port} replaces existing qubit"
            )

        self.__qubit_slots[port] = inbound_qubit
        if self.__qubit_slots["qin0"] is None or self.__qubit_slots["qin1"] is None:
            logging.debug(
                f"(FidelityCalc | {self.name}) one qubit is loaded into the slots {self.__qubit_slots}"
            )
        else:
            fidelity = self.calculate_fidelity(
                self.__qubit_slots["qin0"], self.__qubit_slots["qin1"]
            )
            logging.debug(f"(FidelityCalc | {self.name}) Fidelity output: {fidelity}")
            self.__fidelity_arr.append(fidelity)  # Keep track of fidelities
            self.return_qubits()

    def return_qubits(self):
        """
        Returns the qubits to their original owners via output ports and clears the slots.
        """
        logging.debug(
            f"(FidelityCalc.return_qubits | {self.name}) Returning qubits to Alice and Bob"
        )

        # Pop the qubits off the slots
        q0 = self.__qubit_slots.pop("qin0")
        q1 = self.__qubit_slots.pop("qin1")

        # Create messages and send them off via the output ports
        header = "fidelity"
        msg0 = Message(q0, header=header)
        msg1 = Message(q1, header=header)
        self.ports["qout0"].tx_output(msg0)
        self.ports["qout1"].tx_output(msg1)

    @staticmethod
    def calculate_fidelity(qubit0, qubit1):
        """
        Calculates the fidelity between two qubits in various Bell states.

        Parameters
        ----------
        qubit0 : Qubit
            The first qubit for fidelity calculation.
        qubit1 : Qubit
            The second qubit for fidelity calculation.

        Returns
        -------
        float
            The fidelity value between the qubits in the Bell state ``|B00>``.

        Notes
        -----
        This method also calculates fidelities for several target states (``|00>``, ``|11>``, and Bell states ``B00``, ``B01``, ``B10``, ``B11``).
        Fidelity for the Bell state ``|B00>`` is returned, and all results are logged for debugging.
        """
        try:
            fidelities = {
                "|00>": qapi.fidelity(
                    [qubit0, qubit1], np.array([1, 0, 0, 0]), squared=True
                ),
                "|11>": qapi.fidelity(
                    [qubit0, qubit1], np.array([0, 0, 0, 1]), squared=True
                ),
                "B00": qapi.fidelity([qubit0, qubit1], ks.b00, squared=True),
                "B01": qapi.fidelity([qubit0, qubit1], ks.b01, squared=True),
                "B10": qapi.fidelity([qubit0, qubit1], ks.b10, squared=True),
                "B11": qapi.fidelity([qubit0, qubit1], ks.b11, squared=True),
            }
            logging.debug(f"(FidelityCalc) Fidelities output: {fidelities}")
            return fidelities["B00"]
        except Exception as e:
            logging.error(
                f"(FidelityCalculator.calculate_fidelity) Error calculating fidelity: {e}"
            )
