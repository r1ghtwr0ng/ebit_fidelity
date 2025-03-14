import logging

from utils import flush_port
from netsquid.protocols import NodeProtocol, Protocol, Signals
from qpu_programs import (
    EmitProgram,
    XCorrection,
    YCorrection,
    SwapProgram,
    EPLDistillationProgram,
)


class EntanglementProtocol(NodeProtocol):
    def __init__(self, node, timeout=100, perform_correction=True):
        super().__init__(node)
        self.node = node
        self.timeout = timeout
        self.perform_correction = perform_correction
        self.protocol_log = "EBIT_CORRECT" if perform_correction else "EBIT_PASSIVE"

    def run(self):
        # Local vars
        node_name = self.node.name
        node_proc = self.node.processor
        emit_idx = self.node.emit_idx
        comm_idx = self.node.comm_idx

        # Flush any stale messages on the corrections port
        logging.debug(f"{node_name} - Flushing corrections port.")
        flush_port(self.node.ports["corrections"])

        # Execute the emit program
        emit_photon = EmitProgram(comm_idx=comm_idx, emit_idx=emit_idx)
        node_proc.execute_program(emit_photon)

        # Prepare to wait for the emit program to finish AND a port input, OR a timeout
        emit_done = self.await_program(node_proc)
        port_event = self.await_port_input(self.node.ports["corrections"])
        timeout_event = self.await_timer(self.timeout)
        compound_expr = (emit_done & port_event) | timeout_event
        ent_expr = yield compound_expr

        logging.debug(
            f"[{self.protocol_log}] {node_name} ======================= EXPR === PROG: {ent_expr.first_term.first_term.value} PORT: | {ent_expr.first_term.second_term.value} | TIMEOUT: {ent_expr.second_term.value} |||| {self.node.ports['corrections'].input_queue}"
        )
        # Check if a timeout occurred.
        if ent_expr.second_term.value:
            logging.info(
                f"[{self.protocol_log}] {node_name} ebit establishment timeout."
            )
            return {"log": "timeout", "success": False}

        # Process the Bell state from the received message
        msg = self.node.ports["corrections"].rx_input()
        if msg is None:
            logging.info(
                f"[{self.protocol_log}] {node_name} FUCKING MISSING MESSAGE ERROR WTFFFFFF."
            )
            return {"log": "no_msg", "success": False}

        bell_state = msg.items[0].bell_index

        if bell_state == -1:
            logging.info(f"[{self.protocol_log}] {node_name} invalid entanglement")
            result = {"log": "no entanglement", "success": False}
        elif bell_state == 1:
            logging.info(f"[{self.protocol_log}] {node_name} Processing Bell state 1")
            if self.perform_correction:
                x_prog = XCorrection()
                node_proc.execute_program(x_prog, qubit_mapping=[comm_idx])
                yield self.await_program(node_proc)
            result = {"log": "corrected", "success": True}
        elif bell_state == 2:
            logging.info(f"[{self.protocol_log}] {node_name} Processing Bell state 2")
            if self.perform_correction:
                y_prog = YCorrection()
                node_proc.execute_program(y_prog, qubit_mapping=[comm_idx])
                yield self.await_program(node_proc)
            result = {"log": "corrected", "success": True}
        else:
            logging.error(f"[{self.protocol_log}] {node_name} bad state: {bell_state}")
            result = {"log": f"bad state: {bell_state}", "success": False}

        return result


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
        timeout=200,
    ):
        super().__init__()
        self.fsoswitch_node = fsoswitch
        self.routing_table = routing_table
        self.max_attempts = max_attempts
        self.timeout = timeout
        self.attempts = 0
        self.success = False

        # Create a single instance of the EntanglementProtocol
        self.subprotocol_alice = EntanglementProtocol(
            alice, timeout=timeout, perform_correction=True
        )
        self.subprotocol_bob = EntanglementProtocol(
            bob, timeout=timeout, perform_correction=False
        )

        # Add the subprotocols
        self.add_subprotocol(self.subprotocol_alice, name="alice_entanglement_protocol")
        self.add_subprotocol(self.subprotocol_bob, name="bob_entanglement_protocol")

        # TODO add connections from Alice to FSO and from Bob to FSO

    def run(self):
        # Set the FSO switch path configuration
        # TODO use a switch scheduler here
        self.fsoswitch_node.switch(self.routing_table)

        for attempt in range(self.max_attempts):
            # Register and log the attempt count
            logging.info(f"[RETRYPROTO] Attempt {attempt + 1}.")

            # Run the subprotocols and process the results.
            self.subprotocol_alice.reset()
            self.subprotocol_bob.reset()
            self.start_subprotocols()

            # Wait for finish signals from both subprotocols
            yield self.await_signal(
                self.subprotocol_alice, signal_label=Signals.FINISHED
            ) & self.await_signal(self.subprotocol_bob, signal_label=Signals.FINISHED)

            # Retrieve results from subprotocols
            alice_result = self.subprotocol_alice.get_signal_result(Signals.FINISHED)
            bob_result = self.subprotocol_bob.get_signal_result(Signals.FINISHED)

            logging.info(
                f"[RETRYPROTO] Done | Alice: {alice_result['log']} | Bob: {bob_result['log']}"
            )

            # Verify protocol response status
            if alice_result["success"] and bob_result["success"]:
                self.success = True  # TODO remove once you know how to get results
                self.attempts = attempt + 1
                return True
            else:
                logging.debug("[RETRYPROTO] Failed, retrying")

        # If all attempts fail return False
        self.attempts = self.max_attempts
        return False


