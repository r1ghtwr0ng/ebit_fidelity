import re
import uuid
import json
import logging

from netsquid.nodes import Node


class ControlNode(Node):
    """
    Central controller node for managing quantum network switching.

    The control node is responsible for:
      * Maintaining a central registry mapping node names to their object instances.
      * Receiving heralding signals from switches and forwarding correction messages
        to the relevant quantum nodes.
      * Sending switching commands to configure the network, with topology-dependent
        routing logic (ring, tree, or simple).
      * Assigning a unique UUID to each routing request for correlation between
        switching commands and heralded corrections.

    Parameters
    ----------
    id : int
        Unique integer identifier for the control node, included in its name as ``CTRL[{id}]``.
    network_type : str, optional
        Network topology type that determines which internal switching method is used.
        Supported values are:
          * ``"ring"`` – ring topology with intermediate relay configuration.
          * ``"tree"`` – hierarchical tree topology with a super-switch.
          * ``"simple"`` – single-switch topology.
        Any other value defaults to no-op switching.

    Attributes
    ----------
    __registry : dict[str, Node]
        Central mapping of registered node names to their object instances.
        Used for name → object resolution during switching and correction handling.
    __uuid_queue : dict[str, tuple[str, str]]
        Maps request UUIDs to the pair of quantum node names involved in the route.
    ports : dict[str, Port]
        Contains the ``switch_herald`` input port for receiving heralding messages.
    __logger : logging.Logger
        Logger instance for controller events.
    __switch_re : re.Pattern
        Compiled regex for parsing switch names (e.g., ``switch_2``).
    __qnode_re : re.Pattern
        Compiled regex for parsing quantum node names (e.g., ``qnode_5``).

    Examples
    --------
    >>> ctrl_node = ControlNode(id=0, network_type="ring")
    >>> ctrl_node.register_nodes([node_a, node_b, switch_0, switch_1])
    >>> req_id = ctrl_node.request_route("qnode_0", "qnode_3")
    >>> isinstance(req_id, str)
    True
    """

    def __init__(self, id, network_type=None):
        # Central registry for all nodes, allows for name -> Object resolution
        self.__registry = {}

        # Setup ports
        super().__init__(f"CTRL[{id}]", port_names=["switch_herald"])

        # Fetch logger
        self.__logger = logging.getLogger("ctrl_logger")

        self.__uuid_queue = {}
        self.__setup_callbacks()

        # Compile regexes for efficiency
        self.__switch_re = re.compile("^(switch_)([0-9]{1,})$")
        self.__qnode_re = re.compile("^(qnode_)([0-9]{1,})$")

        # Setup routing controls based on topology
        if network_type == "ring":
            self.__switch_route = self.__switch_ring
        elif network_type == "tree":
            self.__switch_route = self.__switch_tree
        elif network_type == "simple":
            self.__switch_route = self.__switch_simple
        else:
            self.__switch_route = self.__noop

    def request_route(self, qnode_1_name, qnode_2_name):
        """
        Initiate a switching request between two quantum nodes.

        Sends topology-dependent switching commands to configure the network,
        then generates and stores a request UUID to match future heralding
        corrections to this route.

        Parameters
        ----------
        qnode_1_name : str
            Name of the first quantum node (e.g., ``"qnode_0"``).
        qnode_2_name : str
            Name of the second quantum node.

        Returns
        -------
        str
            UUID string identifying this routing request.
        """
        # Send switching signals along the route to configure the network
        self.__switch_route(qnode_1_name, qnode_2_name)

        # TODO clean up the requests table if too big (i.e. leftover dropped requests)
        # Create request UUID
        request_uuid = str(uuid.uuid4())
        self.__uuid_queue[request_uuid] = (qnode_1_name, qnode_2_name)
        return request_uuid

    def register_nodes(self, node_list):
        """
        Register a set of nodes with the controller.

        Adds node objects to the internal registry so they can be referenced
        by name during switching and correction handling.

        Parameters
        ----------
        node_list : list[netsquid.nodes.Node]
            List of node objects to register.
        """
        # Register a list of nodes with the central registry
        for node in node_list:
            self.__registry[node.name] = node

    def _query_node(self, name):
        """
        Retrieve a node object from the registry by name.

        Parameters
        ----------
        name : str
            Node name to look up.

        Returns
        -------
        Node or None
            The corresponding node object, or ``None`` if not found.
        """

        # For debugging purposes, allows directly querying the central registry
        return self.__registry.get(name)

    def __setup_callbacks(self):
        # Setup callbacks for port
        self.ports["switch_herald"].bind_input_handler(self.__handle_correction)

    def __handle_correction(self, msg):
        """
        Handle a heralding correction message from a switch.

        Extracts the request UUID from the message header, resolves the
        associated quantum nodes from the UUID queue, and forwards the
        correction message to both nodes' ``corrections`` ports.

        Parameters
        ----------
        msg : Message
            Heralding correction message containing a serialized JSON header
            with the ``request_uuid`` field.
        """
        dict_headers = json.loads(msg.meta.get("header", "{}"))
        request_uuid = dict_headers.pop("request_uuid", None)
        (qnode_1_name, qnode_2_name) = self.__uuid_queue.get(request_uuid)

        self.__logger.debug(
            f"[ControlNode] Received corrections UUID: {request_uuid}, routing to: {qnode_1_name}, {qnode_2_name}"
        )

        # Resolve qnode_1, qnode_2ination
        qnode_1 = self._query_node(qnode_1_name)
        qnode_2 = self._query_node(qnode_2_name)

        # Relay the request to the corrections port
        qnode_1.ports["corrections"].tx_input(msg)
        qnode_2.ports["corrections"].tx_input(msg)

    def __switch_ring(self, qnode_1_name, qnode_2_name):
        """
        Perform switching for a ring network topology.

        Configures the relevant switches between two quantum nodes. If the
        nodes share the same switch, a direct herald switch is set. Otherwise,
        intermediate switches are configured in relay mode to connect the
        path, with the final switch set to herald.

        Parameters
        ----------
        qnode_1_name : str
            Name of the first quantum node.
        qnode_2_name : str
            Name of the second quantum node.
        """
        # Step 1: Parse the ID from the string name
        id_1 = self.__qnode_re.findall(qnode_1_name)[0][1]
        id_2 = self.__qnode_re.findall(qnode_2_name)[0][1]

        # Step 2: sort x < y
        [low_id, high_id] = sorted([int(id_1), int(id_2)])

        # Step 3: Identify the switches
        sw_low = low_id // 2
        sw_high = high_id // 2

        # Convert to qnode names
        low_qnode = f"qnode_{low_id}"
        high_qnode = f"qnode_{high_id}"
        low_switch = f"switch_{sw_low}"
        high_switch = f"switch_{sw_high}"

        # Step 4: Do routing checks, send commands
        if sw_low == sw_high:
            # Get the switch object and send command
            switch_node = self._query_node(low_switch)
            switch_node.herald_switch(low_qnode, high_qnode)
        else:
            # Get number of switches in ring network
            switch_count = len([x for x in self.__registry if "switch_" in x])

            # Switch intermediate nodes to relay previous -> next node
            for sw_idx in range(sw_low + 1, sw_high):
                prev_switch_idx = (sw_idx - 1) % switch_count
                next_switch_idx = (sw_idx + 1) % switch_count
                prev_switch = f"switch_{prev_switch_idx}"
                next_switch = f"switch_{next_switch_idx}"
                intermediate_switch_node = self._query_node(f"switch_{sw_idx}")
                intermediate_switch_node.relay_switch(prev_switch, next_switch)

            # Find target (next node) and switch first node to it
            next_switch_idx = (sw_low + 1) % switch_count
            next_switch = f"switch_{next_switch_idx}"
            first_switch_node = self._query_node(low_switch)
            first_switch_node.relay_switch(low_qnode, next_switch)

            # Switch final node to herald (high_id, 2)
            prev_sw_name = f"switch_{sw_high - 1}"
            final_switch_node = self._query_node(high_switch)
            final_switch_node.herald_switch(high_qnode, prev_sw_name)

    def __switch_tree(self, qnode_1_name, qnode_2_name):
        """
        Perform switching for a tree network topology.

        Configures direct herald switching if both nodes share the same switch.
        Otherwise, connects both to a super-switch and sets the super-switch
        to herald between them.

        Parameters
        ----------
        qnode_1_name : str
            Name of the first quantum node.
        qnode_2_name : str
            Name of the second quantum node.
        """
        # Step 1: Parse the ID from the string name
        id_1 = self.__qnode_re.findall(qnode_1_name)[0][1]
        id_2 = self.__qnode_re.findall(qnode_2_name)[0][1]

        # Step 2: sort x < y
        [low_id, high_id] = [int(x) for x in sorted([id_1, id_2])]

        # Step 3: Do routing checks
        sw_low = low_id // 3
        sw_high = high_id // 3

        # Convert to qnode names
        low_qnode = f"qnode_{low_id}"
        high_qnode = f"qnode_{high_id}"
        low_switch = f"switch_{sw_low}"
        high_switch = f"switch_{sw_high}"
        super_switch = "switch_3"

        # Step 4: Transform the IDs to switch names and send commands
        if sw_low == sw_high:
            # Get the switch objects
            switch_node = self._query_node(low_switch)

            # Switch herald
            switch_node.herald_switch(low_qnode, high_qnode)
        else:
            # Get the switch objects
            switch_low_node = self._query_node(low_switch)
            switch_high_node = self._query_node(high_switch)
            switch_super_node = self._query_node(super_switch)

            # Send switch signals
            switch_low_node.relay_switch(low_qnode, super_switch)
            switch_high_node.relay_switch(high_qnode, super_switch)
            switch_super_node.herald_switch(low_switch, high_switch)

    def __switch_simple(self, qnode_1_name, qnode_2_name):
        """
        Perform switching for a single-switch network topology.

        Always sends a herald switch command to ``switch_0`` between the
        two specified quantum nodes.

        Parameters
        ----------
        qnode_1_name : str
            Name of the first quantum node.
        qnode_2_name : str
            Name of the second quantum node.
        """
        switch_node = self._query_node("switch_0")
        switch_node.herald_switch(qnode_1_name, qnode_2_name)

    def __noop(self, _arg1, _arg2):
        pass
