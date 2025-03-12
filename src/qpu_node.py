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

    # ======== PUBLIC METHODS ========
    # TODO move into protocol
    def apply_epl_gates_and_measurement(self):
        """
        Apply the local operations for EPL entanglement distillation.
        Uses the memory qubit (shielded qubit, index 1) as control and
        the fresh entanglement qubit (communication qubit, index 0) as target.
        This method performs the necessary gates (e.g. CNOT) and then measures the target.

        Returns:
            The measurement result (0 or 1) as set by the custom program.
        """
        logging.info(
            f"(QPUNode | {self.name}) Applying EPL distillation gates on qubit 1 (control) and qubit 0 (target)."
        )
        # We assume a custom quantum processor program (EPLDistillationProgram) exists.
        epl_prog = EPLDistillationProgram(control_index=1, target_index=0)
        self.add_program(epl_prog)

        # In a full implementation you might need to wait for the program to finish.
        # For now, we assume that once the program completes it sets an attribute:
        # self._last_epl_measurement with the measurement result.
        return getattr(self, "_last_epl_measurement", None)

    # TODO move into DataCollector callback
    def start_fidelity_calculation(self, request_id, position=0):
        """
        Emit a qubit from memory for fidelity calculation.

        Parameters
        ----------
        request_id: str, required
            The ID associated with the fidelity measurement request.
        position : int, optional
            The memory position of the qubit to emit, by default 0.
        """
        header = {"request_id": request_id}
        qubit = self.processor.peek(position, skip_noise=True)[0]
        state = qubit.qstate.qrepr
        logging.debug(f"State: {state}")
        clone = qapi.create_qubits(1, no_state=True)[0]
        qapi.assign_qstate(clone, state)
        msg = Message(qubit)
        msg.meta["header"] = json.dumps(header)
        self.ports["fidelity_out"].tx_output(msg)
