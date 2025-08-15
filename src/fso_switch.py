import json
import logging
from utils import loss_prob
from netsquid.nodes import Node
from bsm_wrapper import BSMWrapper
from netsquid.qubits.qubitapi import amplitude_dampen
from netsquid.components import QuantumChannel
from netsquid.components.models import (
    FibreDelayModel,
    FibreLossModel,
)


class FSOSwitch(Node):
    """
    A Free-Space Optical (FSO) switch component for routing quantum signals.

    This routes photonic qubits through lossy fibre channels and connects to
    a Bell-state measurement (BSM) detector. It applies fibre models for noise and loss.

    The connections to and from the switch should be registered using register() to
    allow for proper switching on a component name basis.

    It uses the "fso_logger" logger object, get it with:
    ``logging.getLogger("fso_logger")``

    Parameters
    ----------
    switch_id : int
        Integer ID of the switch, it's used to create the :class:`netsquid.nodes.Node`
        superclass name.
    ctrl_port : netsquid.components.component.Port
        The port object of the control node, all output commands are sent to it.
    dampening_parameter : float
        Amplitude dampening parameter for photons passing through the switch.
        Should be between 0 and 1.
    ideal : bool
        Specify whether the switch is ideal, i.e. no photon losses and path differences
        in fibre channels.
    herald_ports : list
        The entanglement heralding port names which will be connected to the BSM device.
    visibility : float
        The HOM visibility parameter of the BSM detector attached to the herald ports.
        Should be between 0 and 1.

    Examples
    --------
    >>> ctrl_node = ControlNode(id=0, network_type="tree")
    >>> ctrl_port = ctrl_node.ports["switch_herald"]
    >>> fsoswitch_node = FSOSwitch(
    >>>     switch_id=1,
    >>>     ctrl_port=ctrl_port,
    >>>     dampening_parameter=0.15,
    >>>     ideal=False,
    >>>     herald_ports=["qout0", "qout1"],
    >>>     visibility=0.85,
    >>> )
    """

    def __init__(
        self,
        switch_id,
        ctrl_port,
        dampening_parameter,
        ideal=False,
        herald_ports=["qout0", "qout1"],
        visibility=1,
    ):
        ports = [
            "qin0",
            "qin1",
            "qin2",
            "qout0",
            "qout1",
            "qout2",
            "cout",
        ]
        self.id = switch_id
        name = f"switch_{switch_id}"
        super().__init__(name, port_names=ports)
        self.__ctrl_port = ctrl_port
        self.__setup_fibre_channels(ideal)
        self.__setup_bsm_detector(
            herald_ports=herald_ports,
            det_eff=1,  # Ideal detector
            dampening_parameter=dampening_parameter,
            visibility=visibility,
        )
        self.__setup_port_forwarding(ctrl_port)

        # Amplitude dampening parameter
        self.__amplitude_dampening = dampening_parameter

        # Save the outbound port name for quick lookup
        self.__outbound_port = list({"qout0", "qout1", "qout2"} - set(herald_ports))[0]
        self.__herald_ports = herald_ports

        # Default routing
        self.__routing_table = {"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"}

        # Connections registry
        self.__registry = {}

        # Fetch logger
        self.__logger = logging.getLogger("fso_logger")

    def __setup_bsm_detector(
        self,
        herald_ports,
        dampening_parameter,
        det_eff,
        visibility,
        p_dark=0,
    ):
        """
        Creates a BSM detector component and adds it as a subcomponent to the FSO Switch
        Assuming herald_ports of ["qout0", "qout1"], we have these port bindings:
            [FSO] qout0 -> qin0  [BSM]
            [FSO] qout1 -> qin1  [BSM]

        Parameters
        ----------
        herald_ports : list
            The entanglement heralding port names which will be connected to the BSM.
        dampening_parameter : float
            Amplitude dampening parameter for photons passing through the switch.
            Should be between 0 and 1.
        det_eff : float
            Efficiency per detector, i.e. the probability of detecting an incoming
            photon.
        visibility : float
            The HOM visibility parameter of the BSM detector attached to the herald ports.
            Should be between 0 and 1.
        p_dark : float, optional
            Dark-count probability, i.e. probability of measuring a photon while
            no photon was present.
        """

        bsm_wrapper = BSMWrapper(
            name=f"BSMWrap_{self.id}",
            p_dark=p_dark,
            det_eff=det_eff,
            visibility=visibility,
        )
        self.add_subcomponent(bsm_wrapper)

        # Connect ports from FSO to BSM heralding station wrapper
        self.ports[herald_ports[0]].bind_output_handler(
            bsm_wrapper.ports["qin0"].tx_input
        )
        self.ports[herald_ports[1]].bind_output_handler(
            bsm_wrapper.ports["qin1"].tx_input
        )
        bsm_wrapper.ports["cout"].bind_input_handler(self.__ctrl_port.tx_input)

    def __setup_fibre_channels(self, ideal):
        """
        Configure fibre loss channels with noise, delay, and depolarization models.

        Parameters
        ----------
        ideal : bool
            A boolean parameter controlling whether the switch is an ideal component
            (no loss and path differences).
        """

        model_map_short = {
            "quantum_loss_model": FibreLossModel(
                p_loss_init=0 if ideal else loss_prob(1.319),
                rng=None,
            ),
        }
        model_map_mid = {
            "quantum_loss_model": FibreLossModel(
                p_loss_init=0 if ideal else loss_prob(2.12),
                rng=None,
            ),
        }
        model_map_long = {
            "quantum_loss_model": FibreLossModel(
                p_loss_init=0 if ideal else loss_prob(2.005),
                rng=None,
            ),
        }

        # Model the three different routes qubits can take through the switch
        qchannel_short = QuantumChannel(
            name="qchannel_short",
            models=model_map_short,
            length=0 if ideal else 0.005,
        )
        qchannel_mid = QuantumChannel(
            name="qchannel_mid",
            models=model_map_mid,
            length=0 if ideal else 0.00587,
        )
        qchannel_long = QuantumChannel(
            name="qchannel_long",
            models=model_map_long,
            length=0 if ideal else 0.00756,
        )

        # Add subcomponents
        self.__channels = [qchannel_short, qchannel_mid, qchannel_long]

    def __setup_port_forwarding(self, ctrl_port):
        """
        Setup routing for the incoming ports through the fibre channels to the output
        ports. The classical output (cout) port is bound to the control node's port
        (ctrl_port) for communicating routing requests.

        Parameters
        ----------
        ctrl_port : netsquid.components.component.Port
            The port object of the control node to which requests from the "cout" port
            are relayed.
        """
        # Bind input handlers
        self.ports["qin0"].bind_input_handler(self.__recv_qubit, tag_meta=True)
        self.ports["qin1"].bind_input_handler(self.__recv_qubit, tag_meta=True)
        self.ports["qin2"].bind_input_handler(self.__recv_qubit, tag_meta=True)

        # Bind output handlers
        self.__channels[0].ports["recv"].bind_output_handler(self.__relay_qubit)
        self.__channels[1].ports["recv"].bind_output_handler(self.__relay_qubit)
        self.__channels[2].ports["recv"].bind_output_handler(self.__relay_qubit)

        # Route COUT messages to CTRL_PORT.tx_input via a lambda
        self.ports["cout"].bind_output_handler(lambda msg: ctrl_port.tx_input(msg))

    def __relay_qubit(self, msg):
        """
        Route an incoming quantum message to the appropriate output port. This requires
        deserializing the message headers, popping the output port and relaying the
        message through the port.

        Parameters
        ----------
        msg : netsquid.components.component.Message
            Quantum message containing metadata for routing.
        """

        serialized_headers = msg.meta.get("header", "{}")
        dict_headers = json.loads(serialized_headers)
        outbound_port = dict_headers.pop("outport", None)
        # Debug print
        self.__logger.debug(f"{self.name} Relaying qubit to port: {outbound_port}")

        # Serialize headers before sending (dict is unhashable)
        msg.meta["header"] = json.dumps(dict_headers)
        self.ports[outbound_port].tx_output(msg)

    def __recv_qubit(self, msg):
        """
        Process an inbound qubit, apply amplitude dampening, determine the routing path
        and forward it through the appropriate lossy channel.

        Parameters
        ----------
        msg : netsquid.components.component.Message
            Quantum message received on a specific input port.
        """
        inbound_port = msg.meta.get("rx_port_name", "missing_port_name")
        outbound_port = self.__routing_table[inbound_port]
        self.__logger.debug(
            f"""[{self.name}] Received ({msg.items[0]} sender: {msg.meta['source']}
            hdr: {msg.meta['header']}) on port {inbound_port}"""
        )

        # Deserialize the JSON headers
        serialized_headers = msg.meta.get("header", "{}")
        dict_headers = json.loads(serialized_headers)
        dict_headers["outport"] = outbound_port
        self.__logger.debug(
            f"[{self.name}] Incoming: {inbound_port} | Outbound: {outbound_port}"
        )

        # Calculate which channel to route through:
        # 0 -> Short channel
        # 1 -> Medium channel
        # 2 -> Long channel
        channel_idx = abs(int(inbound_port[-1]) - int(outbound_port[-1]))
        channel = self.__channels[channel_idx]

        # Serialize the headers
        msg.meta["header"] = json.dumps(dict_headers)

        # Apply amplitude dampening
        amplitude_dampen(msg.items[0], self.__amplitude_dampening)

        # Relay qubit
        channel.ports["send"].tx_input(msg)

    def __switch(self, routing_table):
        """
        Configure the FSO switch's routing table for input-output port mapping.

        Parameters
        ----------
        routing_table : dict
            Dictionary mapping input ports (qin0, qin1, qin2) to output ports
            (qout0, qout1, qout2).

        Raises
        ------
        ValueError
            If the provided routing table has invalid keys or values.
        """
        self.__logger.info(f"Switching {self.name}: {routing_table}")
        valid_keys = sorted(routing_table.keys()) == ["qin0", "qin1", "qin2"]
        valid_vals = sorted(routing_table.values()) == ["qout0", "qout1", "qout2"]
        if not (valid_keys and valid_vals):
            self.__logger.error(f"[FSO] Invalid routing table: {routing_table}")

        self.__routing_table = routing_table.copy()

    def _query_node(self, node_name):
        return self.__registry.get(node_name)

    def register(self, node_name, inbound_port):
        """
        Register a node that is connected to the switch's port for later querying.

        Parameters
        ----------
        node_name : str
            The name of the node object.
        inbound_port : str
            The port name to which the node is connected to.
        """
        self.__registry[node_name] = inbound_port

    def herald_switch(self, node_one, node_two):
        """
        Change to a routing configuration which routes the input ports connected to the
        two nodes to the BSM detector node (heralding device).

        Parameters
        ----------
        node_one : str
            The first node which must be routed to the heralding device.

        node_two : str
            The second node which must be routed to the heralding device.
        """
        # Fetch port names
        inbound_one = self._query_node(node_one)
        inbound_two = self._query_node(node_two)
        remaining = list({"qin0", "qin1", "qin2"} - {inbound_one, inbound_two})[0]
        self.__logger.info(
            f"""[HERALD] {node_one} ({inbound_one}) & {node_two} ({inbound_two})
            To herald: {self.__herald_ports}"""
        )

        # Construct routing table
        routing_table = {
            inbound_one: self.__herald_ports[0],
            inbound_two: self.__herald_ports[1],
            remaining: self.__outbound_port,
        }
        self.__logger.info(f"[HERALD TABLE] {routing_table}")
        self.__switch(routing_table)

    def relay_switch(self, node_in, node_out):
        """
        Change the switching configuration to connect node_in to node_out, assuming they
        have been registered with the node. Remaining paths are connected in no
        particular order.

        Parameters
        ----------
        node_in : str
            The name of the node from which the photon is inbound.
        node_out : str
            The name of the photon's destination node, connected to an output port.
        """
        # Fetch port names
        inbound_port = self._query_node(node_in)
        outbound_port = self._query_node(node_out)
        remaining_in = list({"qin0", "qin1", "qin2"} - {inbound_port})
        remaining_out = list({"qout0", "qout1", "qout2"} - {outbound_port})

        # Construct routing table to relay in -> out
        routing_table = {
            inbound_port: outbound_port,
            remaining_in[0]: remaining_out[0],
            remaining_in[1]: remaining_out[1],
        }
        self.__logger.debug("========= RELAY SWITCHING ============")
        self.__logger.debug(f"REGISTRY: {self.__registry}")
        self.__logger.debug(f"INBOUND  ({node_in}): {inbound_port}")
        self.__logger.debug(f"OUTBOUND ({node_out}): {outbound_port}")
        self.__logger.debug(f"REMAINING IN: {inbound_port}")
        self.__logger.debug(f"REMAINING OUT: {inbound_port}")
        self.__switch(routing_table)

    # Switch to the initial saved configuration
    def default_switch(self):
        """
        Reset the switch to the initial switching configuration (no deflections)
        default: {"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"}
        """
        self.__switch(self.__routing_table)
