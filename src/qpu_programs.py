import logging
import netsquid.components.instructions as instr
from netsquid.components.qprogram import QuantumProgram


class EmitProgram(QuantumProgram):
    """
    Program to initialize a qubit at a specified position and emit an entangled photon.

    Parameters
    ----------
    qubit1 : int
        The memory position of the qubit to initialize and entangle with a photon.
    qubit2 : int
        The memory position or virtual index of the qubit that represents the photon
        output.
    """

    def __init__(self, qubit1, qubit2):
        # Initialize with two program qubits, mapped to the specified indices
        super().__init__(num_qubits=2, qubit_mapping=[qubit1, qubit2])

    def program(self, **_):
        """
        Run the emit program, initializing `qubit1` and emitting a photon entangled with
        it.

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
        self.apply(instr.INSTR_EMIT, [q1, q2])  # TODO consider using only q1
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
        q1 = self.get_qubit_indices(self.num_qubits)[
            0
        ]  # TODO use self.position instead of hardcoded index
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


class SwapCommToMemoryProgram(QuantumProgram):
    """
    Program to swap the state from a source qubit (communication qubit)
    to a target qubit (memory qubit) using three CNOT gates.

    This is intended to leave the entangled Bell state in the target qubit.

    Parameters:
      source_index : int
          The index of the qubit that currently holds the state (e.g. 0).
      target_index : int
          The index of the qubit to which the state is to be swapped (e.g. 1).
    """

    def __init__(self, source_index, target_index):
        # We use two qubits in this program.
        super().__init__(num_qubits=2)
        self.source_index = source_index
        self.target_index = target_index

    def program(self, **kwargs):
        logging.debug("Entry point for the SWAP program")
        qubits = self.get_qubit_indices(self.num_qubits)
        src = qubits[self.source_index]
        tgt = qubits[self.target_index]

        # Apply SWAP
        self.apply(instr.INSTR_SWAP, [src, tgt])
        yield self.run()


class EPLDistillationProgram(QuantumProgram):
    """
    Program to perform the local operations for EPL distillation.

    This program applies a CNOT gate with a designated control qubit and target qubit,
    then measures the target qubit. (For instance, for Alice, this matches the operation:

        q_control.cnot(q_target)
        m = q_target.measure()

    so that when called as:

        epl_prog = EPLDistillationProgram(control_index=1, target_index=0)

    the operation uses qubit 1 as control and qubit 0 as target.)

    Parameters:
      control_index : int
          The index of the qubit used as control (e.g. the memory qubit at index 1).
      target_index : int
          The index of the qubit used as target (e.g. the fresh entanglement qubit at index 0).
    """

    def __init__(self, control_index, target_index):
        # This program works on two qubits.
        super().__init__(num_qubits=2)
        self.control_index = control_index
        self.target_index = target_index

    def program(self, **kwargs):
        logging.debug("Entry point for the EPL Distillation program")
        qubits = self.get_qubit_indices(self.num_qubits)
        control = qubits[self.control_index]
        target = qubits[self.target_index]
        # Apply CNOT from the control to the target
        self.apply(instr.INSTR_CNOT, [control, target])
        # Then measure the target qubit.
        self.apply(instr.INSTR_MEASURE, target)
        yield self.run()
