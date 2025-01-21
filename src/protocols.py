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

            # Await signals from both subprotocol_alice and subprotocol_bob
            yield from self.__single_run()

            # Check results from both subprotocols
            alice_result = self.subprotocol_alice.get_signal_result(Signals.SUCCESS)
            bob_result = self.subprotocol_bob.get_signal_result(Signals.SUCCESS)
            logging.info(
                f"[RETRYPROTO] Subprotocol response (Alice): {alice_result} (Bob): {bob_result}"
            )

            if alice_result and bob_result:
                logging.info("[RETRYPROTO] Retry protocol succeeded.")
                self.results = (alice_result, bob_result)  # Store results as a tuple
                return True
            else:
                alice_fail = self.subprotocol_alice.get_signal_result(Signals.FAIL)
                bob_fail = self.subprotocol_bob.get_signal_result(Signals.FAIL)
                logging.warning(
                    f"[RETRYPROTO] EntanglementProtocol failed. Alice: {alice_fail}, Bob: {bob_fail}"
                )
                self.results = (alice_fail, bob_fail)  # Store failure results

        # Send final signal based on success or failure
        if self.success:
            logging.info("[RETRYPROTO] Entanglement established successfully.")
            self.send_signal(Signals.SUCCESS, result=self.results)
        else:
            logging.error(
                "[RETRYPROTO] Failed to establish entanglement after maximum attempts."
            )
            self.send_signal(Signals.FAIL, result=self.results)

    def __single_run(self):
        # Reset the subprotocols for a clean start
        self.subprotocol_alice.reset()
        self.subprotocol_bob.reset()

        # Start subprotocols
        self.start_subprotocols()

        # Wait for the subprotocols to complete (SUCCESS or FAIL)
        alice_event = self.await_signal(
            self.subprotocol_alice, signal_label=Signals.FINISHED
        )
        bob_event = self.await_signal(
            self.subprotocol_bob, signal_label=Signals.FINISHED
        )
        combined_event = alice_event & bob_event

        result = yield combined_event  # Wait for both signals

        # Log and process the result after the signals are triggered
        logging.debug(
            f"[RETRYPROTO] Signals received: {type(result)} | Triggered Events: {result.triggered_events}"
        )
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
        logging.info(f"[EBIT_SUBPROTOCOL]: {node_name} STARTED")

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
            f"[EBIT_SUBPROTOCOL] Status: {triggered_expression.first_term.value} | Timeout: {triggered_expression.second_term.value}"
        )

        # Check what triggered the expression
        if triggered_expression.first_term.value:  # Alice and Bob responses arrived
            status = self.node.get_status()
            logging.info(
                f"[EBIT_SUBPROTOCOL] ({self.node.name}) Returned ebit establishment status: {status}"
            )
            self.results = status
        elif triggered_expression.second_term.value:  # Timeout occurred
            logging.warning(
                f"[EBIT_SUBPROTOCOL] ({node_name}) Timeout occurred in ebit establishment."
            )
            self.results = "Timeout"

        # Signal the results
        if self.results == "Timeout" or not self.results:
            self.send_signal(Signals.FAIL, result=self.results)
        else:
            self.send_signal(Signals.SUCCESS, result=self.results)

        logging.debug(f"[EBIT_SUBPROTOCOL] ({node_name}) Results: {self.results}")
