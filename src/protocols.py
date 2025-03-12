import logging
import netsquid.components.instructions as instr

from netsquid.protocols import NodeProtocol, Protocol, Signals
from qpu_programs import EmitProgram, XCorrection, YCorrection


class EntanglementProtocol(NodeProtocol):
    def __init__(self, node, timeout=100, perform_correction=True):
        super().__init__(node)
        self.node = node
        self.timeout = timeout
        self.perform_correction = perform_correction
        self.protocol_log = (
            "{self.protocol_log}" if perform_correction else "EBIT_PASSIVE"
        )

    def run(self):
        node_name = self.node.name
        node_proc = self.node.processor
        emit_idx = self.node.emit_idx
        comm_idx = self.node.comm_idx

        # Emit a qubit and wait for execution.
        emit_photon = EmitProgram(comm_idx=comm_idx, emit_idx=emit_idx)
        node_proc.execute_program(emit_photon)
        yield self.await_program(node_proc)

        # Await port input (switch response) or timeout.
        switch_expr = self.await_port_input(self.node.ports["corrections"])
        timeout_expr = self.await_timer(self.timeout)
        ent_expr = yield switch_expr | timeout_expr

        if ent_expr.second_term.value:
            logging.info(
                f"[{self.protocol_log}] {node_name} ebit establishment timeout"
            )
            return {"log": "timeout", "success": False}

        bell_state = self.node.ports["corrections"].rx_input().items[0].bell_index

        match bell_state:
            case -1:
                logging.info(f"[{self.protocol_log}] {node_name} invalid entanglement")
                result = {"log": "no entanglement", "success": False}
            case 1:
                if self.perform_correction:
                    logging.info(
                        f"[{self.protocol_log}] {node_name} Performing X correction"
                    )
                    x_prog = XCorrection()
                    node_proc.execute_program(x_prog, qubit_mapping=[comm_idx])
                    yield self.await_program(node_proc)
                result = {"log": "corrected", "success": True}
            case 2:
                if self.perform_correction:
                    logging.info(
                        f"[{self.protocol_log}] {node_name} Performing Y correction"
                    )
                    y_prog = YCorrection()
                    node_proc.execute_program(y_prog, qubit_mapping=[comm_idx])
                    yield self.await_program(node_proc)
                result = {"log": "corrected", "success": True}
            case _:
                logging.error(
                    f"[{self.protocol_log}] {node_name} bad state: {bell_state}"
                )
                result = {"log": f"bad state: {bell_state}", "success": False}

        return result

        # SWAP communication qubit into shielded memory location
        # swap_prog = SwapProgram()
        # qpu.execute_program(swap_prog, qubit_mapping=[1, 2])
        # yield self.await_program(node_proc)  # Await instruction


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
