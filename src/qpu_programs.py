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
