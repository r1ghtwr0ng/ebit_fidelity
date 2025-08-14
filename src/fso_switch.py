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

    This component manages the routing of quantum information through lossy
    channels, including the setup of a Bell-state measurement (BSM) detector
    and fiber models for noise, loss, and delay.

    Parameters
    ----------
    name : str
        Name of the FSO switch.
    model_parameters : dict
        Configuration for fiber loss, delay, and depolarization models.
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
        Port bindings:  [FSO] qout0 -> qin0  [BSM]
                        [FSO] qout1 -> qin1  [BSM]
                        [FSO] cout0 <- cout0 [BSM]
                        [FSO] cout1 <- cout1 [BSM]

        Parameters
        ----------
        p_dark : float, optional
            Dark-count probability, i.e. probability of measuring a photon while
            no photon was present, per detector.
        det_eff : float, optional
            Efficiency per detector, i.e. the probability of detecting an incoming
            photon.
        visibility : float, optional
            Visibility of the Hong-Ou-Mandel dip, also referred to as the photon
            indistinguishability.
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
        model_parameters : dict
            Configuration dictionary for short, mid, and long channels with
            depolarization, loss, and delay parameters.
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
        Setup routing for the incoming ports through the lossy channels to the output
        ports
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
        Apply amplitude dampening and route an incoming quantum message
        to the appropriate output port.

        Parameters
        ----------
        msg : object
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
        Process an inbound qubit, apply amplitude dempaning, determine the routing path
        and forward it through the appropriate lossy channel.

        Parameters
        ----------
        msg : object
            Quantum message received on a specific input port.
        """
        inbound_port = msg.meta.get("rx_port_name", "missing_port_name")
        outbound_port = self.__routing_table[inbound_port]
        self.__logger.debug(
            f"[{self.name}] Received ({msg.items[0]} sender: {msg.meta['source']}, hdr: {msg.meta['header']}) on port {inbound_port}"
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
            self.__logger.error(f"[FSO] Invalid routing rable: {routing_table}")

        self.__routing_table = routing_table.copy()

    def _query_node(self, node_name):
        return self.__registry.get(node_name)

    def register(self, node_name, inbound_port):
        self.__registry[node_name] = inbound_port

    def herald_switch(self, node_low, node_high):
        # Fetch port names
        inbound_low = self._query_node(node_low)
        inbound_high = self._query_node(node_high)
        remaining = list({"qin0", "qin1", "qin2"} - {inbound_low, inbound_high})[0]
        self.__logger.info(
            f"[HERALD SWITCH] {node_low} ({inbound_low}) and {node_high} ({inbound_high}) to herald: {self.__herald_ports}"
        )

        # Construct routing table
        routing_table = {
            inbound_low: self.__herald_ports[0],
            inbound_high: self.__herald_ports[1],
            remaining: self.__outbound_port,
        }
        self.__logger.info(f"[HERALD TABLE] {routing_table}")
        self.__switch(routing_table)

    def relay_switch(self, node_in, node_out):
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
        self.__switch(self.__routing_table)

    # Get heralding ports and outbound ports
    def get_outports(self):
        return self.__herald_ports, self.__outbound_port
