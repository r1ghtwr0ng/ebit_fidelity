import logging
import netsquid as ns
from netsquid.protocols import NodeProtocol, Signals

from utils import get_fidelities


class EntanglementProtocol(NodeProtocol):
    """
    A protocol to manage entanglement generation between two QPU nodes via an FSO switch.

    This protocol orchestrates the process of emitting qubits from two QPU nodes,
    routing them through an FSO switch, and collecting the results of the entanglement
    process, including simulation time, status, and fidelity.

    Parameters
    ----------
    alice_node : QPUNode
        The QPU node representing Alice, responsible for emitting qubits and receiving corrections.
    bob_node : QPUNode
        The QPU node representing Bob, responsible for emitting qubits and receiving corrections.
    fsoswitch_node : FSOSwitch
        The FSO switch node used to route quantum information between Alice and Bob.
    routing_table : dict
        A dictionary defining the routing logic for the FSO switch.

    Attributes
    ----------
    results : tuple or None
        Results of the entanglement protocol, including:
        - status: Success or failure of the entanglement process.
        - fidelity: Fidelity of the entangled state.
        - simtime: Simulation time at the completion of the protocol.

    Methods
    -------
    run()
        Executes the entanglement protocol, including qubit emission, simulation, and result collection.
    """

    def __init__(self, alice_node, bob_node, fsoswitch_node, routing_table):
        super().__init__(alice_node)  # Main protocol tied to Alice
        self.alice_node = alice_node
        self.bob_node = bob_node
        self.fsoswitch_node = fsoswitch_node
        self.routing_table = routing_table
        self.results = None

    def run(self):
        """
        Run the entanglement protocol.

        This method performs the following steps:
        1. Configures the routing table on the FSO switch.
        2. Triggers qubit emissions from Alice and Bob nodes.
        3. Executes the simulation until all events are processed.
        4. Collects and logs the status, fidelity, and simulation time.
        5. Signals completion of the protocol.

        Returns
        -------
        None
        """
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
            f"Simtime: {simtime} | Status: {status} | Fidelity: {fidelity:.3f}"
        )

        # Signal outcome
        if status:
            self.send_signal(Signals.SUCCESS, result=self.results)
        else:
            self.send_signal(Signals.FAIL, result=self.results)