class ContinuousDistillationProtocol(Protocol):
    def __init__(
        self,
        alice,
        bob,
        fsoswitch,
        routing_table,
        max_attempts=10,
        timeout=100,
        max_distillation=3,
    ):
        super().__init__()
        self.alice = alice
        self.bob = bob
        self.fsoswitch = fsoswitch
        self.routing_table = routing_table
        self.max_attempts = max_attempts
        self.timeout = timeout
        self.max_distillation = max_distillation
        self.attempts = 0
        self.success = False

        self.subprotocol_alice = EntanglementProtocol(
            alice, timeout=timeout, perform_correction=True
        )
        self.subprotocol_bob = EntanglementProtocol(
            bob, timeout=timeout, perform_correction=False
        )
        self.add_subprotocol(self.subprotocol_alice, name="alice_entanglement_protocol")
        self.add_subprotocol(self.subprotocol_bob, name="bob_entanglement_protocol")

    def run(self):
        logging.info(
            "ContinuousDistillation: Running initial entanglement establishment."
        )
        self.fsoswitch.switch(self.routing_table)

        # --- Initial entanglement establishment ---
        init_success = False
        for attempt in range(self.max_attempts):
            logging.info(
                f"[ContinuousDistillation] Initial entanglement attempt {attempt + 1}"
            )
            self.subprotocol_alice.reset()
            self.subprotocol_bob.reset()
            self.start_subprotocols()

            yield (
                self.await_signal(self.subprotocol_alice, signal_label=Signals.FINISHED)
                & self.await_signal(self.subprotocol_bob, signal_label=Signals.FINISHED)
            )
            alice_result = self.subprotocol_alice.get_signal_result(Signals.FINISHED)
            bob_result = self.subprotocol_bob.get_signal_result(Signals.FINISHED)
            logging.info(
                f"[ContinuousDistillation] Attempt {attempt + 1}: Alice: {alice_result['log']} | Bob: {bob_result['log']}"
            )

            if alice_result["success"] and bob_result["success"]:
                init_success = True
                self.attempts += attempt + 1
                break
            else:
                logging.debug(
                    "[ContinuousDistillation] Initial entanglement failed, retrying."
                )

        if not init_success:
            logging.error(
                "ContinuousDistillation: Initial entanglement failed after maximum attempts."
            )
            return False

        # --- Swap qubits ---
        logging.info(
            "ContinuousDistillation: Swapping qubits (positions 1->2) on both nodes."
        )
        alice_swap_prog = SwapProgram()
        bob_swap_prog = SwapProgram()
        self.alice.processor.execute_program(alice_swap_prog, qubit_mapping=[1, 2])
        self.bob.processor.execute_program(bob_swap_prog, qubit_mapping=[1, 2])
        yield self.await_program(self.alice.processor) & self.await_program(
            self.bob.processor
        )

        # --- Distillation iterations ---
        for i in range(self.max_distillation):
            logging.info(f"ContinuousDistillation: Distillation iteration {i + 1}")
            # Reattempt entanglement for this iteration.
            iteration_success = False
            for attempt in range(self.max_attempts):
                logging.info(
                    f"[ContinuousDistillation] Iteration {i + 1} entanglement attempt {attempt + 1}"
                )
                self.subprotocol_alice.reset()
                self.subprotocol_bob.reset()
                self.start_subprotocols()

                yield (
                    self.await_signal(
                        self.subprotocol_alice, signal_label=Signals.FINISHED
                    )
                    & self.await_signal(
                        self.subprotocol_bob, signal_label=Signals.FINISHED
                    )
                )
                alice_result = self.subprotocol_alice.get_signal_result(
                    Signals.FINISHED
                )
                bob_result = self.subprotocol_bob.get_signal_result(Signals.FINISHED)
                logging.info(
                    f"[ContinuousDistillation] Iteration {i + 1}, attempt {attempt + 1}: Alice: {alice_result['log']} | Bob: {bob_result['log']}"
                )
                if alice_result["success"] and bob_result["success"]:
                    iteration_success = True
                    self.attempts += attempt + 1
                    break
                else:
                    logging.debug(
                        f"[ContinuousDistillation] Iteration {i + 1} entanglement failed, retrying."
                    )

            if not iteration_success:
                logging.error(
                    f"[ContinuousDistillation] Entanglement failed at iteration {i + 1}"
                )
                return False

            # Run the EPL distillation program after successful entanglement.
            logging.info(
                f"[ContinuousDistillation] Running distillation at iteration {i + 1}"
            )
            alice_distill = EPLDistillationProgram()
            bob_distill = EPLDistillationProgram()
            self.alice.processor.execute_program(alice_distill, qubit_mapping=[1, 2])
            self.bob.processor.execute_program(bob_distill, qubit_mapping=[1, 2])
            yield self.await_program(self.alice.processor) & self.await_program(
                self.bob.processor
            )

            # Retrieve measurement outcomes from the EPL distillation program.
            alice_meas = alice_distill.output["m_target"][0]
            bob_meas = bob_distill.output["m_target"][0]
            logging.info(
                f"[ContinuousDistillation] Iteration {i + 1} results - Alice: {alice_meas}, Bob: {bob_meas}"
            )
            # Check if the distillation was successful (success condition: both outcomes equal 1).
            if (alice_meas, bob_meas) != (1, 1):
                logging.error(
                    f"[ContinuousDistillation] Distillation iteration {i + 1} failed."
                )
                return False

        logging.info("[ContinuousDistillation] All distillation iterations succeeded")
        self.success = True
        return True


