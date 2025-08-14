import re
import uuid
import json
import logging

from netsquid.nodes import Node


class ControlNode(Node):
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
        # Send switching signals along the route to configure the network
        self.__switch_route(qnode_1_name, qnode_2_name)

        # TODO clean up the requests table if too big (i.e. leftover dropped requests)
        # Create request UUID
        request_uuid = str(uuid.uuid4())
        self.__uuid_queue[request_uuid] = (qnode_1_name, qnode_2_name)
        return request_uuid

    def register_nodes(self, node_list):
        # Register a list of nodes with the central registry
        for node in node_list:
            self.__registry[node.name] = node

    def _query_node(self, name):
        # For debugging purposes, allows directly querying the central registry
        return self.__registry.get(name)

    def __setup_callbacks(self):
        # Setup callbacks for port
        self.ports["switch_herald"].bind_input_handler(self.__handle_correction)

    def __handle_correction(self, msg):
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
        switch_node = self._query_node("switch_0")
        switch_node.herald_switch(qnode_1_name, qnode_2_name)

    def __noop(self, _arg1, _arg2):
        pass
