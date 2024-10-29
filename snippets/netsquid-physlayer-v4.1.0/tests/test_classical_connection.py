from netsquid_physlayer.classical_connection import ClassicalConnection, ClassicalConnectionWithLength
from netsquid.components.component import Message
import netsquid as ns


def check_delay_of_classical_connection(connection, delay):
    """Assert that messages on a classical connection take the right amount of time to traverse it."""
    ns.sim_reset()
    msgA = Message("A")
    msgB = Message("B")
    connection.ports["A"].tx_input(msgA)
    connection.ports["B"].tx_input(msgB)
    ns.sim_run()
    assert ns.sim_time() == delay
    assert connection.ports["A"].rx_output() == msgB
    assert connection.ports["B"].rx_output() == msgA


def test_classical_connection(delay=100):
    connection = ClassicalConnection(name="test_classical_connection", delay=delay)
    check_delay_of_classical_connection(connection=connection, delay=delay)


def test_classical_connection_with_length(length=1, c=1E9):
    delay = length / c * 1E9  # 1E9 converts seconds to nanoseconds
    connection = ClassicalConnectionWithLength(name="test_classical_connection_with_length", length=length, c=c)
    check_delay_of_classical_connection(connection=connection, delay=delay)
