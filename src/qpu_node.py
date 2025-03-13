import json
import logging
import netsquid as ns
import netsquid.qubits.qubitapi as qapi

from netsquid.nodes import Node
from netsquid.components.component import Message
from netsquid.components.qprocessor import QuantumProcessor

from qpu_programs import (
    EPLDistillationProgram,
)


class QPUNode(Node):
    """
    Represents an entity (i.e. the legendary Alice and Bob) with a quantum processing
    unit (QPU) with a program queue and callback functionality. If a program needs to be
    executed it should be added to the queue using the add_program method.

    Qubit mapping:
    0 - Emission qubit
    1 - Communications qubit, entangled with emission qubit
    2 - Shielded qubit, used for storing & distilling entanglement

    Parameters
    ----------
    name : str
        The name of the QPU entity.
    qbit_count : int, optional
        Number of qubits in the processor, by default 2.
    depolar_rate : float, optional
        Depolarization rate for the noise model, by default 0.
    """

    def __init__(self, name, qbit_count=3, depolar_rate=0):
        super().__init__(name, port_names=["corrections"])
        # The last qubit slot is used for photon emission into fibre
        self.processor = self.__create_processor(name, qbit_count, depolar_rate)
        self.__setup_callbacks()
        # Keep track of qubit mappings
        self.emit_idx = 0
        self.comm_idx = 1
        self.shielded_idx = 2

    # ======== PRIVATE METHODS ========
    # Helper function to create a simple QPU with a few useful instructions
    def __create_processor(self, name, qbit_count, depolar_rate):
        """
        Private helper method used to initialize the quantum processor for the entity.
        We have nonphysical instructions as we use an abstract QPU architecture.

        Parameters
        ----------
        name : str
            Name of the quantum processor.
        qbit_count : int
            Number of qubits in the processor.
        depolar_rate : float
            Depolarization rate for the noise model.

        Returns
        -------
        QuantumProcessor
            A configured quantum processor with fallback to nonphysical instructions.
        """
        memory_noise_model = ns.components.models.DepolarNoiseModel(
            depolar_rate=depolar_rate
        )
        processor = QuantumProcessor(
            name,
            num_positions=qbit_count,
            memory_noise_models=[memory_noise_model] * qbit_count,
            phys_instructions=None,
            fallback_to_nonphysical=True,  # Execute instructions as nonphysical
        )
        # TODO fix this to not be in the processor
        processor.add_ports(["qout_hdr", "qout0_hdr"])
        return processor

    # Helper for setting up the callbacks and handlers
    def __setup_callbacks(self):
        """Set up callback handling for when programs complete."""
        self.processor.ports["qout"].bind_output_handler(
            self.__setup_header_wrapper, tag_meta=True
        )
        self.processor.ports["qout0"].bind_output_handler(
            self.__setup_header_wrapper, tag_meta=True
        )
        # self.ports["corrections"].bind_input_handler(self.__debug, tag_meta=True)

    def __debug(self, msg):
        port = msg.meta.get("rx_port_name", "missing_port_metadata")
        logging.debug(f"Received message on port: {port}, MSG: {msg}")

    def __setup_header_wrapper(self, msg):
        """
        Add metadata headers to outbound messages for routing and identification.

        Parameters
        ----------
        msg : object
            The message object containing metadata and payload to be transmitted.

        Returns
        -------
        None
            Modifies the message in place by adding a JSON-serialized header.
        """
        port = msg.meta.get("rx_port_name", "missing_port_metadata")
        event_id = msg.meta["put_event"].id

        header = {"event_id": event_id, "request_id": "TODO"}
        msg.meta["header"] = json.dumps(header)
        self.processor.ports[f"{port}_hdr"].tx_output(msg)
