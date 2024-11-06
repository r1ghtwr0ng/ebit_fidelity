import pytest
import netsquid as ns
from src.qpu_entity import QPUEntity  # , EmitProgram, CorrectXProgram, CorrectYProgram
from netsquid.components.qprocessor import QuantumProcessor
from netsquid.components import Message
from netsquid.qubits.qubit import Qubit


@pytest.fixture
def qpu_entity():
    """Fixture to create a QPUEntity with minimal configuration for testing."""
    return QPUEntity(name="TestQPU", correction=True, qbit_count=2, depolar_rate=0)


def test_qpu_entity_initialization(qpu_entity):
    """Test that QPUEntity initializes with the correct attributes."""
    assert qpu_entity.name == "TestQPU"
    assert isinstance(
        qpu_entity.processor, QuantumProcessor
    ), "The QPUEntity.processor type not QuantumProcessor"
    assert qpu_entity._QPUEntity__correction is True
    assert qpu_entity.processor.num_positions == 2


def test_emit_output_port(qpu_entity):
    """Test that emit() triggers output on the qout port of QuantumProcessor."""
    # Reset the simulation timer to 0
    ns.sim_reset()

    # Run simulation with emission procedure
    qpu_entity.emit()
    ns.sim_run()

    # Collect output from the output port
    output_msg = qpu_entity.processor.ports["qout"].rx_output()
    assert isinstance(output_msg, Message), "The QPU entity does not emit a message"
    assert isinstance(output_msg.items[0], Qubit), "The emitted item is not a Qubit"


# Test Z correction (two QPUs, one set to correct, one not)
# Test X correction (two QPUs, one set to correct, one not)
# Test no correction (two QPUs, one set to correct, one not)

# Test queue scheduling
# Test fidelity emission (just verify qubits go out the correct port)
