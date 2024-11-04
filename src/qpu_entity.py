# Imports section
import logging
import netsquid as ns

from collections import deque
from netsquid.components.qprogram import QuantumProgram
from netsquid.components.qprocessor import QuantumProcessor

import netsquid.components.instructions as instr

class QPUEntity(ns.pydynaa.Entity):
    """Represents a quantum processing unit (QPU) with program queue and callback functionality."""

    def __init__(self, name, correction, qbit_count=2, depolar_rate=0):
        logging.debug(f"(QPUEntity | {name}) Logging check in __init__")
        super().__init__()
        self.name = name
        self.processor = self.__create_processor(name, qbit_count, depolar_rate)
        self.__correction = correction
        self.__queue = deque()
        self.__measuring = False
        self.__setup_callbacks()

    # ======== PRIVATE METHODS ========
    # Helper function to create a simple QPU with a few useful instructions
    def __create_processor(self, name, qbit_count, depolar_rate):
        """Initialize the quantum processor for this QPU."""
        physical_instructions = [
            ns.components.qprocessor.PhysicalInstruction(ns.components.instructions.INSTR_INIT, duration=3, parallel=True),
            ns.components.qprocessor.PhysicalInstruction(ns.components.instructions.INSTR_H, duration=1, parallel=True),
            ns.components.qprocessor.PhysicalInstruction(ns.components.instructions.INSTR_X, duration=1, parallel=True),
            ns.components.qprocessor.PhysicalInstruction(ns.components.instructions.INSTR_Y, duration=1, parallel=True),
            ns.components.qprocessor.PhysicalInstruction(ns.components.instructions.INSTR_Z, duration=1, parallel=True),
            ns.components.qprocessor.PhysicalInstruction(ns.components.instructions.INSTR_CNOT, duration=4, parallel=True, topology=[(0, 1)]),
            ns.components.qprocessor.PhysicalInstruction(ns.components.instructions.INSTR_EMIT, duration=1, parallel=True),
            ns.components.qprocessor.PhysicalInstruction(ns.components.instructions.INSTR_MEASURE, duration=7, parallel=False)
        ]
        memory_noise_model = ns.components.models.DepolarNoiseModel(depolar_rate=depolar_rate)
        processor = QuantumProcessor(name, num_positions=qbit_count,
                                     memory_noise_models=[memory_noise_model] * qbit_count,
                                     phys_instructions=physical_instructions)
        processor.add_ports(['correction'])
        return processor

    # Helper for setting up the callbacks and handlers
    def __setup_callbacks(self):
        """Set up callback handling for when programs complete."""
        self.processor.set_program_done_callback(self.__on_program_done, once=False)
        self.processor.set_program_fail_callback(self.__on_program_fail, once=False)
        self.processor.ports['qin0'].bind_input_handler(self.__recv_qubit)
        self.processor.ports['correction'].bind_input_handler(self.__correction_callback)

    # Callback for when a QPU program finishes executing successfully
    def __on_program_done(self):
        """Handle completion of a program, and process the next one if queued."""
        logging.debug(f"(QPUEntity | {self.name}) program complete")
        if len(self.__queue) > 0 and not self.processor.busy:
            if self.processor.peek(0, skip_noise=True)[0] is not None:
                next_program = self.__queue.popleft()
                logging.debug(f"(QPUEntity | {self.name}) queuing next program: {next_program}")
                self.add_program(next_program)
        else:
            logging.debug(f"(QPUEntity | {self.name}) Emitting qubit for fidelity measurement")
            self.start_fidelity_calculation()

    # Callback for when a QPU program exits with a failure
    def __on_program_fail(self):
        """Inform of program failure."""
        logging.debug(f"(QPUEntity | {self.name}) program resulted in failure")
        if len(self.__queue) > 0:
            next_program = self.__queue.popleft()
            logging.debug(f"(QPUEntity | {self.name}) queuing next program:", next_program)
            self.add_program(next_program)


    # On qubit receival (back from fidelity check) return it to QPU and unset busy flag
    def __recv_qubit(self, msg):
        logging.debug(f"(QPUEntity | {self.name}) Received qubit back, returning to QPU position 0")
        qubit = msg.items[0]
        self.processor.put(qubit, 0)
        self.__measuring = False # Unset the flag which blocks QPU ops

    # Callback function for applying qubit corrections based on BSMDetector output
    def __correction_callback(self, msg):
        logging.debug(f"(QPUEntity | {self.name}) received: {msg}")
        bell_idx = msg.items[0].bell_index

        if self.__correction == 'Y': logging.debug(f"(QPUEntity | {self.name}) Fidelities output: Bell Index: {bell_idx}")
        if bell_idx == 1 and self.__correction == 'Y':
            logging.debug(f"(QPUEntity | {self.name}) Performing X correction")
            self.add_program(CorrectXProgram())
        elif bell_idx == 2 and self.__correction == 'Y':
            logging.debug(f"(QPUEntity | {self.name}) Performing Y correction")
            self.add_program(CorrectYProgram())
        else:
            logging.debug(f"(QPUEntity | {self.name}) No correction needed")

    # ======== PUBLIC METHODS ========
    # Use this function to append programs to the object queue
    def add_program(self, program):
        """Add a program to the queue and execute if the processor is available."""
        logging.debug(f"(QPUEntity | {self.name}) Call to add_program with {program}")
        if not self.processor.busy:
            if not self.__measuring:
                logging.debug(f"(QPUEntity | {self.name}) executing program {program}")
                self.processor.execute_program(program)
            else:
                logging.debug(f"(QPUEntity | {self.name}) appending program to queue (measuring qubit fidelity)")
                self.__queue.append(program)
        else:
            logging.debug(f"(QPUEntity | {self.name}) appending program to queue (QPU busy)")
            self.__queue.append(program)

    # Emit qubit out the relevant port for fidelity calculation
    def start_fidelity_calculation(self):
        self.processor.pop(0, skip_noise=True, positional_qout=True)
        self.__measuring = True

    # Utility function to call when we want to emit a qubit (no need to import EmitProgram outside)
    def emit(self):
        self.add_program(EmitProgram())


class EmitProgram(QuantumProgram):
    """Program to create a qubit and emit an entangled photon to the 'qout' port.
    """
    def __init__(self):
        super().__init__(num_qubits=2)

    def program(self, **_):
        logging.debug("Entry point for the Emit program")
        # Emit from q2 using q1
        q1, q2 = self.get_qubit_indices(self.num_qubits)
        self.apply(instr.INSTR_INIT, q1)
        self.apply(instr.INSTR_EMIT, [q1, q2])
        yield self.run()

class CorrectYProgram(QuantumProgram):
    """Program to apply a Pauli Z correction to a shared Bell state
    """
    def __init__(self):
        super().__init__(num_qubits=1)

    def program(self, **_):
        logging.debug("Entry point for the Correct Z program")
        q1 = self.get_qubit_indices(self.num_qubits)
        self.apply(instr.INSTR_Y, q1)
        yield self.run()

class CorrectXProgram(QuantumProgram):
    """Program to apply a Pauli X correction to a shared Bell state
    """
    def __init__(self):
        super().__init__(num_qubits=1)

    def program(self, **_):
        logging.debug("Entry point for the Correct X program")
        q1 = self.get_qubit_indices(self.num_qubits)
        self.apply(instr.INSTR_X, q1)
        yield self.run()

