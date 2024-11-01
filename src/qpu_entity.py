# Imports section
import logging
import netsquid as ns

from collections import deque
from netsquid.components.qprogram import QuantumProgram
from netsquid.components.qprocessor import QuantumProcessor

import netsquid.components.instructions as instr
import netsquid.qubits.ketstates as ks
from netsquid.qubits import qubitapi as qapi

# ---- CLASSES ----
class QPUEntity(ns.pydynaa.Entity):
    """Represents a quantum processing unit (QPU) with program queue and callback functionality."""

    def __init__(self, name, correction, qbit_count=2, depolar_rate=0):
        logging.debug("(QPUEntity) Logging check in __init__")
        super().__init__()
        self.name = name
        self.correction = correction
        self.processor = self._create_processor(name, qbit_count, depolar_rate)
        self.queue = deque()
        self.measuring = False
        self._setup_callbacks()

    # Helper function to create a simple QPU with a few useful instructions
    def _create_processor(self, name, qbit_count, depolar_rate):
        """Initialize the quantum processor for this QPU."""
        physical_instructions = [
            ns.components.qprocessor.PhysicalInstruction(ns.components.instructions.INSTR_INIT, duration=3, parallel=True),
            ns.components.qprocessor.PhysicalInstruction(ns.components.instructions.INSTR_H, duration=1, parallel=True),
            ns.components.qprocessor.PhysicalInstruction(ns.components.instructions.INSTR_X, duration=1, parallel=True),
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
    def _setup_callbacks(self):
        """Set up callback handling for when programs complete."""
        self.processor.set_program_done_callback(self.on_program_done)
        self.processor.set_program_fail_callback(self.on_program_fail)
        self.processor.ports['correction'].bind_input_handler(self.correction_callback)

    # Use this function to append programs to the object queue
    def add_program(self, program):
        """Add a program to the queue and execute if the processor is available."""
        logging.info(f"(QPUEntity | {self.name}) Call to add_program")
        if not self.processor.busy:
            if not self.measuring:
                logging.info(f"(QPUEntity | {self.name}) executing program")
                self.processor.execute_program(program)
            else:
                logging.info(f"(QPUEntity | {self.name}) appending program to queue (measuring qubit fidelity)")
                self.queue.append(program)
        else:
            logging.info(f"(QPUEntity | {self.name}) appending program to queue (QPU busy)")
            self.queue.append(program)

    # TODO fix this, we need to emit a qubit out the relevant port for fidelity calculations
    def start_fidelity_calculation(self):
        self.processor.pop(0, skip_noise=True, positional_qout=True)
        self.measuring = True
        # TODO disable the flag when you get the qubit back
        pass

    # Callback function for applying qubit corrections based on BSMDetector output
    def correction_callback(self, msg):
        logging.debug(f"(QPUEntity | {self.name}) received: {msg}")
        status = msg.items[0]
        if status == 1 and self.correction == 'X':
            # TODO
            logging.debug(f"(QPUEntity | {self.name}) Performing X correction")
            pass
        elif status == 2 and self.correction == 'Z':
            # TODO perform Z correction
            logging.debug(f"(QPUEntity | {self.name}) Performing Z correction")
            pass
        else:
            logging.debug(f"(QPUEntity | {self.name}) No correction needed")

    # Callback for when a QPU program finishes executing successfully
    def on_program_done(self):
        """Handle completion of a program, and process the next one if queued."""
        logging.debug(f"(QPUEntity | {self.name}) program complete")
        if len(self.queue) > 0 and not self.processor.busy:
            if self.processor.peek(0, skip_noise=True)[0] is not None:
                next_program = self.queue.popleft()
                logging.debug(f"(QPUEntity | {self.name}) queuing next program:", next_program)
                self.add_program(next_program)
        else:
            logging.debug(f"(QPUEntity | {self.name}) Emitting qubit for fidelity measurement")
            self.start_fidelity_calculation()

    # Callback for when a QPU program exits with a failure
    def on_program_fail(self):
        """Inform of program failure."""
        logging.debug(f"(QPUEntity | {self.name}) program resulted in failure")
        if len(self.queue) > 0:
            next_program = self.queue.popleft()
            logging.debug(f"(QPUEntity | {self.name}) queuing next program:", next_program)
            self.add_program(next_program)

class EmitProgram(QuantumProgram):
    """Program to create a qubit and emit an entangled photon to the 'qout' port.
    """
    def __init__(self):
        super().__init__(num_qubits=2)

    def program(self, **_):
        logging.info("Entry point for the Emit program")
        # Emit from q2 using q1
        q1, q2 = self.get_qubit_indices(self.num_qubits)
        self.apply(instr.INSTR_INIT, q1)
        self.apply(instr.INSTR_EMIT, [q1, q2])
        yield self.run()

class CorrectZProgram(QuantumProgram):
    """Program to apply a Pauli Z correction to a shared Bell state
    """
    def __init__(self):
        super().__init__(num_qubits=1)

    def program(self, **_):
        logging.info("Entry point for the Correct Z program")
        # Emit from q2 using q1
        q1 = self.get_qubit_indices(self.num_qubits)
        self.apply(instr.INSTR_Z, q1)
        yield self.run()

class CorrectXProgram(QuantumProgram):
    """Program to apply a Pauli X correction to a shared Bell state
    """
    def __init__(self):
        super().__init__(num_qubits=1)

    def program(self, **_):
        logging.info("Entry point for the Correct X program")
        # Emit from q2 using q1
        q1 = self.get_qubit_indices(self.num_qubits)
        self.apply(instr.INSTR_X, q1)
        yield self.run()

