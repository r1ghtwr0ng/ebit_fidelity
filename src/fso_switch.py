import json
import logging
from netsquid.nodes import Node
from detectors import BSMDetector
from netsquid.components import QuantumChannel
from netsquid.examples.repeater_chain import FibreDepolarizeModel
from netsquid.components.models import FibreDelayModel, FibreLossModel


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

    def __init__(self, name, model_parameters):
        ports = [
            "qin0",
            "qin1",
            "qin2",
            "qout0",
            "qout1",
            "qout2",
            "cout0",
            "cout1",
            "cout2",
        ]
        super().__init__(name, port_names=ports)
        self.__setup_fibre_channels(model_parameters)
        self.__setup_bsm_detector()
        self.__setup_port_forwarding()

    def __setup_bsm_detector(self, p_dark=0, det_eff=1, visibility=1):
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

        # Create BSMDetector component
        bsm_detector = BSMDetector(
            name=f"BSM[{self.name}]",
            p_dark=p_dark,
            det_eff=det_eff,
            visibility=visibility,
        )

        # Add subcomponents
        self.add_subcomponent(bsm_detector)

        self.ports["qout0"].bind_output_handler(bsm_detector.ports["qin0"].tx_input)
        self.ports["qout1"].bind_output_handler(bsm_detector.ports["qin1"].tx_input)
        bsm_detector.ports["cout0"].bind_output_handler(self.ports["cout0"].tx_output)
        bsm_detector.ports["cout1"].bind_output_handler(self.ports["cout1"].tx_output)

    def __setup_port_forwarding(self):
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

    def __setup_fibre_channels(self, model_parameters):
        """
        Configure fibre loss channels with noise, delay, and depolarization models.

        Parameters
        ----------
        model_parameters : dict
            Configuration dictionary for short, mid, and long channels with
            depolarization, loss, and delay parameters.
        """
        model_map_short = {
            "delay_model": FibreDelayModel(),
            "quantum_noise_model": FibreDepolarizeModel(
                p_depol_init=model_parameters["short"]["init_depolar"],
                p_depol_length=model_parameters["short"]["len_depolar"],
            ),
            "quantum_loss_model": FibreLossModel(
                p_loss_init=model_parameters["short"]["init_loss"],
                p_loss_length=model_parameters["short"]["len_loss"],
                rng=None,
            ),
        }
        model_map_mid = {
            "quantum_noise_model": FibreDepolarizeModel(
                p_depol_init=model_parameters["mid"]["init_depolar"],
                p_depol_length=model_parameters["mid"]["len_depolar"],
            ),
            "quantum_loss_model": FibreLossModel(
                p_loss_init=model_parameters["mid"]["init_loss"],
                p_loss_length=model_parameters["mid"]["len_loss"],
                rng=None,
            ),
        }
        model_map_long = {
            "delay_model": FibreDelayModel(),
            "quantum_noise_model": FibreDepolarizeModel(
                p_depol_init=model_parameters["long"]["init_depolar"],
                p_depol_length=model_parameters["long"]["len_depolar"],
            ),
            "quantum_loss_model": FibreLossModel(
                p_loss_init=model_parameters["long"]["init_loss"],
                p_loss_length=model_parameters["long"]["len_loss"],
                rng=None,
            ),
        }

        # Model the three different routes qubits can take through the switch
        qchannel_short = QuantumChannel(
            name="qchannel_short",
            models=model_map_short,
            length=model_parameters["short"]["channel_len"],
        )
        qchannel_mid = QuantumChannel(
            name="qchannel_mid",
            models=model_map_mid,
            length=model_parameters["mid"]["channel_len"],
        )
        qchannel_long = QuantumChannel(
            name="qchannel_long",
            models=model_map_long,
            length=model_parameters["long"]["channel_len"],
        )

        # Add subcomponents
        self.__channels = [qchannel_short, qchannel_mid, qchannel_long]

    def __relay_qubit(self, msg):
        """
        Route an incoming quantum message to the appropriate output port.

        Parameters
        ----------
        msg : object
            Quantum message containing metadata for routing.
        """
        serialized_headers = msg.meta.get("header", "{}")
        dict_headers = json.loads(serialized_headers)
        outbound_port = dict_headers.pop("outport", None)
        # Debug print
        logging.debug(
            f"(FSOSwitch | {self.name}) Relaying qubit to port: {outbound_port}"
        )

        # Serialize headers before sending (dict is unhashable)
        msg.meta["header"] = json.dumps(dict_headers)
        self.ports[outbound_port].tx_output(msg)

    def __recv_qubit(self, msg):
        """
        Process an inbound qubit, determine the routing path, and forward it
        through the appropriate lossy channel.

        Parameters
        ----------
        msg : object
            Quantum message received on a specific input port.
        """
        inbound_port = msg.meta.get("rx_port_name", "missing_port_name")
        logging.debug(
            f"(FSOSwitch | {self.name}) Received {msg} on port {inbound_port}"
        )
        # TODO extract destination from message metadata and route through the
        # correct channel
        outbound_port = self.__routing_table[inbound_port]

        # Deserialize the JSON headers
        serialized_headers = msg.meta.get("header", "{}")
        dict_headers = json.loads(serialized_headers)
        dict_headers["outport"] = outbound_port
        logging.debug(
            f"!!! Incoming port: {inbound_port} | Outbound port: {outbound_port}"
        )
        # Calculate which channel to route through:
        # 0 -> Short channel
        # 1 -> Medium channel
        # 2 -> Long channel
        channel_idx = abs(int(inbound_port[-1]) - int(outbound_port[-1]))
        channel = self.__channels[channel_idx]

        # Serialize the headers before sending
        msg.meta["header"] = json.dumps(dict_headers)
        channel.ports["send"].tx_input(msg)

    def switch(self, routing_table):
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
        valid_keys = list(routing_table.keys()) == ["qin0", "qin1", "qin2"]
        valid_vals = list(routing_table.values()) == ["qout0", "qout1", "qout2"]
        if not (valid_keys and valid_vals):
            logging.error(f"Invalid routing rable: {routing_table}")

        self.__routing_table = routing_table.copy()
        # TODO set timeout by which you will switch to the next request
