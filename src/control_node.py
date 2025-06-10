import re
import uuid
import json
import logging
import networkx as nx

from netsquid.nodes import Node


class ControlNode(Node):
    def __init__(self, id, network_type=None):
        # Central registry for all nodes, allows for name -> Object resolution
        self.__registry = {}

        # Setup ports
        super().__init__(f"CTRL[{id}]", port_names=["switch_herald"])

        self.__uuid_queue = {}
        self.__setup_callbacks()

        # Compile regexes for efficiency
        self.__switch_re = re.compile("^(switch_)([0-9]{1,})$")
        self.__qnode_re = re.compile("^(qnode_)([0-9]{1,})$")

        # Setup routing controls based on topology
        if network_type == "tree":
            self.__switch_route = self.__switch_ring
        elif network_type == "tree":
            self.__switch_route = self.__switch_tree
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

    def __calculate_route(self, qnode_1, target):
        # TODO calculate which switches need signals (and which signals) to connect qnode_1 to target for entanglement
        # Return map with switch: config, empty map for no route
        return {}

    def __setup_callbacks(self):
        # Setup callbacks for port
        self.ports["switch_herald"].bind_input_handler(self.__handle_correction)

    def __handle_correction(self, msg):
        dict_headers = json.loads(msg.meta.get("header", "{}"))
        request_uuid = dict_headers.pop("request_uuid", None)
        (qnode_1_name, qnode_2_name) = self.__uuid_queue.pop(request_uuid)

        logging.debug(
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
        [low_id, high_id] = sorted([id_1, id_2])

        # Step 3: Identify the switches
        sw_low = low_id // 2
        sw_high = high_id // 2

        # Step 3: Do routing checks
        # Step 4: Transform the IDs to switch names and send commands
        # Step 5: Profit?
        pass

    def __switch_tree(self, qnode_1_name, qnode_2_name):
        # Step 1: Parse the ID from the string name
        id_1 = self.__qnode_re.findall(qnode_1_name)[0][1]
        id_2 = self.__qnode_re.findall(qnode_2_name)[0][1]

        # Step 2: sort x < y
        [low_id, high_id] = sorted([id_1, id_2])

        # Step 3: Do routing checks
        # Step 4: Transform the IDs to switch names and send commands
        # Step 5: Profit?
        pass

    def __noop(self, _arg1, _arg2):
        pass
