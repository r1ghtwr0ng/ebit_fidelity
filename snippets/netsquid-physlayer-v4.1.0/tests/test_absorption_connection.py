import random

import netsquid as ns
from netsquid.qubits import qubitapi as qapi
from netsquid.qubits import operators as ops
from netsquid.nodes.node import Node
from netsquid.protocols import TimedNodeProtocol
from netsquid_physlayer.absorption_connection import NoResetAbsorptionConnection


class EmitPhotonProtocol(TimedNodeProtocol):
    def __init__(self, node, port_name, time_step, start_time=0.):
        super().__init__(node=node, time_step=time_step, start_time=start_time)
        self._port_name = port_name
        self._setup_ports()

        # Keep track of states used
        self._states = []
        # Keep track of midpoint bell meas
        self._midpoint_bell_outcomes = []

    @property
    def port_name(self):
        return self._port_name

    def _setup_ports(self):
        self.node.ports[self.port_name].bind_input_handler(self.process_data)

    def process_data(self, message):
        m1, m2 = message.items[0]
        m1 = int(m1)
        m2 = int(m2)
        self._midpoint_bell_outcomes.append((m1, m2))

    def exec_protocol(self):
        # Create a photon in random BB84 state
        t = random.randint(0, 1)
        x = random.randint(0, 1)
        self._states.append((t, x))
        photon = qapi.create_qubits(1)[0]
        if x == 1:
            qapi.operate(photon, ops.X)
        if t == 1:
            qapi.operate(photon, ops.H)
        self.send_msg([["emit", photon]])

    def send_msg(self, msg):
        self.node.ports[self.port_name].tx_output(msg)


def setup_protocols(time_step, delay):
    # Port name to use
    port_name = "absorp"

    # Setup nodes
    nodeA = Node("A", 0, port_names=[port_name])
    nodeB = Node("B", 1, port_names=[port_name])

    # Setup connection
    speed = 2e5
    ns = 1e9
    length = delay * speed / ns
    time_window = 1
    t0 = delay - time_window / 2
    conn = NoResetAbsorptionConnection(
        "Absorp",
        length_A=length,
        length_B=length,
        t0=t0,
        t_cycle=time_step,
    )

    # Connect
    nodeA.connect_to(nodeB, connection=conn, local_port_name=port_name, remote_port_name=port_name)

    # Setup protocols
    prot_A = EmitPhotonProtocol(nodeA, port_name, time_step=time_step)
    prot_B = EmitPhotonProtocol(nodeB, port_name, time_step=time_step)

    return prot_A, prot_B


def test():
    ns.sim_reset()

    time_step = 5.0
    delay = 10  # ns
    prot_A, prot_B = setup_protocols(time_step=time_step, delay=delay)
    prot_A.start()
    prot_B.start()

    num_photons = 1000
    ns.sim_run(time_step * num_photons)
    print(len(prot_A._states))
    print(len(prot_B._states))
    print(len(prot_A._midpoint_bell_outcomes))
    print(len(prot_B._midpoint_bell_outcomes))
    assert prot_A._midpoint_bell_outcomes == prot_B._midpoint_bell_outcomes
    truth_table = {
        0: {  # Z basis
            True: [(0, 0), (1, 0)],  # Equal states
            False: [(0, 1), (1, 1)],  # Not equal
        },
        1: {  # X basis
            True: [(0, 0), (0, 1)],  # Equal states
            False: [(1, 0), (1, 1)],  # Not equal
        },
    }
    for stateA, stateB, midpoint_outcome in zip(prot_A._states, prot_B._states, prot_A._midpoint_bell_outcomes):
        if stateA[0] == stateB[0]:  # Equal basis
            basis = stateA[0]
            equal = stateA[1] == stateB[1]
            print(f"{stateA}, {stateB}, {midpoint_outcome}")
            print(truth_table[basis][equal])
            assert midpoint_outcome in truth_table[basis][equal]
        # if stateA[0] == 1 and stateB[0] == 1:


if __name__ == "__main__":
    test()
