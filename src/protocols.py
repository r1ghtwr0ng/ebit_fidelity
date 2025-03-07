import logging
import pydynaa
from netsquid.protocols import NodeProtocol, Protocol, Signals

from qpu_node import QPUNode


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
        self.attempts = 0

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
            # Register and log the attempt count
            logging.info(f"[RETRYPROTO] Attempt {attempt + 1}.")
            self.attempts = attempt + 1

            # Run the subprotocols and process the results.
            # Yield the generator to the NetSquid scheduler.
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
        logging.debug(
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


class ContinuousEntanglementDistillationProto(NodeProtocol):
    """
    A protocol that first performs an initial entanglement generation (using
    EntanglementRetryProto) and swaps the communication qubits to memory. Then,
    it enters a loop where fresh entanglement is established and a distillation
    (purification) operation is performed. The loop continues until either a Bell pair
    is consumed (i.e. a distillation attempt fails) or a maximum number of distillations
    is reached.

    Assumptions:
      - QPUNode implements:
          * swap_comm_to_memory(): swaps the communication qubit to a memory qubit.
          * apply_epl_gates_and_measurement(): performs the local two-qubit gate (e.g. CNOT)
            and measurement needed for the EPL distillation.
          * update_memory_from_fresh(): updates the memory qubit with the distilled state
            when the distillation is successful.
    """

    def __init__(
        self,
        alice,
        bob,
        fsoswitch,
        routing_table,
        max_attempts=10,
        timeout=100,
        max_distillations=5,
    ):
        # Pass a node (here, alice) to properly connect this NodeProtocol.
        super().__init__(alice)
        self.alice_node = alice
        self.bob_node = bob
        self.fsoswitch_node = fsoswitch
        self.routing_table = routing_table
        self.max_attempts = max_attempts
        self.timeout = timeout
        self.max_distillations = max_distillations
        self.success = False
        self.distillations = 0

        # Create subprotocol instances.
        self.initial_entanglement = EntanglementRetryProto(
            alice, bob, fsoswitch, routing_table, max_attempts, timeout
        )
        self.fresh_entanglement = EntanglementRetryProto(
            alice, bob, fsoswitch, routing_table, max_attempts, timeout
        )

        # Add the subprotocols so they're fully connected.
        self.add_subprotocol(self.initial_entanglement, name="initial_entanglement")
        self.add_subprotocol(self.fresh_entanglement, name="fresh_entanglement")

    def run(self):
        # --- Initial Setup ---
        logging.info("[DISTILLATION] Starting initial entanglement establishment.")
        yield from self.initial_entanglement.run()
        if not self.initial_entanglement.success:
            logging.error("[DISTILLATION] Initial entanglement establishment failed.")
            self.send_signal(Signals.FAIL, result="Initial entanglement failed")
            return

        logging.info("[DISTILLATION] Swapping entangled qubits to memory.")
        self.alice_node.swap_comm_to_memory()
        self.bob_node.swap_comm_to_memory()

        # --- Distillation Loop ---
        distill_count = 0
        while distill_count < self.max_distillations:
            logging.info(
                f"[DISTILLATION] Starting distillation iteration {distill_count + 1}."
            )

            # Establish a fresh entanglement pair on the communication qubit.
            yield from self.fresh_entanglement.run()
            if not self.fresh_entanglement.success:
                logging.error(
                    "[DISTILLATION] Fresh entanglement generation failed. Stopping distillation."
                )
                self.send_signal(Signals.FAIL, result="Fresh entanglement failed")
                return

            # Apply local distillation operations on each node.
            a_measurement = self.alice_node.apply_epl_gates_and_measurement()
            b_measurement = self.bob_node.apply_epl_gates_and_measurement()
            logging.info(
                f"[DISTILLATION] Measurement outcomes: Alice={a_measurement}, Bob={b_measurement}"
            )

            # Check if the distillation round was successful.
            if (a_measurement, b_measurement) == (1, 1):
                logging.info(
                    "[DISTILLATION] Distillation round successful. Updating memory state."
                )
                # Update the memory qubit with the distilled state.
                self.alice_node.update_memory_from_fresh()
                self.bob_node.update_memory_from_fresh()
                distill_count += 1
                self.distillations += 1
            else:
                logging.warning(
                    "[DISTILLATION] Distillation round failed. Bell pair consumed."
                )
                self.send_signal(
                    Signals.FAIL, result="Distillation failed - Bell pair consumed"
                )
                return

        # If loop completes successfully:
        logging.info("[DISTILLATION] Continuous entanglement distillation succeeded.")
        self.success = True
        self.send_signal(Signals.SUCCESS, result="Continuous distillation succeeded")
