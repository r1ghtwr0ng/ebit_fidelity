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
        (q,) = self.get_qubit_indices(1)
        self.apply(instr.INSTR_X, q)
        yield self.run()


class YCorrection(QuantumProgram):
    default_num_qubits = 1

    def program(self):
        (q,) = self.get_qubit_indices(1)
        self.apply(instr.INSTR_Y, q)
        yield self.run()


class SwapProgram(QuantumProgram):
    default_num_qubits = 2

    def program(self):
        q1, q2 = self.get_qubit_indices(2)
        self.apply(instr.INSTR_SWAP, [q1, q2])
        yield self.run()


class EPLDistillationProgram(QuantumProgram):
    """
    Program to perform the local operations for EPL distillation.

    This program applies a CNOT gate with a designated control qubit and target qubit,
    then measures the target qubit. (For instance, for Alice, this matches the operation:

        q_control.cnot(q_target)
        m = q_target.measure()

    so that when called as:

        epl_prog = EPLDistillationProgram(control_index=2, target_index=1)

    the operation uses qubit 2 as control and qubit 1 as target.)

    Parameters:
      control_index : int
          The index of the qubit used as control (e.g. the memory qubit at index 1).
      target_index : int
          The index of the qubit used as target (e.g. the fresh entanglement qubit at index 2).
    """

    def __init__(self, control_idx, target_idx):
        # This program works on two qubits.
        super().__init__(num_qubits=2, qubit_mapping=[control_idx, target_idx])
        self.control_idx = control_idx
        self.target_idx = target_idx

    def program(self, **kwargs):
        logging.debug("Entry point for the EPL Distillation program")
        qubits = self.get_qubit_indices(self.num_qubits)
        control = qubits[self.control_idx]
        target = qubits[self.target_idx]
        # Apply CNOT from the control to the target
        self.apply(instr.INSTR_CNOT, [control, target])
        # Then measure the target qubit.
        self.apply(instr.INSTR_MEASURE, target)
        yield self.run()