# class ContinuousDistillationProtocol(Protocol):
#    def __init__(
#        self,
#        alice,
#        bob,
#        fsoswitch,
#        routing_table,
#        max_attempts=10,
#        timeout=100,
#        max_distillation=3,
#    ):
#        super().__init__()
#        self.alice = alice
#        self.bob = bob
#        self.fsoswitch = fsoswitch
#        self.routing_table = routing_table
#        self.max_attempts = max_attempts
#        self.timeout = timeout
#        self.max_distillation = max_distillation
#        self.attempts = 0
#
#    def run(self):
#        logging.info(
#            "ContinuousDistillation: Running initial entanglement establishment."
#        )
#        retry_proto = EntanglementRetryProto(
#            self.alice,
#            self.bob,
#            self.fsoswitch,
#            self.routing_table,
#            max_attempts=self.max_attempts,
#            timeout=self.timeout,
#        )
#        retry_proto.start()
#        yield self.await_signal(retry_proto, signal_label=Signals.FINISHED)
#        init_result = retry_proto.get_signal_result(Signals.FINISHED)
#        if not init_result:
#            logging.error("ContinuousDistillation: Initial entanglement failed.")
#            return False
#
#        logging.info(
#            "ContinuousDistillation: Swapping qubits (positions 1->2) on both nodes."
#        )
#        swap_prog = SwapProgram()
#        self.alice.processor.execute_program(swap_prog, qubit_mapping=[1, 2])
#        yield self.await_program(self.alice.processor)
#        swap_prog = SwapProgram()
#        self.bob.processor.execute_program(swap_prog, qubit_mapping=[1, 2])
#        yield self.await_program(self.bob.processor)
#
#        for i in range(self.max_distillation):
#            logging.info(f"ContinuousDistillation: Distillation iteration {i + 1}.")
#            retry_proto = EntanglementRetryProto(
#                self.alice,
#                self.bob,
#                self.fsoswitch,
#                self.routing_table,
#                max_attempts=self.max_attempts,
#                timeout=self.timeout,
#            )
#            retry_proto.start()
#            yield self.await_signal(retry_proto, signal_label=Signals.FINISHED)
#            iter_result = retry_proto.get_signal_result(Signals.FINISHED)
#            if not iter_result:
#                logging.error(
#                    f"ContinuousDistillation: Entanglement failed at iteration {i + 1}."
#                )
#                return False
#
#            logging.info(
#                f"ContinuousDistillation: Running distillation at iteration {i + 1}."
#            )
#            alice_distill = EPLDistillationProgram()
#            bob_distill = EPLDistillationProgram()
#            self.alice.processor.execute_program(alice_distill, qubit_mapping=[1, 2])
#            self.bob.processor.execute_program(bob_distill, qubit_mapping=[1, 2])
#            yield self.await_program(self.alice.processor) & self.await_program(
#                self.bob.processor
#            )
#            # Retrieve measurement outcomes from the EPL distillation program.
#            alice_result = alice_distill.output["m_target"][0]
#            bob_result = bob_distill.output["m_target"][0]
#            logging.info(
#                f"ContinuousDistillation: Iteration {i + 1} results - Alice: {alice_result}, Bob: {bob_result}"
#            )
#            # Check if the distillation was successful (e.g. success condition: both outcomes equal 1)
#            if (alice_result, bob_result) != (1, 1):
#                logging.debug(
#                    f"ContinuousDistillation: Distillation iteration {i + 1} failed with results: {alice_result}, {bob_result}"
#                )
#                return False
#
#        logging.info("ContinuousDistillation: All distillation iterations succeeded.")
#        return True
