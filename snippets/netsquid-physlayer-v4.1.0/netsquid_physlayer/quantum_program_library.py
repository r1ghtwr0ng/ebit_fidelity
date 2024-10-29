################################################################################################################
# This library consists of functions that takes QuantumPrograms as inputs and applies gates to achieve a certain
# operation or circuit.
#
################################################################################################################

import numpy as np
from netsquid.components.instructions import (
    INSTR_CNOT,
    INSTR_ROT_Z,
    INSTR_ROT_X,
    INSTR_ROT_Y,
    INSTR_CXDIR,
)

__all__ = [
    'move_using_CNOTs',
    'move_using_CXDirections',
]


def move_using_CNOTs(q_program, control=0, target=1):
    r"""
    This schedules the correct operations in the provided QuantumProgram, using CNOTs
    to perform an effective 'move' operation. Assuming that the target qubit is in the \|0> state
    and the control qubit is in the state \|psi>, after the operation the state of the target
    will be \|psi> and the control will be \|0>.
    NOTE, will not perform an initialization of the target qubit before.

    Parameters
    ----------
    q_program : :class:`netsquid.components.qprogram.QuantumProgram`
    control : int
        The qubit ID of the control qubit in the program
    target : int
        The qubit ID of the target qubit in the program
    """
    # Do effective move operation
    q_program.apply(INSTR_CNOT, [control, target])
    q_program.apply(INSTR_CNOT, [target, control])


def move_using_CXDirections(q_program, control=0, target=1):
    r"""
    This schedules the correct operations in the provided QuantumProgram, using CXDirection, XRot, YRot and ZRot,
    to perform an effective 'move' operation. Assuming that the target qubit is in the \|0> state
    and the control qubit is in the state \|psi>, after the operation the state of the target
    will be H\|psi>, where H is the Hadamard operation, and the control will be \|0>.
    NOTE, will not perform an initialization of the target qubit before.

    The operations in here are taken from the paper: arXiv:1703.03244

    Parameters
    ----------
    q_program : :class:`netsquid.components.qprogram.QuantumProgram`
    control : int
        The qubit ID of the control qubit
    target : int
        The qubit ID of the target qubit
    """
    # Do effective CYDirection
    q_program.apply(INSTR_ROT_Z, target, angle=-np.pi / 2)
    q_program.apply(INSTR_CXDIR, [control, target], angle=np.pi / 2)
    q_program.apply(INSTR_ROT_Z, target, angle=np.pi / 2)
    # Do ROTX
    q_program.apply(INSTR_ROT_X, control, angle=np.pi / 2)
    # Do CXDirection
    q_program.apply(INSTR_CXDIR, [control, target], angle=np.pi / 2)
    # Do ROTY
    q_program.apply(INSTR_ROT_Y, control, angle=-np.pi / 2)
