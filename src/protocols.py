import logging
import pydynaa
import netsquid as ns
from netsquid.protocols import NodeProtocol, Signals

from qpu_entity import QPUNode
from utils import get_fidelities


class EntanglementProtocol(NodeProtocol):
    """
    A protocol to manage entanglement generation between two QPU nodes via an FSO switch.
    """

    def __init__(
        self, alice_node, bob_node, fsoswitch_node, routing_table, timeout=3000
    ):
        super().__init__(alice_node)  # Main protocol tied to Alice
        self.alice_node = alice_node
        self.bob_node = bob_node
        self.fsoswitch_node = fsoswitch_node
        self.routing_table = routing_table
        self.timeout = timeout
        self.results = None

    def run(self):
        """Run the entanglement protocol."""
        # Configure the FSO switch
        self.fsoswitch_node.switch(self.routing_table)

        # Emit qubits from Alice and Bob
        self.alice_node.emit()
        self.bob_node.emit()

        # Create event expressions for Alice and Bob
        alice_event = pydynaa.EventExpression(
            source=self.alice_node, event_type=QPUNode.correction_done_evtype
        )
        bob_event = pydynaa.EventExpression(
            source=self.bob_node, event_type=QPUNode.correction_done_evtype
        )

        # Create a timeout event expression
        timeout_event = self.await_timer(self.timeout)

        # Composite event expression: wait for both Alice and Bob's responses or timeout
        expression = (alice_event & bob_event) | timeout_event

        # Yield and wait for the event expression
        triggered_expression = yield expression

        # Check what triggered the expression
        if triggered_expression.first_term.value:  # Alice and Bob responses arrived
            logging.debug("Both Alice and Bob responded.")
            status = self.alice_node.get_status()
            print(f"STATUS: {status}")
            self.results = status
        elif triggered_expression.second_term.value:  # Timeout occurred
            logging.warning("Timeout occurred before both responses were received.")
            self.results = "Timeout"

        # Signal the results
        if self.results == "Timeout" or not self.results:
            self.send_signal(Signals.FAIL, result=self.results)
        else:
            self.send_signal(Signals.SUCCESS, result=self.results)

        logging.debug(f"Protocol results: {self.results}")
