import logging
import netsquid.components.instructions as instr
from netsquid.components.qprogram import QuantumProgram


class EmitProgram(QuantumProgram):
    """
    Quantum program that initializes a qubit and emits an entangled photon.

    This program uses two qubits: one is initialized, and then an
    emit instruction is applied to create an emitted qubit pair.

    Notes
    -----
    - Uses `INSTR_INIT` on the first qubit.
    - Applies `INSTR_EMIT` on a pair of qubits.
    """

    def program(self):
        logger = logging.getLogger("qprog_logger")
        logger.debug("Entry point for the Emit program")
        q1, q2 = self.get_qubit_indices(2)

        # Initialize and emit using specified qubits
        self.apply(instr.INSTR_INIT, q1)
        self.apply(instr.INSTR_EMIT, [q1, q2])
        yield self.run()


class XCorrection(QuantumProgram):
    """
    Quantum program that applies an X (bit-flip) correction.

    Parameters
    ----------
    default_num_qubits : int, optional
        Number of qubits used by the program (default: 1).

    Notes
    -----
    - Single-qubit X gate applied to the selected qubit.
    """

    default_num_qubits = 1

    def program(self):
        logger = logging.getLogger("qprog_logger")
        logger.debug("Entry point for X correct")
        (q,) = self.get_qubit_indices(1)
        self.apply(instr.INSTR_X, q)
        yield self.run()


class YCorrection(QuantumProgram):
    """
    Quantum program that applies a Y (bit and phase-flip) correction.

    Parameters
    ----------
    default_num_qubits : int, optional
        Number of qubits used by the program (default: 1).

    Notes
    -----
    - Single-qubit Y gate applied to the selected qubit.
    """

    default_num_qubits = 1

    def program(self):
        logger = logging.getLogger("qprog_logger")
        logger.debug("Entry point for Y correct")
        (q,) = self.get_qubit_indices(1)
        self.apply(instr.INSTR_Y, q)
        yield self.run()


class SwapProgram(QuantumProgram):
    """
    Quantum program that performs a SWAP operation between two qubits.

    Parameters
    ----------
    default_num_qubits : int, optional
        Number of qubits used by the program (default: 2).

    Notes
    -----
    - Applies the `INSTR_SWAP` gate between the two allocated qubits.
    """

    default_num_qubits = 2

    def program(self):
        logger = logging.getLogger("qprog_logger")
        logger.debug("Entry point for SWAP")
        q1, q2 = self.get_qubit_indices(2)
        self.apply(instr.INSTR_SWAP, [q1, q2])
        yield self.run()


class EPLDistillationProgram(QuantumProgram):
    """
    Quantum program for entanglement purification using EPL.

    This program applies a CNOT gate between two qubits and measures
    the target qubit to determine whether the distillation step succeeds.

    Parameters
    ----------
    default_num_qubits : int, optional
        Number of qubits used by the program (default: 2).

    Notes
    -----
    - Control qubit acts as the source.
    - Target qubit is measured with result stored in `m_target`.
    """

    default_num_qubits = 2

    def program(self):
        logger = logging.getLogger("qprog_logger")
        logger.debug("Entry point for EPLDistillation")
        target, control = self.get_qubit_indices(2)
        # Apply CNOT and measure the target
        self.apply(instr.INSTR_CNOT, [control, target])
        self.apply(instr.INSTR_MEASURE, target, output_key="m_target")
        yield self.run()
