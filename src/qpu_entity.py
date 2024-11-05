# Imports section
import logging
import netsquid as ns

from collections import deque
from netsquid.components.qprogram import QuantumProgram
from netsquid.components.qprocessor import QuantumProcessor

import netsquid.components.instructions as instr


class QPUEntity(ns.pydynaa.Entity):
    """
    Represents an entity (i.e. the legendary Alice and Bob) with a quantum processing unit (QPU) with a program queue and callback functionality.
    If a program needs to be executed it should be added to the queue using the add_program method.

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
        logging.debug(f"(QPUEntity | {name}) Logging check in __init__")
        super().__init__()
        self.name = name
        # The last qubit slot is used for photon emission into fibre
        self.__emission_idx = qbit_count - 1
        self.processor = self.__create_processor(name, qbit_count, depolar_rate)
        self.__correction = correction
        self.__queue = deque()
        self.__measuring = False
        self.__setup_callbacks()

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
        processor.add_ports(["correction"])
        return processor

    # Helper for setting up the callbacks and handlers
    def __setup_callbacks(self):
        """Set up callback handling for when programs complete."""
        self.processor.set_program_done_callback(self.__on_program_done, once=False)
        self.processor.set_program_fail_callback(self.__on_program_fail, once=False)
        self.processor.ports["qin0"].bind_input_handler(self.__recv_qubit)
        self.processor.ports["correction"].bind_input_handler(
            self.__correction_callback
        )

    # Callback for when a QPU program finishes executing successfully
    def __on_program_done(self):
        """Handle completion of a program, and process the next one if queued."""
        logging.debug(f"(QPUEntity | {self.name}) program complete")
        if len(self.__queue) > 0 and not self.processor.busy:
            if self.processor.peek(0, skip_noise=True)[0] is not None:
                next_program = self.__queue.popleft()
                logging.debug(
                    f"(QPUEntity | {self.name}) queuing next program: {next_program}"
                )
                self.add_program(next_program)
        else:
            logging.debug(
                f"(QPUEntity | {self.name}) Emitting qubit for fidelity measurement"
            )
            self.start_fidelity_calculation()

    # Callback for when a QPU program exits with a failure
    def __on_program_fail(self):
        """Inform of program failure."""
        logging.debug(f"(QPUEntity | {self.name}) program resulted in failure")
        if len(self.__queue) > 0:
            next_program = self.__queue.popleft()
            logging.debug(
                f"(QPUEntity | {self.name}) queuing next program:", next_program
            )
            self.add_program(next_program)

    # On qubit receival (back from fidelity check) return it to QPU and unset busy flag
    def __recv_qubit(self, msg):
        logging.debug(
            f"(QPUEntity | {self.name}) Received qubit back, returning to QPU position 0"
        )
        qubit = msg.items[0]
        self.processor.put(qubit, 0)
        self.__measuring = False  # Unset the flag which blocks QPU ops

    # Callback function for applying qubit corrections based on BSMDetector output
    def __correction_callback(self, msg):
        """
        Callback function, this runs whenever a Bell state measurement is received for the emitted photons.
        Used to apply qubit correction and get the ebit pair to the |00> + |11> Bell state.

        Parameters
        ----------
        msg : Message
            The message containing BSM results for corrections.
        """
        logging.debug(f"(QPUEntity | {self.name}) received: {msg}")
        bell_idx = msg.items[0].bell_index
        if self.__correction:
            logging.debug(
                f"(QPUEntity | {self.name}) Fidelities output: Bell Index: {bell_idx}"
            )
        if bell_idx == 1 and self.__correction:
            # This means the state is in state |01> + |10> and needs X correction to become |00> + |11>
            logging.debug(f"(QPUEntity | {self.name}) Performing X correction")
            self.add_program(CorrectXProgram())
        elif bell_idx == 2 and self.__correction:
            # This means the state is in state |01> - |10> and needs X correction to become |00> + |11>
            logging.debug(f"(QPUEntity | {self.name}) Performing Y correction")
            self.add_program(CorrectYProgram())
        else:
            logging.debug(f"(QPUEntity | {self.name}) No correction needed")

    # ======== PUBLIC METHODS ========
    # Use this function to append programs to the object queue
    def add_program(self, program):
        """
        Add a program to the queue and execute if the processor is available.

        Parameters
        ----------
        program : QuantumProgram
            The quantum program to be added to the QPU's queue.
        """
        logging.debug(f"(QPUEntity | {self.name}) Call to add_program with {program}")
        if not self.processor.busy:
            if not self.__measuring:
                logging.debug(f"(QPUEntity | {self.name}) executing program {program}")
                self.processor.execute_program(program)
            else:
                logging.debug(
                    f"(QPUEntity | {self.name}) appending program to queue (measuring qubit fidelity)"
                )
                self.__queue.append(program)
        else:
            logging.debug(
                f"(QPUEntity | {self.name}) appending program to queue (QPU busy)"
            )
            self.__queue.append(program)

    def start_fidelity_calculation(self, position=0):
        """
        Emit a qubit from memory for fidelity calculation.

        Parameters
        ----------
        position : int, optional
            The memory position of the qubit to emit, by default 0.
        """
        self.processor.pop(position, skip_noise=True, positional_qout=True)
        self.__measuring = True

    def emit(self, position=0):
        """
        Trigger the emission of a photon entangled with the memory qubit at the specified position.

        Parameters
        ----------
        position : int
            The memory position of the qubit to emit and entangle with a photon.
        """

        self.add_program(EmitProgram(position, self.__emission_idx))


class EmitProgram(QuantumProgram):
    """
    Program to initialize a qubit at a specified position and emit an entangled photon.

    Parameters
    ----------
    qubit1 : int
        The memory position of the qubit to initialize and entangle with a photon.
    qubit2 : int
        The memory position or virtual index of the qubit that represents the photon output.
    """

    def __init__(self, qubit1, qubit2):
        # Initialize with two program qubits, mapped to the specified indices
        super().__init__(num_qubits=2, qubit_mapping=[qubit1, qubit2])

    def program(self, **_):
        """
        Run the emit program, initializing `qubit1` and emitting a photon entangled with it.

        Uses
        ----
        INSTR_INIT : Initialize the qubit at `qubit1`.
        INSTR_EMIT : Emit a photon entangled with the qubit at `qubit1`.

        Yields
        ------
        Generator
            The program execution flow control.
        """
        logging.debug("Entry point for the Emit program")
        q1, q2 = self.get_qubit_indices(self.num_qubits)

        # Initialize and emit using specified qubits
        self.apply(instr.INSTR_INIT, q1)
        self.apply(instr.INSTR_EMIT, [q1, q2])
        yield self.run()


class CorrectYProgram(QuantumProgram):
    """
    Program to apply a Pauli Y correction to a specified qubit in a shared Bell state.

    Parameters
    ----------
    position : int
        The memory position of the qubit to apply the Pauli Y correction.
    """

    def __init__(self, position=0):
        super().__init__(num_qubits=1)
        self.position = position

    def program(self, **_):
        """
        Apply a Pauli Y correction to the qubit at the specified position.

        Uses
        ----
        INSTR_Y : Pauli Y correction on the qubit.

        Yields
        ------
        Generator
            The program execution flow control.
        """
        logging.debug("Entry point for the Correct Y program")
        q1 = self.get_qubit_indices(self.num_qubits)[0]
        self.apply(instr.INSTR_Y, q1)
        yield self.run()


class CorrectXProgram(QuantumProgram):
    """
    Program to apply a Pauli X correction to a specified qubit in a shared Bell state.

    Parameters
    ----------
    position : int
        The memory position of the qubit to apply the Pauli X correction.
    """

    def __init__(self, position=0):
        super().__init__(num_qubits=1)
        self.position = position

    def program(self, **_):
        """
        Apply a Pauli X correction to the qubit at the specified position.

        Uses
        ----
        INSTR_X : Pauli X correction on the qubit.

        Yields
        ------
        Generator
            The program execution flow control.
        """
        logging.debug("Entry point for the Correct X program")
        q1 = self.get_qubit_indices(self.num_qubits)[0]
        self.apply(instr.INSTR_X, q1)
        yield self.run()
