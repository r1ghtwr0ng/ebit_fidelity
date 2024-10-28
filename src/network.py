# Imports section
import numpy as np
import netsquid as ns

from netsquid.nodes import Node
from netsquid.qubits import Operator
from netsquid.components import Component
from netsquid.components import QuantumChannel, ClassicalChannel, Message
from netsquid.components.qprogram import QuantumProgram
from netsquid.components.qdetector import QuantumDetector
from netsquid.components.qprocessor import QuantumProcessor, PhysicalInstruction
from netsquid.examples.repeater_chain import FibreDepolarizeModel
from netsquid.components.models import FibreDelayModel, FibreLossModel, DepolarNoiseModel

import netsquid.components.instructions as instr

# Debug prints
def print_output_message(message, port):
    # Print qubit, emission time and emission delay.
    print(f"Qbits ({port}): {message.items}, t={message.meta['emission_time']}, del={message.meta['emission_delay']}")

def debug_output(message, port):
    results_map = {
            0: False,
            1: True,
            2: True,
            3: False
    }
    status = message.items[0]
    print(f"Port: {port}, status: {results_map[status]} ({status})")

# Measurement operators for the beamsplitter
def create_meas_ops(visibility=1):
    """Sets the photon beamsplitter POVM measurements.

    We are assuming a lot here, see the Netsquid-Physlayer snippet for more info.

    Parameters
    ----------
    visibility : float, optional
        The visibility of the qubits in the detector.

    """
    mu = np.sqrt(visibility)
    s_plus = (np.sqrt(1 + mu) + np.sqrt(1 - mu)) / (2. * np.sqrt(2))
    s_min = (np.sqrt(1 + mu) - np.sqrt(1 - mu)) / (2. * np.sqrt(2))
    m0 = np.diag([1, 0, 0, 0])
    ma = np.array([[0, 0, 0, 0],
                   [0, s_plus, s_min, 0],
                   [0, s_min, s_plus, 0],
                   [0, 0, 0, np.sqrt(1 + mu * mu) / 2]],
                  dtype=complex)
    mb = np.array([[0, 0, 0, 0],
                   [0, s_plus, -1. * s_min, 0],
                   [0, -1. * s_min, s_plus, 0],
                   [0, 0, 0, np.sqrt(1 + mu * mu) / 2]],
                  dtype=complex)
    m1 = np.diag([0, 0, 0, np.sqrt(1 - mu * mu) / np.sqrt(2)])
    n0 = Operator("n0", m0)
    na = Operator("nA", ma)
    nb = Operator("nB", mb)
    n1 = Operator("n1", m1)
    return [n0, na, nb, n1]

class BSMDetector(QuantumDetector):
    """A component that performs Bell basis measurements.

    Measure two incoming qubits in the Bell basis if they
    arrive within the specified measurement delay.
    Only informs the connections that send a qubit of the measurement result.

    """

    def __init__(self, name, system_delay=0., dead_time=0., models=None,
                 output_meta=None, error_on_fail=False, properties=None):
        super().__init__(name, num_input_ports=2, num_output_ports=2,
                         meas_operators=create_meas_ops(),
                         system_delay=system_delay, dead_time=dead_time,
                         models=models, output_meta=output_meta,
                         error_on_fail=error_on_fail, properties=properties)
        self._sender_ids = []

    def preprocess_inputs(self):
        """Preprocess and capture the qubit metadata

        """
        super().preprocess_inputs()
        for port_name, qubit_list in self._qubits_per_port.items():
            if len(qubit_list) > 0:
                self._sender_ids.append(port_name[3:])

    def inform(self, port_outcomes):
        """Inform the MHP of the measurement result.

        We only send a result to the node that send a qubit.
        If the result is empty we change the result and header.

        Parameters
        ----------
        port_outcomes : dict
            A dictionary with the port names as keys
            and the post-processed measurement outcomes as values

        """
        for port_name, outcomes in port_outcomes.items():
            if len(outcomes) == 0:
                outcomes = ['TIMEOUT']
                header = 'error'
            else:
                header = 'photonoutcome'
            # Extract the ids from the port names (cout...)
            if port_name[4:] in self._sender_ids:
                msg = Message(outcomes, header=header, **self._meta)
                self.ports[port_name].tx_output(msg)

    def finish(self):
        """Clear sender ids after the measurement has finished."""
        super().finish()
        self._sender_ids.clear()

class EmitProgram(QuantumProgram):
    """Program to create a qubit and emit an entangled photon to the 'qout' port.

    """
    def __init__(self):
        super().__init__(num_qubits=2)

    def program(self):
        # Emit from q2 using q1
        q1, q2 = self.get_qubit_indices(self.num_qubits)
        self.apply(instr.INSTR_INIT, q1)
        self.apply(instr.INSTR_EMIT, [q1, q2])
        yield self.run()

def create_simple_processor(qpu_name, qbit_count=2, depolar_rate=0):
    """Create a quantum processor with basic operations for teleportation."""
    physical_instructions = [
        PhysicalInstruction(instr.INSTR_INIT, duration=3, parallel=True),
        PhysicalInstruction(instr.INSTR_H, duration=1, parallel=True),
        PhysicalInstruction(instr.INSTR_X, duration=1, parallel=True),
        PhysicalInstruction(instr.INSTR_Z, duration=1, parallel=True),
        PhysicalInstruction(instr.INSTR_CNOT, duration=4, parallel=True, topology=[(0, 1)]),
        PhysicalInstruction(instr.INSTR_EMIT, duration=1, parallel=True),
        PhysicalInstruction(instr.INSTR_MEASURE, duration=7, parallel=False)
    ]
    memory_noise_model = DepolarNoiseModel(depolar_rate=depolar_rate)
    processor = QuantumProcessor(qpu_name, num_positions=qbit_count, memory_noise_models=[memory_noise_model]*2, 
                                 phys_instructions=physical_instructions)
    return processor

def run():
    # Run simulation
    ns.sim_reset()

    # Setup BSM detector
    detector = BSMDetector("test")
    detector.ports['cout0'].bind_output_handler(lambda msg: debug_output(msg, 'cout0'))
    detector.ports['cout1'].bind_output_handler(lambda msg: debug_output(msg, 'cout1'))

    # Instantiate the QPU units for Alice and Bob
    qpu_a = create_simple_processor("qpu_a", 2, 0) 
    qpu_a.ports['qout'].connect(detector.ports['qin0'])
    qpu_b = create_simple_processor("qpu_b", 2, 0) 
    qpu_b.ports['qout'].connect(detector.ports['qin1'])

    # Setup & run program
    prog = EmitProgram()
    qpu_a.execute_program(prog)
    qpu_b.execute_program(prog)
    
    stats = ns.sim_run()
    #print(stats)

if __name__ == "__main__":
    for _ in range(10):
        print('-------------------------------')
        run()
