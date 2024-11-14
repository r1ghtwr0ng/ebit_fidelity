import logging
from detectors import BSMDetector
from netsquid.components import Component
from netsquid.components import QuantumChannel
from netsquid.examples.repeater_chain import FibreDepolarizeModel
from netsquid.components.models import FibreDelayModel, FibreLossModel

# TODO fix this by adding a well-defined header object at some point
#from networking import MessageHeader

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
                "len_loss": 0,#.25,
                "init_depolar": 0,
                "len_depolar": 0,
                "channel_len": 1,
            },
            "mid": {
                "init_loss": 0,
                "len_loss": 0,#.25,
                "init_depolar": 0,
                "len_depolar": 0,
                "channel_len": 1.2,
            },
            "long": {
                "init_loss": 0,
                "len_loss": 0,#.25,
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
        self.add_subcomponent(qchannel_short)
        self.add_subcomponent(qchannel_mid)
        self.add_subcomponent(qchannel_long)

    def __handle_incoming(self, msg):
        event_id = msg.meta['put_event'].id
        #header = msg.meta['header']
        #request_id = header['request_id']
        #input = self.__lookup_input(request_id)
        # TODO register the event ID in the routing table for future reference

        print(f"Fucking debug shit ------------ {self.subcomponents}")
        
    def __setup_port_forwarding(self):
        """Setup routing for the incoming ports through the lossy channels to the output ports"""
        # Bind input handlers
        self.ports["qin0"].bind_input_handler(self.__handle_incoming)
        self.ports["qin1"].bind_input_handler(
            lambda msg: print(f"Received msg on port qin1: {msg}")
        )
        self.ports["qin2"].bind_input_handler(
            lambda msg: print(f"Received msg on port qin: {msg}")
        )

        # Bind output handlers
        self.subcomponents["qchannel_short"].ports["recv"].bind_input_handler(
            self.__send_qubit
        )
        self.subcomponents["qchannel_mid"].ports["recv"].bind_input_handler(
            self.__send_qubit
        )
        self.subcomponents["qchannel_long"].ports["recv"].bind_input_handler(
            self.__send_qubit
        )

    def __send_qubit(self, msg):
        """Route message to the necessary output port depending on the header contents"""
        # sim_event_id, destination_switch, entanglement_id, herald_input
        outbound_port = msg.header["outport"]
        self.ports[outbound_port].tx_input(msg)

    def __recv_qubit(self, msg, inbound_port):
        """Handle inbound qubit on a given port and route through a lossy channel"""
        logging.debug(
            f"(FSOSwitch | {self.name}) Received {msg} on port {inbound_port}"
        )
        # TODO extract destination from message metadata and route through the correct channel
        routing_table = {
            "qin0": {
                "qout0": self.subcomponents["qchannel_short"],
                "qout1": self.subcomponents["qchannel_mid"],
                "qout2": self.subcomponents["qchannel_long"],
            },
            "qin1": {
                "qout0": self.subcomponents["qchannel_mid"],
                "qout1": self.subcomponents["qchannel_short"],
                "qout2": self.subcomponents["qchannel_mid"],
            },
            "qin2": {
                "qout0": self.subcomponents["qchannel_long"],
                "qout1": self.subcomponents["qchannel_mid"],
                "qout2": self.subcomponents["qchannel_short"],
            },
        }
        outbound_port = msg.header["outport"]
        channel = routing_table[inbound_port][outbound_port]
        channel.ports["send"].tx_input(msg)

    def switch(self, input, output):
        pass

