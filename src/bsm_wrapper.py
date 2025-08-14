import json
import logging
from netsquid.nodes import Node
from detectors import BSMDetector


class BSMWrapper(Node):
    def __init__(
        self,
        name,
        p_dark,
        det_eff,
        visibility,
    ):
        super().__init__(name=name)

        # Last request UUID header
        self.__request_uuid = None

        # Fetch logger
        self.__logger = logging.getLogger("bsm_logger")

        # Instantiate the actual BSMDetector
        self.bsm_detector = BSMDetector(
            name=f"{name}_detector",
            p_dark=p_dark,
            det_eff=det_eff,
            visibility=visibility,
        )

        self.add_subcomponent(self.bsm_detector)

        # Input and output ports of the wrapper
        self.add_ports(["qin0", "qin1", "cout"])

        # Bind inputs from wrapper to internal BSM with amplitude dampening
        self.ports["qin0"].bind_input_handler(
            lambda msg: self.__inbound_handler(msg, "qin0")
        )
        self.ports["qin1"].bind_input_handler(
            lambda msg: self.__inbound_handler(msg, "qin1")
        )

        # Bind outputs from internal BSM to this wrapper's outputs
        self.bsm_detector.ports["cout0"].bind_output_handler(self.__outbound_handler)

    def __inbound_handler(self, msg, port_name):
        # Deserialize the headers and save the UUID
        dict_headers = json.loads(msg.meta.get("header", "{}"))
        request_uuid = dict_headers.pop("request_uuid", None)
        self.__latest_uuid = request_uuid
        self.__logger.debug(f"[{self.name}] Inbound handler got UUID: {request_uuid}")
        self.bsm_detector.ports[port_name].tx_input(msg)

    def __outbound_handler(self, msg):
        # Put in the UUID in the serialized headers and forward to output.
        msg.meta["header"] = json.dumps({"request_uuid": self.__latest_uuid})
        self.__logger.debug(
            f"[{self.name}] Outbound handler using UUID: {self.__latest_uuid}"
        )
        self.ports["cout"].tx_input(msg)
