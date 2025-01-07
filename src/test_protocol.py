import logging
import netsquid as ns
from netsquid.protocols import NodeProtocol, Signals

from utils import get_fidelities
from qpu_entity import QPUNode
from fso_switch import FSOSwitch


class QuantumEmitProtocol(NodeProtocol):
    def __init__(self, node, req_id):
        super().__init__(node)
        self.req_id = req_id

    def run(self):
        # Register and emit
        self.node.register_id(self.req_id)
        self.node.emit()
        yield self.await_signal(self.node, Signals.SUCCESS)
        self.send_signal(Signals.SUCCESS)


class FSOSwitchProtocol(NodeProtocol):
    def __init__(self, node, routing_table):
        super().__init__(node)
        self.routing_table = routing_table

    def run(self):
        # Set the switch routing
        self.node.switch(self.routing_table)
        self.send_signal(Signals.SUCCESS)


class SimulationProtocol(NodeProtocol):
    def __init__(self, alice_node, bob_node, fsoswitch_node, routing_table):
        super().__init__(alice_node)  # Main protocol tied to Alice
        self.alice_node = alice_node
        self.bob_node = bob_node
        self.fsoswitch_node = fsoswitch_node
        self.routing_table = routing_table
        self.results = None

    def run(self):
        # Set up routing table
        self.fsoswitch_node.switch(self.routing_table)

        # Trigger emissions from Alice and Bob
        self.alice_node.emit()
        self.bob_node.emit()

        # Run the simulation
        logging.debug("Starting simulation")
        _stats = ns.sim_run()
        simtime = ns.sim_time()

        # Collect results
        status, fidelity = get_fidelities(self.alice_node, self.bob_node)
        self.results = (status, fidelity, simtime)
        logging.debug(
            f"Simulation complete at t={simtime}. Status: {status}, Fidelity: {fidelity:.3f}"
        )

        # Signal completion
        self.send_signal(Signals.SUCCESS)
