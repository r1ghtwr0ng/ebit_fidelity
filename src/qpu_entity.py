import json
import logging
import netsquid as ns

from netsquid.nodes import Node
from collections import deque
from netsquid.components import Component
from netsquid.components.component import Message
from netsquid.components.qprocessor import QuantumProcessor
from qpu_programs import EmitProgram, CorrectYProgram, CorrectXProgram

import netsquid.qubits.qubitapi as qapi


class QPUComponent(Component):
    def __init__(self, name, correction=False, qbit_count=2, depolar_rate=0):
        super().__init__(name=f"{name}_component")
        self.qpu_entity = QPUNode(name, correction, qbit_count, depolar_rate)

    def get_entity(self):
        return self.qpu_entity


class QPUNode(Node):
    """
    Represents an entity (i.e. the legendary Alice and Bob) with a quantum processing
    unit (QPU) with a program queue and callback functionality. If a program needs to be
    executed it should be added to the queue using the add_program method.

    Parameters
    ----------
    name : str
        The name of the QPU entity.
    correction : bool, optional
        Whether to apply correction based on received measurements, by default False.
    qbit_count : int, optional
        Number of qubits in the processor, by default 2.
    depolar_rate : float, optional
        Depolarization rate for the noise model, by default 0.
    """

    def __init__(self, name, correction=False, qbit_count=2, depolar_rate=0):
        super().__init__(name)
        # The last qubit slot is used for photon emission into fibre
        self.processor = self.__create_processor(name, qbit_count, depolar_rate)
        self.__emission_idx = qbit_count - 1
        self.__correction = correction
        self.__queue = deque()
        self.__measuring = False
        self.__status = False
        self.__setup_callbacks()
        self.__requests = {}
        self.__events = {}
        self.__calc_fideltiy = False

    # ======== PRIVATE METHODS ========
    # Helper function to create a simple QPU with a few useful instructions
    def __create_processor(self, name, qbit_count, depolar_rate):
        """
        Private helper method used to initialize the quantum processor for the entity.

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
            A configured quantum processor with specified characteristics.
        """
        physical_instructions = [
            ns.components.qprocessor.PhysicalInstruction(
                ns.components.instructions.INSTR_INIT, duration=3, parallel=True
            ),
            ns.components.qprocessor.PhysicalInstruction(
                ns.components.instructions.INSTR_H, duration=1, parallel=True
            ),
            ns.components.qprocessor.PhysicalInstruction(
                ns.components.instructions.INSTR_X, duration=1, parallel=True
            ),
            ns.components.qprocessor.PhysicalInstruction(
                ns.components.instructions.INSTR_Y, duration=1, parallel=True
            ),
            ns.components.qprocessor.PhysicalInstruction(
                ns.components.instructions.INSTR_Z, duration=1, parallel=True
            ),
            ns.components.qprocessor.PhysicalInstruction(
                ns.components.instructions.INSTR_CNOT,
                duration=4,
                parallel=True,
                topology=[(0, 1)],
            ),
            ns.components.qprocessor.PhysicalInstruction(
                ns.components.instructions.INSTR_EMIT, duration=1, parallel=True
            ),
            ns.components.qprocessor.PhysicalInstruction(
                ns.components.instructions.INSTR_MEASURE, duration=7, parallel=False
            ),
        ]
        memory_noise_model = ns.components.models.DepolarNoiseModel(
            depolar_rate=depolar_rate
        )
        processor = QuantumProcessor(
            name,
            num_positions=qbit_count,
            memory_noise_models=[memory_noise_model] * qbit_count,
            phys_instructions=physical_instructions,
        )
        processor.add_ports(["correction", "qout_hdr", "qout0_hdr"])
        return processor

    # Helper for setting up the callbacks and handlers
    def __setup_callbacks(self):
        """Set up callback handling for when programs complete."""
        self.processor.set_program_done_callback(self.__on_program_done, once=False)
        self.processor.set_program_fail_callback(self.__on_program_fail, once=False)
        self.processor.ports["qout"].bind_output_handler(
            self.__setup_header_wrapper, tag_meta=True
        )
        self.processor.ports["qout0"].bind_output_handler(
            self.__setup_header_wrapper, tag_meta=True
        )
        self.processor.ports["correction"].bind_input_handler(
            self.__correction_callback
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

    # Callback for when a QPU program finishes executing successfully
    def __on_program_done(self):
        """Handle completion of a program, and process the next one if queued."""
        logging.debug(f"(QPUNode | {self.name}) program complete")
        if len(self.__queue) > 0 and not self.processor.busy:
            if self.processor.peek(0, skip_noise=True)[0] is not None:
                next_program = self.__queue.popleft()
                logging.debug(
                    f"(QPUNode | {self.name}) queuing next program: {next_program}"
                )
                self.add_program(next_program)

    # Callback for when a QPU program exits with a failure
    def __on_program_fail(self):
        """Callback that's run on QPU program failure."""
        logging.debug(f"(QPUNode | {self.name}) program resulted in a failure.")
        if len(self.__queue) > 0:
            (next_program, request_id) = self.__queue.popleft()
            logging.debug(
                f"(QPUNode | {self.name}) queuing next program: {next_program} with request ID: {request_id}"
            )
            self.add_program(next_program)

    # Callback function for applying qubit corrections based on BSMDetector output
    def __correction_callback(self, msg):
        """
        Callback function, this runs whenever a Bell state measurement is received for
        the emitted photons. Used to apply qubit correction and get the ebit pair to
        the |00> + |11> Bell state.

        Parameters
        ----------
        msg : Message
            The message containing BSM results for corrections.
        """
        bell_idx = msg.items[0].bell_index
        self.__status = msg.items[0].success
        if self.__correction:
            logging.debug(
                f"(QPUNode | {self.name}) Fidelities output: Bell Index: {bell_idx}"
            )

        if bell_idx == 1 and self.__correction:
            # This means the state is in state |01> + |10> and needs X correction to
            # become |00> + |11>
            logging.debug(f"(QPUNode | {self.name}) Performing X correction")
            self.add_program(CorrectXProgram())
        elif bell_idx == 2 and self.__correction:
            # This means the state is in state |01> - |10> and needs X correction to
            # become |00> + |11>
            logging.debug(f"(QPUNode | {self.name}) Performing Y correction")
            self.add_program(CorrectYProgram())
        else:
            logging.debug(f"(QPUNode | {self.name}) No correction needed")

    # ======== PUBLIC METHODS ========
    # Register a current request ID to send over to the FSO switch
    def register_id(self, request_id):
        """
        Register the request ID which is expected by the FSO switch in the msg metadata.
        TODO see if this is even useful.

        Parameters
        ----------
        request_id: str, required
            ID of the request being registered.
        """
        pass

    # Use this function to append programs to the object queue
    def add_program(self, program):
        """
        Add a program to the queue and execute if the processor is available.

        Parameters
        ----------
        program : QuantumProgram
            The quantum program to be added to the QPU's queue.
        """
        logging.debug(f"(QPUNode | {self.name}) Call to add_program with {program}")
        if not self.processor.busy:
            if not self.__measuring:
                logging.debug(f"(QPUNode | {self.name}) executing program {program}")
                _event = self.processor.execute_program(program)  # TODO handle event
                # TODO handle this event somehow
                # event.wait(callback=lambda: logging.debug(f"Program done callback"))
            else:
                logging.debug(
                    f"(QPUNode | {self.name}) appending program to queue (measuring qubit fidelity)"
                )
                self.__queue.append(program)
        else:
            logging.debug(
                f"(QPUNode | {self.name}) appending program to queue (QPU busy)"
            )
            self.__queue.append(program)

    # Get the status of the last exchange request
    def get_status(self):
        """
        Getter function to retrieve the status outcome of a given request.

        Parameters
        ----------
        request_id: str, required
            ID of the request whose status you want to check.
        """
        # TODO search by request ID
        return self.__status

    def get_qubit(self, position=0):
        qubit = self.processor.peek(position, skip_noise=True)[0]
        return qubit

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
        print(f"State: {state}")
        clone = qapi.create_qubits(1, no_state=True)[0]
        qapi.assign_qstate(clone, state)
        msg = Message(qubit)
        msg.meta["header"] = json.dumps(header)
        self.ports["fidelity_out"].tx_output(msg)

    def emit(self, position=0):
        """
        Trigger the emission of a photon entangled with the memory qubit at the
        specified position.

        Parameters
        ----------
        position : int
            The memory position of the qubit to emit and entangle with a photon.
        """

        self.add_program(EmitProgram(position, self.__emission_idx))
