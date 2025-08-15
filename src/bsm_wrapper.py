import json
import logging
from netsquid.nodes import Node
from netsquid.examples.simple_link import BSMDetector


class BSMWrapper(Node):
    def __init__(
        self,
        name,
        p_dark,
        det_eff,
        visibility,
    ):
        """
        A wrapper for a Bell-State Measurement (BSM) detector component.

        This component wraps a :class:`BSMDetector` and provides a simplified external
        interface for connecting quantum input ports and a single classical output port.
        It also ensures that a request UUID is tracked between inbound and outbound
        messages.

        The wrapper receives qubits on ``qin0`` and ``qin1``, forwards them to the
        internal BSM detector, and outputs classical measurement results via ``cout``.
        A ``request_uuid`` header is extracted from inbound messages and reinserted into
        outbound classical messages to preserve request–response correlation.

        It uses the ``bsm_logger`` logger object, retrieved with:
        ``logging.getLogger("bsm_logger")``.

        Parameters
        ----------
        name : str
            Name of the BSM wrapper node.
        p_dark : float
            Dark-count probability per detector, i.e., the probability of a detector click
            when no photon was present.
        det_eff : float
            Detector efficiency, i.e., the probability of detecting an incoming photon.
        visibility : float
            HOM visibility parameter of the BSM detector (photon indistinguishability),
            should be between 0 and 1.

        Examples
        --------
        >>> bsm_wrap = BSMWrapper(
        ...     name="BSM_1",
        ...     p_dark=0.001,
        ...     det_eff=0.95,
        ...     visibility=0.9,
        ... )
        >>> bsm_wrap.ports["qin0"].tx_input(qubit_msg_0)
        >>> bsm_wrap.ports["qin1"].tx_input(qubit_msg_1)
        """
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
        """
        Handle inbound qubits on the given port and forward them to the BSM detector.

        The inbound message's ``request_uuid`` header (if present) is extracted
        and stored for later use in the outbound classical message.

        Parameters
        ----------
        msg : netsquid.components.component.Message
            Quantum message received by the wrapper.
        port_name : str
            The name of the quantum input port ("qin0" or "qin1") on the BSM detector.
        """
        # Deserialize the headers and save the UUID
        dict_headers = json.loads(msg.meta.get("header", "{}"))
        request_uuid = dict_headers.pop("request_uuid", None)
        self.__latest_uuid = request_uuid
        self.__logger.debug(f"[{self.name}] Inbound handler got UUID: {request_uuid}")
        self.bsm_detector.ports[port_name].tx_input(msg)

    def __outbound_handler(self, msg):
        """
        Handle outbound classical messages from the BSM detector.

        The stored ``request_uuid`` is inserted into the message's headers before
        forwarding the message through the wrapper's classical output port.

        Parameters
        ----------
        msg : netsquid.components.component.Message
            Classical message produced by the BSM detector.
        """
        # Put in the UUID in the serialized headers and forward to output.
        msg.meta["header"] = json.dumps({"request_uuid": self.__latest_uuid})
        self.__logger.debug(
            f"[{self.name}] Outbound handler using UUID: {self.__latest_uuid}"
        )
        self.ports["cout"].tx_input(msg)
