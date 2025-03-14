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

    def __init__(self, comm_idx=1, emit_idx=0):
        # Initialize with two program qubits, mapped to the specified indices
        super().__init__(num_qubits=2, qubit_mapping=[comm_idx, emit_idx])

    def program(self, **kwargs):
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


class XCorrection(QuantumProgram):
    default_num_qubits = 1

    def program(self):
        logging.debug("Entry point for X correct")
        (q,) = self.get_qubit_indices(1)
        self.apply(instr.INSTR_X, q)
        yield self.run()


class YCorrection(QuantumProgram):
    default_num_qubits = 1

    def program(self):
        logging.debug("Entry point for Y correct")
        (q,) = self.get_qubit_indices(1)
        self.apply(instr.INSTR_Y, q)
        yield self.run()


class SwapProgram(QuantumProgram):
    default_num_qubits = 2

    def program(self):
        logging.debug("Entry point for SWAP")
        q1, q2 = self.get_qubit_indices(2)
        self.apply(instr.INSTR_SWAP, [q1, q2])
        yield self.run()


class EPLDistillationProgram(QuantumProgram):
    default_num_qubits = 2

    def program(self):
        logging.debug("Entry point for EPLDistillation")
        target, control = self.get_qubit_indices(2)
        # Apply CNOT and measure the target
        self.apply(instr.INSTR_CNOT, [control, target])
        self.apply(instr.INSTR_MEASURE, target, output_key="m_target")
        yield self.run()
