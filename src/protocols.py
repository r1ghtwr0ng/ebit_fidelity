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
    """
    Protocol for establishing entanglement between two quantum network nodes.

    This protocol runs on a `source` node and attempts to establish an entangled
    Bell pair with the `target` node. Optionally, it applies local correction
    operations based on the Bell state received from the control node.

    Parameters
    ----------
    source : netsquid.nodes.Node
        Node running the protocol and emitting photons.
    target : netsquid.nodes.Node
        Destination node intended for entanglement.
    ctrl_node : ControlNode
        Central control node managing entanglement routing and corrections.
    timeout : int
        Maximum waiting time (in simulation time units) before aborting.
    perform_correction : bool
        Whether to apply local Pauli corrections after entanglement.
    protocol_log : str
        Protocol identifier string for logging purposes.

    Examples
    --------
    >>> from simulation import setup_simple_network
    >>> _, ctrl_node, [qnode_1, qnode_2] = setup_simple_network(
    ...     dampening_parameter=0.1,
    ...     routing={"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"},
    ...     ideal_switch=False,
    ...     ideal_qpu=False,
    ...     visibility=0.9
    ... ) # Setup network
    >>> entanglement_protocol = EntanglementProtocol(
    ...     ctrl_node=ctrl_node,
    ...     source=qnode_1,
    ...     target=qnode_2,
    ...     timeout=400,
    ...     perform_correction=True,
    ... ) # Setup entanglement protocol
    >>> entanglement_protocol.start() # Run protocol
    """

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

        # Fetch logger
        self.__logger = logging.getLogger("proto_logger")

    def run(self):
        # Local vars
        node_name = self.source.name
        node_proc = self.source.processor
        emit_idx = self.source.emit_idx
        comm_idx = self.source.comm_idx

        # Flush any stale messages on the corrections port
        self.__logger.debug(
            f"[{self.protocol_log}] {node_name}: Flushing corrections port."
        )
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
        self.__logger.info("Emit program completed")

        # Check if a timeout occurred.
        if ent_expr.second_term.second_term.value:
            self.__logger.info(
                f"[{self.protocol_log}] {node_name} ebit establishment timeout."
            )
            return {"log": "timeout", "success": False}

        # Process the Bell state from the received message
        msg = self.source.ports["corrections"].rx_input()
        if msg is None:
            self.__logger.info(f"[{self.protocol_log}] {node_name} missing message")
            return {"log": "no_msg", "success": False}

        bell_state = msg.items[0].bell_index

        if bell_state == -1:
            self.__logger.info(
                f"[{self.protocol_log}] {node_name} invalid entanglement"
            )
            result = {"log": "no entanglement", "success": False}
        elif bell_state == 1:
            self.__logger.info(
                f"[{self.protocol_log}] {node_name} processing Bell state 1"
            )
            if self.perform_correction:
                x_prog = XCorrection()
                node_proc.execute_program(x_prog, qubit_mapping=[comm_idx])
                yield self.await_program(node_proc)
            result = {"log": "corrected", "success": True}
        elif bell_state == 2:
            self.__logger.info(
                f"[{self.protocol_log}] {node_name} processing Bell state 2"
            )
            if self.perform_correction:
                y_prog = YCorrection()
                node_proc.execute_program(y_prog, qubit_mapping=[comm_idx])
                yield self.await_program(node_proc)
            result = {"log": "corrected", "success": True}
        else:
            self.__logger.error(
                f"[{self.protocol_log}] {node_name} bad state: {bell_state}"
            )
            result = {"log": f"bad state: {bell_state}", "success": False}

        return result


class EntanglementRetryProto(Protocol):
    """
    A higher-level protocol that retries entanglement attempts until success
    or until reaching a maximum attempt limit.

    This wrapper manages two `EntanglementProtocol` instances (one per node)
    and coordinates retries across both until a valid Bell pair is established.

    Parameters
    ----------
    routing_table : dict
        Placeholder routing table for entanglement setup (not yet used).
    max_attempts : int
        Maximum number of entanglement attempts.
    timeout : int
        Timeout per entanglement attempt (ns).
    attempts : int
        Number of entanglement attempts the protocol performs before giving up.
    qnode_1 : netsquid.nodes.Node
        First node in the entanglement attempt.
    qnode_2 : netsquid.nodes.Node
        Second node in the entanglement attempt.
    subprotocol_qnode_1 : EntanglementProtocol
        Entanglement protocol instance running on `qnode_1`.
    subprotocol_qnode_2 : EntanglementProtocol
        Entanglement protocol instance running on `qnode_2`.
    """

    def __init__(
        self,
        ctrl_node,
        qnode_1,
        qnode_2,
        routing_table,
        max_attempts=10,
        timeout=1500,
    ):
        super().__init__()
        self.routing_table = routing_table
        self.max_attempts = max_attempts
        self.timeout = timeout
        self.attempts = 0

        # Save nodes TODO remove when CTRL node switching is fixed
        self.qnode_1 = qnode_1
        self.qnode_2 = qnode_2

        # Fetch logger
        self.__logger = logging.getLogger("proto_logger")

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

    def run(self):
        for attempt in range(self.max_attempts):
            # Register and log the attempt count
            self.__logger.info(f"[RETRYPROTO] Attempt {attempt + 1}")

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

            self.__logger.info(
                f"""[RETRYPROTO] Done
                qnode_1: {qnode_1_result['log']}
                qnode_2: {qnode_2_result['log']}"""
            )

            # Verify protocol response status
            if qnode_1_result["success"] and qnode_2_result["success"]:
                self.attempts = attempt + 1
                return True
            else:
                self.__logger.debug("[RETRYPROTO] Failed, retrying")

        # If all attempts fail return False
        self.attempts = self.max_attempts
        return False


