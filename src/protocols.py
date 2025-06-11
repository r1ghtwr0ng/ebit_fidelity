import logging
import pandas as pd
import netsquid as ns

from utils import flush_port
from data_collection import collect_fidelity_data
from netsquid.protocols import NodeProtocol, Protocol, Signals
from qpu_programs import (
    EmitProgram,
    XCorrection,
    YCorrection,
    SwapProgram,
    EPLDistillationProgram,
)


class EntanglementProtocol(NodeProtocol):
    def __init__(
        self, ctrl_node, source, target, timeout=1500, perform_correction=True
    ):
        super().__init__(source)
        # Entanglement source (node which runs protocol) and target
        self.source = source
        self.target = target
        self.ctrl_node = ctrl_node
        self.timeout = timeout
        self.perform_correction = perform_correction
        self.protocol_log = "EBIT_CORRECT" if perform_correction else "EBIT_PASSIVE"

    def run(self):
        # Local vars
        node_name = self.source.name
        node_proc = self.source.processor
        emit_idx = self.source.emit_idx
        comm_idx = self.source.comm_idx

        # Flush any stale messages on the corrections port
        logging.debug(f"[{self.protocol_log}] {node_name}: Flushing corrections port.")
        flush_port(self.source.ports["corrections"])

        # Execute the emit program
        emit_photon = EmitProgram()
        node_proc.execute_program(emit_photon, qubit_mapping=[comm_idx, emit_idx])

        # Prepare to wait for the emit program to finish AND a port input, OR a timeout
        emit_done = self.await_program(node_proc)
        port_event = self.await_port_input(self.source.ports["corrections"])
        timeout_event = self.await_timer(self.timeout)
        compound_expr = emit_done & (port_event | timeout_event)
        ent_expr = yield compound_expr

        # Check if a timeout occurred.
        if ent_expr.second_term.second_term.value:
            logging.info(
                f"[{self.protocol_log}] {node_name} ebit establishment timeout."
            )
            return {"log": "timeout", "success": False}

        # Process the Bell state from the received message
        msg = self.source.ports["corrections"].rx_input()
        if msg is None:
            logging.info(f"[{self.protocol_log}] {node_name} missing message")
            return {"log": "no_msg", "success": False}

        bell_state = msg.items[0].bell_index

        if bell_state == -1:
            logging.info(f"[{self.protocol_log}] {node_name} invalid entanglement")
            result = {"log": "no entanglement", "success": False}
        elif bell_state == 1:
            logging.info(f"[{self.protocol_log}] {node_name} processing Bell state 1")
            if self.perform_correction:
                x_prog = XCorrection()
                node_proc.execute_program(x_prog, qubit_mapping=[comm_idx])
                yield self.await_program(node_proc)
            result = {"log": "corrected", "success": True}
        elif bell_state == 2:
            logging.info(f"[{self.protocol_log}] {node_name} processing Bell state 2")
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
        ctrl_node,
        qnode_1,
        qnode_2,
        fsoswitch,
        routing_table,
        max_attempts=10,
        timeout=1500,
    ):
        super().__init__()
        self.fsoswitch_node = fsoswitch
        self.routing_table = routing_table
        self.max_attempts = max_attempts
        self.timeout = timeout
        self.attempts = 0

        # Save nodes TODO remove when CTRL node switching is fixed
        self.qnode_1 = qnode_1
        self.qnode_2 = qnode_2

        # Create a single instance of the EntanglementProtocol
        self.subprotocol_qnode_1 = EntanglementProtocol(
            ctrl_node=ctrl_node,
            source=qnode_1,
            target=qnode_2,
            timeout=timeout,
            perform_correction=True,
        )
        self.subprotocol_qnode_2 = EntanglementProtocol(
            ctrl_node=ctrl_node,
            source=qnode_2,
            target=qnode_1,
            timeout=timeout,
            perform_correction=False,
        )

        # Add the subprotocols
        self.add_subprotocol(
            self.subprotocol_qnode_1, name="qnode_1_entanglement_protocol"
        )
        self.add_subprotocol(
            self.subprotocol_qnode_2, name="qnode_2_entanglement_protocol"
        )

        # TODO add connections from qnode_1 to FSO and from qnode_2 to FSO

    def run(self):
        for attempt in range(self.max_attempts):
            # Register and log the attempt count
            logging.info(f"[RETRYPROTO] Attempt {attempt + 1}")

            # Run the subprotocols and process the results.
            self.subprotocol_qnode_1.reset()
            self.subprotocol_qnode_2.reset()
            self.start_subprotocols()

            # Wait for finish signals from both subprotocols
            yield self.await_signal(
                self.subprotocol_qnode_1, signal_label=Signals.FINISHED
            ) & self.await_signal(
                self.subprotocol_qnode_2, signal_label=Signals.FINISHED
            )

            # Retrieve results from subprotocols
            qnode_1_result = self.subprotocol_qnode_1.get_signal_result(
                Signals.FINISHED
            )
            qnode_2_result = self.subprotocol_qnode_2.get_signal_result(
                Signals.FINISHED
            )

            logging.info(
                f"[RETRYPROTO] Done | qnode_1: {qnode_1_result['log']} | qnode_2: {qnode_2_result['log']}"
            )

            # Verify protocol response status
            if qnode_1_result["success"] and qnode_2_result["success"]:
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
        ctrl_node,
        qnode_1,
        qnode_2,
        fsoswitch,
        routing_table,
        max_attempts=10,
        timeout=1500,
        max_distillations=3,
    ):
        super().__init__()
        self.ctrl_node = ctrl_node
        self.qnode_1 = qnode_1
        self.qnode_2 = qnode_2
        self.fsoswitch = fsoswitch
        self.routing_table = routing_table
        self.max_attempts = max_attempts
        self.timeout = timeout
        self.max_distillations = max_distillations
        self.attempts = 0
        self.success = False

        # Initialize subprotocols
        self._setup_subprotocols()

    def _setup_subprotocols(self):
        """Set up the entanglement subprotocols for qnode_1 and qnode_2."""
        self.subprotocol_qnode_1 = EntanglementProtocol(
            ctrl_node=self.ctrl_node,
            source=self.qnode_1,
            target=self.qnode_2,
            timeout=self.timeout,
            perform_correction=True,
        )
        self.subprotocol_qnode_2 = EntanglementProtocol(
            ctrl_node=self.ctrl_node,
            source=self.qnode_2,
            target=self.qnode_1,
            timeout=self.timeout,
            perform_correction=False,
        )
        self.add_subprotocol(
            self.subprotocol_qnode_1, name="qnode_1_entanglement_protocol"
        )
        self.add_subprotocol(
            self.subprotocol_qnode_2, name="qnode_2_entanglement_protocol"
        )

    def run(self):
        """Main protocol execution logic."""
        logging.info("[ContinuousDistillation] Running protocol.")

        # Storage for metrics collection
        metrics_list = []

        # Perform initial entanglement
        init_success = yield from self._establish_entanglement(
            metrics_list, phase="initial"
        )
        if not init_success:
            return False, pd.DataFrame(metrics_list)

        # Swap qubits
        yield from self._swap_qubits()

        # Perform distillation iterations
        for i in range(self.max_distillations):
            # Establish entanglement for this iteration
            iteration_success = yield from self._establish_entanglement(
                metrics_list, phase=f"distillation_{i + 1}"
            )
            if not iteration_success:
                return False, pd.DataFrame(metrics_list)

            # Perform distillation
            distillation_success = yield from self._perform_distillation(i)
            if not distillation_success:
                # TODO
                return False, pd.DataFrame(metrics_list)

        # All steps completed successfully
        self.success = True
        return True, pd.DataFrame(metrics_list)

    def _establish_entanglement(self, metrics_list, phase):
        """Establish entanglement between qnode_1 and qnode_2.

        Args:
            metrics_list: List to store collected metrics
            phase: String identifying the protocol phase

        Returns:
            bool: True if entanglement was successfully established
        """
        phase_desc = (
            "initial" if phase == "initial" else f"iteration {phase.split('_')[1]}"
        )
        logging.info(f"[ContinuousDistillation] {phase} entanglement establishment.")

        for attempt in range(self.max_attempts):
            logging.info(
                f"[ContinuousDistillation] {phase_desc} entanglement attempt {attempt + 1}"
            )
            # Track attempts
            self.attempts += 1

            # Reset and start subprotocols
            self.subprotocol_qnode_1.reset()
            self.subprotocol_qnode_2.reset()

            # Create request UUID and request route from control node
            request_uuid = self.ctrl_node.request_route(
                self.qnode_1.name, self.qnode_2.name
            )
            if request_uuid is None:
                logging.error(f"[ContinuousDistillation] CTRL node NACKs route request")
                return False

            # Set request UUIDs for both nodes and run entanglement protocol
            self.qnode_1.set_emit_uuid(request_uuid)
            self.qnode_2.set_emit_uuid(request_uuid)
            self.start_subprotocols()

            # Wait for subprotocols to finish
            subprotocols_done = self.await_signal(
                self.subprotocol_qnode_1, signal_label=Signals.FINISHED
            ) & self.await_signal(
                self.subprotocol_qnode_2, signal_label=Signals.FINISHED
            )
            yield subprotocols_done

            # Collect metrics
            data_point = collect_fidelity_data(subprotocols_done)
            data_point["qnode_1"] = self.qnode_1.name
            data_point["qnode_2"] = self.qnode_2.name
            data_point["phase"] = phase
            data_point["attempt"] = attempt + 1
            data_point["total_attempts"] = self.attempts
            data_point["time"] = ns.sim_time()
            metrics_list.append(data_point)

            # Get results
            qnode_1_result = self.subprotocol_qnode_1.get_signal_result(
                Signals.FINISHED
            )
            qnode_2_result = self.subprotocol_qnode_2.get_signal_result(
                Signals.FINISHED
            )

            logging.info(
                f"[ContinuousDistillation] {phase_desc}, attempt {attempt + 1}: "
                f"qnode_1: {qnode_1_result['log']} | qnode_2: {qnode_2_result['log']}"
            )

            # Check success
            if qnode_1_result["success"] and qnode_2_result["success"]:
                return True

            logging.debug(
                f"[ContinuousDistillation] {phase_desc} entanglement failed, retrying."
            )

        logging.debug(
            f"[ContinuousDistillation] {phase_desc} entanglement failed after maximum attempts."
        )
        return False

    def _swap_qubits(self):
        """Perform qubit swap operation on both nodes."""
        logging.info(
            "[ContinuousDistillation] Swapping qubits (positions 1->2) on both nodes."
        )

        # Create and execute swap programs
        qnode_1_swap_prog = SwapProgram()
        qnode_2_swap_prog = SwapProgram()

        self.qnode_1.processor.execute_program(qnode_1_swap_prog, qubit_mapping=[1, 2])
        self.qnode_2.processor.execute_program(qnode_2_swap_prog, qubit_mapping=[1, 2])

        # Wait for programs to complete
        yield self.await_program(self.qnode_1.processor) & self.await_program(
            self.qnode_2.processor
        )

        logging.info("[ContinuousDistillation] Swap operations completed.")

    def _perform_distillation(self, iteration):
        """Perform EPL distillation for the given iteration.

        Args:
            iteration: Current distillation iteration (0-indexed)

        Returns:
            bool: True if distillation was successful
        """
        iteration_num = iteration + 1
        logging.info(
            f"[ContinuousDistillation] Running distillation at iteration {iteration_num}"
        )

        # Create and execute distillation programs
        qnode_1_distill = EPLDistillationProgram()
        qnode_2_distill = EPLDistillationProgram()

        self.qnode_1.processor.execute_program(qnode_1_distill, qubit_mapping=[1, 2])
        self.qnode_2.processor.execute_program(qnode_2_distill, qubit_mapping=[1, 2])

        # Wait for programs to complete
        yield self.await_program(self.qnode_1.processor) & self.await_program(
            self.qnode_2.processor
        )

        # Check measurement outcomes
        qnode_1_meas = qnode_1_distill.output["m_target"][0]
        qnode_2_meas = qnode_2_distill.output["m_target"][0]

        logging.info(
            f"[ContinuousDistillation] Iteration {iteration_num} results - "
            f"qnode_1: {qnode_1_meas}, qnode_2: {qnode_2_meas}"
        )

        # Success condition: both outcomes equal 1
        if (qnode_1_meas, qnode_2_meas) != (1, 1):
            # TODO fix failed distillation terminating protocol
            logging.debug(
                f"[ContinuousDistillation] Distillation iteration {iteration_num} failed, terminating"
            )
            return False

        logging.info(
            f"[ContinuousDistillation] Distillation iteration {iteration_num} succeeded."
        )
        return True
