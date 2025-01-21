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
        alice,
        bob,
        fsoswitch,
        routing_table,
        max_attempts=10,
        timeout=100,
    ):
        super().__init__()
        self.alice_node = alice
        self.bob_node = bob
        self.fsoswitch_node = fsoswitch
        self.routing_table = routing_table
        self.max_attempts = max_attempts
        self.timeout = timeout
        self.success = False
        self.results = None  # Store results here

        # Create a single instance of the EntanglementProtocol
        self.subprotocol_alice = EntanglementProtocol(alice, timeout=timeout)
        self.subprotocol_bob = EntanglementProtocol(bob, timeout=timeout)

        # Add the subprotocols
        self.add_subprotocol(self.subprotocol_alice, name="alice_entanglement_protocol")
        self.add_subprotocol(self.subprotocol_bob, name="bob_entanglement_protocol")

    def run(self):
        # Set the FSO switch path configuration
        # TODO use a switch scheduler here
        self.fsoswitch_node.switch(self.routing_table)

        for attempt in range(self.max_attempts):
            logging.info(f"[RETRYPROTO] Attempt {attempt + 1}.")
            yield from self.__single_run()

            # Retrieve results from subprotocols
            alice_result = self.subprotocol_alice.get_signal_result(Signals.SUCCESS)
            bob_result = self.subprotocol_bob.get_signal_result(Signals.SUCCESS)
            logging.info(
                f"[RETRYPROTO] Subprotocol results - Alice: {alice_result}, Bob: {bob_result}"
            )

            if alice_result and bob_result:
                self._on_success(alice_result, bob_result)
                return True
            else:
                self._on_failure(attempt)

        # Final failure after all attempts
        self._on_final_failure()
        return False

    def __single_run(self):
        """Execute a single run of the entanglement protocol."""
        self._reset_subprotocols()
        self.start_subprotocols()

        # Wait for signals from both subprotocols
        combined_event = self._create_combined_event()
        result = yield combined_event

        # Log the triggered events
        self._log_signals_received(result)
        return result

    # ---- Helper methods for signaling and logging entanglement attempt status ----
    def _reset_subprotocols(self):
        """Reset Alice and Bob subprotocols for a clean start."""
        self.subprotocol_alice.reset()
        self.subprotocol_bob.reset()

    def _create_combined_event(self):
        """Create a combined event expression to await signals from both subprotocols."""
        alice_event = self.await_signal(
            self.subprotocol_alice, signal_label=Signals.FINISHED
        )
        bob_event = self.await_signal(
            self.subprotocol_bob, signal_label=Signals.FINISHED
        )
        return alice_event & bob_event

    def _log_signals_received(self, result):
        """Log the result after signals are triggered."""
        logging.debug(
            f"[RETRYPROTO] Signals received: {type(result)} | Triggered Events: {result.triggered_events}"
        )

    def _on_success(self, alice_result, bob_result):
        """Handle successful entanglement."""
        logging.info("[RETRYPROTO] Retry protocol succeeded.")
        logging.info("[RETRYPROTO] Entanglement established successfully.")
        self.results = (alice_result, bob_result)
        self.success = True
        self.send_signal(Signals.SUCCESS, result=self.results)

    def _on_failure(self, attempt):
        """Log and store failure results."""
        alice_fail = self.subprotocol_alice.get_signal_result(Signals.FAIL)
        bob_fail = self.subprotocol_bob.get_signal_result(Signals.FAIL)
        logging.warning(
            f"[RETRYPROTO] EntanglementProtocol attempt {attempt + 1} failed. "
            f"Alice: {alice_fail}, Bob: {bob_fail}"
        )
        self.results = (alice_fail, bob_fail)

    def _on_final_failure(self):
        """Handle failure after all attempts."""
        logging.error(
            "[RETRYPROTO] Failed to establish entanglement after maximum attempts."
        )
        self.send_signal(Signals.FAIL, result=self.results)


class EntanglementProtocol(NodeProtocol):
    """
    Protocol for entanglement establishment.
    Emits qubits, waits for a correction event or timeout.
    """

    def __init__(self, node, timeout=100):
        super().__init__(node)  # Main protocol tied to Alice
        self.node = node
        self.timeout = timeout
        self.results = None

    def run(self):
        """Main protocol logic."""
        node_name = self.node.name
        logging.info(f"[EBIT_SUBPROTOCOL] {node_name} STARTED")

        self._emit_qubits()
        triggered_expression = yield self._await_response_or_timeout()

        self._process_triggered_expression(triggered_expression)
        self._send_final_signal()

    # ---- Helper methods ----
    def _emit_qubits(self):
        """Emit qubits from the node."""
        self.node.emit()

    def _await_response_or_timeout(self):
        """Create and yield a composite event expression for correction or timeout."""
        correction_event = pydynaa.EventExpression(
            source=self.node, event_type=QPUNode.correction_done_evtype
        )
        timeout_event = self.await_timer(self.timeout)
        return correction_event | timeout_event

    def _process_triggered_expression(self, triggered_expression):
        """Process the result of the triggered event expression."""
        node_name = self.node.name
        correction_triggered = triggered_expression.first_term.value
        timeout_triggered = triggered_expression.second_term.value

        logging.debug(
            f"[EBIT_SUBPROTOCOL] Status: Correction: {correction_triggered}, Timeout: {timeout_triggered}"
        )

        if correction_triggered:
            self.results = self._handle_correction()
        elif timeout_triggered:
            self.results = self._handle_timeout(node_name)

    def _handle_correction(self):
        """Handle the case where the correction event is triggered."""
        status = self.node.get_status()
        logging.info(
            f"[EBIT_SUBPROTOCOL] ({self.node.name}) Returned ebit establishment status: {status}"
        )
        return status

    def _handle_timeout(self, node_name):
        """Handle the case where a timeout occurs."""
        logging.warning(
            f"[EBIT_SUBPROTOCOL] ({node_name}) Timeout occurred in ebit establishment."
        )
        return "Timeout"

    def _send_final_signal(self):
        """Send the final signal based on results."""
        if self.results == "Timeout" or not self.results:
            self.send_signal(Signals.FAIL, result=self.results)
        else:
            self.send_signal(Signals.SUCCESS, result=self.results)
        logging.debug(f"[EBIT_SUBPROTOCOL] ({self.node.name}) Results: {self.results}")
