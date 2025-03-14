import logging
import netsquid.components.instructions as instr
from netsquid.components.qprogram import QuantumProgram


class EmitProgram(QuantumProgram):
    default_num_qubits = 2

    def program(self):
        logging.debug("Entry point for the Emit program")
        q1, q2 = self.get_qubit_indices(2)

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
