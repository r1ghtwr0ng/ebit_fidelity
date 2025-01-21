import logging
import pydynaa
from netsquid.protocols import NodeProtocol, Protocol, Signals

from qpu_entity import QPUNode


class EntanglementRetryProto(Protocol):
    """
    A wrapper protocol that attempts to run the EntanglementProtocol until it succeeds
    or reaches the maximum number of attempts.
    """

    def __init__(
        self,
        alice_node,
        bob_node,
        fsoswitch_node,
        routing_table,
        max_attempts=10,
        timeout=3000,
    ):
        super().__init__()
        self.alice_node = alice_node
        self.bob_node = bob_node
        self.fsoswitch_node = fsoswitch_node
        self.routing_table = routing_table
        self.max_attempts = max_attempts
        self.timeout = timeout
        self.success = False
        self.results = None  # Store results here

        # Create a single instance of the EntanglementProtocol
        self.subprotocol_alice = EntanglementProtocol(alice_node, timeout=timeout)
        self.subprotocol_bob = EntanglementProtocol(bob_node, timeout=timeout)

        # Add the subprotocols
        self.add_subprotocol(self.subprotocol_alice, name="alice_entanglement_protocol")
        self.add_subprotocol(self.subprotocol_bob, name="bob_entanglement_protocol")

    def run(self):
        # Set the FSO switch path configuration
        self.fsoswitch_node.switch(self.routing_table)

        # Start attempting entanglement establishment
        for attempt in range(self.max_attempts):
            logging.info(f"[RETRYPROTO] Attempt {attempt + 1}.")
            self.__single_run()
            logging.info(
                f"FUCKING: {self.subprotocol_alice.get_signal_result(Signals.SUCCESS)}"
            )

            # Process subprotocol status codes
            if True:  # Early return if successful ebit establishment
                logging.info("Retry protocol succeeded.")
                self.results = self.subprotocol_alice.get_signal_result(Signals.SUCCESS)
                return True
            else:  # Continue
                logging.warning("EntanglementProtocol failed.")
                self.results = self.subprotocol_alice.get_signal_result(Signals.FAIL)

        # Send final signal based on success or failure
        if self.success:
            logging.info("Entanglement established successfully.")
            self.send_signal(Signals.SUCCESS, result=self.results)
        else:
            logging.error("Failed to establish entanglement after maximum attempts.")
            self.send_signal(Signals.FAIL, result=self.results)

    def __single_run(self):
        # Reset the subprotocols for a clean start
        self.subprotocol_alice.reset()
        self.subprotocol_bob.reset()

        # Wait for the subprotocols to complete (SUCCESS or FAIL)
        alice_evexpr = self.await_signal(
            self.subprotocol_alice, signal_label=Signals.SUCCESS
        ) | self.await_signal(self.subprotocol_alice, signal_label=Signals.FAIL)
        bob_evexpr = self.await_signal(
            self.subprotocol_bob, signal_label=Signals.SUCCESS
        ) | self.await_signal(self.subprotocol_bob, signal_label=Signals.FAIL)

        # Start subprotocols
        self.start_subprotocols()

        # Await for subprotocols
        result = alice_evexpr & bob_evexpr

        # Return the result of the signal
        result.wait()
        logging.debug(f"AAAAAAAAAA: {type(result)} | {result.value} | ")
        return result


class EntanglementProtocol(NodeProtocol):
    """
    Produces an emit event on a node, awaits correction event.
    """

    def __init__(self, node, timeout=100):
        super().__init__(node)  # Main protocol tied to Alice
        self.node = node
        self.timeout = timeout
        self.results = None

    def run(self):
        node_name = self.node.name
        logging.info(f"SUBPROTOCOL: {node_name} STARTED")

        # Emit qubits from the node
        self.node.emit()

        # Create event expression for correctionevent
        correction_event = pydynaa.EventExpression(
            source=self.node, event_type=QPUNode.correction_done_evtype
        )

        # Create a timeout event expression
        timeout_event = self.await_timer(self.timeout)

        # Composite event expression: wait for both Alice and Bob's responses or timeout
        expression = correction_event | timeout_event

        # Yield and wait for the event expression
        triggered_expression = yield expression

        logging.debug(
            f"BBBB {type(triggered_expression)} | {triggered_expression.value} | {triggered_expression.first_term.value} | {triggered_expression.second_term.value}"
        )

        # Check what triggered the expression
        if triggered_expression.first_term.value:  # Alice and Bob responses arrived
            logging.debug(f"Correction applied by: {node_name}.")
            status = self.node.get_status()
            logging.info(
                f"({self.node.name}) Returned ebit establishment status: {status}"
            )
            self.results = status
        elif triggered_expression.second_term.value:  # Timeout occurred
            logging.warning(f"({node_name}) Timeout occurred in ebit establishment.")
            self.results = "Timeout"

        # Signal the results
        if self.results == "Timeout" or not self.results:
            self.send_signal(Signals.FAIL, result=self.results)
        else:
            self.send_signal(Signals.SUCCESS, result=self.results)

        logging.debug(f"Protocol results: {self.results}")