class ContinuousDistillationProtocol(Protocol):
    """
    Continuous entanglement distillation protocol.

    This protocol repeatedly attempts to establish entanglement between two
    quantum nodes, performs qubit swapping, and applies entanglement purification
    (EPL-style distillation) in multiple rounds. The goal is to iteratively
    improve the fidelity of the shared entangled state.

    Parameters
    ----------
    ctrl_node : Node
        Control node responsible for managing routing and coordination.
    qnode_1 : Node
        First quantum node participating in entanglement and distillation.
    qnode_2 : Node
        Second quantum node participating in entanglement and distillation.
    routing_table : dict
        Table defining routing information for entanglement attempts.
    max_attempts : int, optional
        Maximum number of entanglement attempts per phase (default: 10).
    timeout : int, optional
        Timeout for entanglement attempts in nanoseconds (default: 1500).
    max_distillations : int, optional
        Maximum number of distillation iterations to perform (default: 3).
    """

    def __init__(
        self,
        ctrl_node,
        qnode_1,
        qnode_2,
        routing_table,
        max_attempts=10,
        timeout=1500,
        max_distillations=3,
    ):
        super().__init__()
        self.ctrl_node = ctrl_node
        self.qnode_1 = qnode_1
        self.qnode_2 = qnode_2
        self.routing_table = routing_table
        self.max_attempts = max_attempts
        self.timeout = timeout
        self.max_distillations = max_distillations
        self.attempts = 0
        self.success = False

        # Fetch logger
        self.__logger = logging.getLogger("proto_logger")

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
        self.__logger.info("[ContinuousDistill] Running protocol.")

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
        """
        Establish entanglement between qnode_1 and qnode_2.

        Parameters
        ----------
        metrics_list : list
            List to store collected metrics
        phase : str
            Protocol phase name

        Returns
        -------
        bool
            True if entanglement was successfully established
        """
        phase_desc = (
            "initial" if phase == "initial" else f"iteration {phase.split('_')[1]}"
        )
        self.__logger.info(f"[ContinuousDistill] {phase} entanglement establishment.")

        for attempt in range(self.max_attempts):
            self.__logger.info(
                f"[ContinuousDistill] {phase_desc} entanglement attempt {attempt+1}"
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
                self.__logger.error("[ContinuousDistill] CTRL node NACKs route request")
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
            self.__logger.info("Subprotocols completed")

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

            self.__logger.info(
                f"[ContinuousDistill] {phase_desc}, attempt {attempt + 1}: "
                f"qnode_1: {qnode_1_result['log']} | qnode_2: {qnode_2_result['log']}"
            )

            # Check success
            if qnode_1_result["success"] and qnode_2_result["success"]:
                return True

            self.__logger.debug(
                f"[ContinuousDistill] {phase_desc} entanglement failed, retrying."
            )

        self.__logger.debug(
            f"[ContinuousDistill] {phase_desc} entanglement failed after max attempts."
        )
        return False

    def _swap_qubits(self):
        """Perform qubit swap operation on both nodes."""
        self.__logger.info(
            "[ContinuousDistill] Swapping qubits (positions 1->2) on both nodes."
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

        self.__logger.info("[ContinuousDistill] Swap operations completed.")

    def _perform_distillation(self, iteration):
        """
        Perform EPL distillation for the given iteration.

        Parameters
        ----------
        iteration : int
            Current distillation iteration (0-indexed)

        Returns
        -------
        bool
            True if distillation was successful
        """
        iteration_num = iteration + 1
        self.__logger.info(
            f"[ContinuousDistill] Running distillation at iteration {iteration_num}"
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

        self.__logger.info(
            f"""[ContinuousDistill] Iteration {iteration_num} results:
            qnode_1: {qnode_1_meas}, qnode_2: {qnode_2_meas}"""
        )

        # Success condition: both outcomes equal 1
        if (qnode_1_meas, qnode_2_meas) != (1, 1):
            # TODO fix failed distillation terminating protocol
            self.__logger.debug(
                f"[ContinuousDistill] Distillation iteration {iteration_num} failed"
            )
            return False

        self.__logger.info(
            f"[ContinuousDistill] Distillation iteration {iteration_num} succeess."
        )
        return True
