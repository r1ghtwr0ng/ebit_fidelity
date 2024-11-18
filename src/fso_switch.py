import json
import logging
from detectors import BSMDetector
from netsquid.components import Component
from netsquid.components import QuantumChannel
from netsquid.examples.repeater_chain import FibreDepolarizeModel
from netsquid.components.models import FibreDelayModel, FibreLossModel

# TODO fix this by adding a well-defined header object at some point
# from networking import MessageHeader


class FSOSwitch(Component):
    def __init__(self, name):
        ports = ["qin0", "qin1", "qin2", "qout0", "qout1", "qout2", "cout0", "cout1"]
        super().__init__(name, port_names=ports)
        self.__setup_fibre_channels()
        self.__setup_bsm_detector()
        self.__setup_port_forwarding()

    def __setup_bsm_detector(self):
        # Create BSMDetector component
        bsm_detector = BSMDetector(f"BSM[{self.name}]")

        # Add subcomponents
        self.add_subcomponent(bsm_detector)

        self.ports["qout0"].bind_output_handler(
            lambda msg: bsm_detector.ports["qin0"].tx_input(msg)
        )
        self.ports["qout1"].bind_output_handler(
            lambda msg: bsm_detector.ports["qin1"].tx_input(msg)
        )
        bsm_detector.ports["cout0"].bind_output_handler(
            lambda msg: self.ports["cout0"].tx_input(msg)
        )
        bsm_detector.ports["cout1"].bind_output_handler(
            lambda msg: self.ports["cout1"].tx_input(msg)
        )

    def __setup_fibre_channels(self):
        """Initialize the fibre loss channels through which photons are routed"""
        model_parameters = {
            "short": {
                "init_loss": 0,
                "len_loss": 0,  # .25,
                "init_depolar": 0,
                "len_depolar": 0,
                "channel_len": 1,
            },
            "mid": {
                "init_loss": 0,
                "len_loss": 0,  # .25,
                "init_depolar": 0,
                "len_depolar": 0,
                "channel_len": 1.2,
            },
            "long": {
                "init_loss": 0,
                "len_loss": 0,  # .25,
                "init_depolar": 0,
                "len_depolar": 0,
                "channel_len": 1.4,
            },
        }

        # Model the fibre loss, delay and dephasing of the different routes in the switch
        model_map_short = {
            "delay_model": FibreDelayModel(
                p_depol_init=model_parameters["short"]["init_depolar"],
                p_depol_length=model_parameters["short"]["len_depolar"],
            ),
            "quantum_noise_model": FibreDepolarizeModel(),
            "quantum_loss_model": FibreLossModel(
                p_loss_init=model_parameters["short"]["init_loss"],
                p_loss_length=model_parameters["short"]["len_loss"],
                rng=None,
            ),
        }
        model_map_mid = {
            "delay_model": FibreDelayModel(
                p_depol_init=model_parameters["mid"]["init_depolar"],
                p_depol_length=model_parameters["mid"]["len_depolar"],
            ),
            "quantum_noise_model": FibreDepolarizeModel(),
            "quantum_loss_model": FibreLossModel(
                p_loss_init=model_parameters["mid"]["init_loss"],
                p_loss_length=model_parameters["mid"]["len_loss"],
                rng=None,
            ),
        }
        model_map_long = {
            "delay_model": FibreDelayModel(
                p_depol_init=model_parameters["long"]["init_depolar"],
                p_depol_length=model_parameters["long"]["len_depolar"],
            ),
            "quantum_noise_model": FibreDepolarizeModel(),
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

    def __setup_port_forwarding(self):
        """Setup routing for the incoming ports through the lossy channels to the output ports"""
        # Bind input handlers
        self.ports["qin0"].bind_input_handler(self.__recv_qubit, tag_meta=True)
        self.ports["qin1"].bind_input_handler(self.__recv_qubit, tag_meta=True)
        self.ports["qin2"].bind_input_handler(self.__recv_qubit, tag_meta=True)

        # Bind output handlers
        self.__channels[0].ports["recv"].bind_output_handler(self.__relay_qubit)
        self.__channels[1].ports["recv"].bind_output_handler(self.__relay_qubit)
        self.__channels[2].ports["recv"].bind_output_handler(self.__relay_qubit)

    def __relay_qubit(self, msg):
        """Route message to the necessary output port depending on the header contents"""
        # Deserialize the headers from the msg metadata
        serialized_headers = msg.meta.get("header", "{}")
        dict_headers = json.loads(serialized_headers)
        outbound_port = dict_headers.pop("outport", None)
        # Debug print
        logging.info(f"Routing qubit to port: {outbound_port}")

        # Serialize headers before sending (dict is unhashable)
        msg.meta["header"] = json.dumps(dict_headers)
        self.ports[outbound_port].tx_input(msg)

    def __recv_qubit(self, msg):
        """Handle inbound qubit on a given port and route through a lossy channel"""
        inbound_port = msg.meta.get("rx_port_name", "missing_port_name")
        logging.debug(
            f"(FSOSwitch | {self.name}) LETS FUCKING DEBUG THIS SHIT AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA Received {msg} on port {inbound_port}"
        )
        # TODO extract destination from message metadata and route through the correct channel
        outbound_port = self.__routing_table[inbound_port]

        # Deserialize the JSON headers
        serialized_headers = msg.meta.get("header", "{}")
        dict_headers = json.loads(serialized_headers)
        dict_headers["outport"] = outbound_port
        logging.info(
            f"!!! Incoming port: {inbound_port} | Outbound port: {outbound_port}"
        )
        # Calculate which channel to route through:
        # 0 -> Short channel
        # 1 -> Medium channel
        # 2 -> Long channel
        channel_idx = abs(int(inbound_port[-1]) - int(outbound_port[-1]))
        channel = self.__channels[channel_idx]
        logging.debug(f"Fucking channel man: {channel.ports['send']} | msg: {msg}")

        # Serialize the headers before sending
        msg.meta["header"] = json.dumps(dict_headers)
        channel.ports["send"].tx_input(msg)

    def switch(self, routing_table):
        valid_keys = list(routing_table.keys()) == ["qin0", "qin1", "qin2"]
        valid_vals = list(routing_table.values()) == ["qout0", "qout1", "qout2"]
        if not (valid_keys and valid_vals):
            logging.error(f"Invalid routing rable: {routing_table}")

        self.__routing_table = routing_table.copy()
        # TODO set timeout by which you will switch to the next request
