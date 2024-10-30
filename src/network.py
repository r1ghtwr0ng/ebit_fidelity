# Imports section
import numpy as np
import netsquid as ns

from collections import deque
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
import netsquid.qubits.ketstates as ks
from netsquid.qubits import qubitapi as qapi

# ---- CLASSES ----
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

class CorrectZProgram(QuantumProgram):
    """Program to apply a Pauli Z correction to a shared Bell state
    """
    def __init__(self):
        super().__init__(num_qubits=1)

    def program(self):
        # Emit from q2 using q1
        q1 = self.get_qubit_indices(self.num_qubits)
        self.apply(instr.INSTR_Z, q1)
        yield self.run()

class CorrectXProgram(QuantumProgram):
    """Program to apply a Pauli X correction to a shared Bell state
    """
    def __init__(self):
        super().__init__(num_qubits=1)

    def program(self):
        # Emit from q2 using q1
        q1 = self.get_qubit_indices(self.num_qubits)
        self.apply(instr.INSTR_X, q1)
        yield self.run()

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
    processor.add_ports(['correction'])
    return processor

# ---- CALLBACKS ----
# Callback for scheduling corrections
def handle_corrections(message, port, qpu_x, qpu_z, qpu_x_queue, qpu_z_queue):
    status = message.items[0]
    if status == 1:
        print(f"Recv: {status} on port: {port}, performing X correction")
        execute_program_with_queue(qpu_x, CorrectXProgram(), qpu_x_queue)
    elif status == 2:
        print(f"Recv: {status} on port: {port}, performing Z correction")
        execute_program_with_queue(qpu_z, CorrectZProgram(), qpu_z_queue)
    else:
        print(f"Recv: {status} on port: {port}, bad state, no corrections performed")

# ---- QUEUE IMPLEMENTATION ----
# Helper to manage program queue execution
def execute_program_with_queue(qpu, program, queue):
    if not qpu.busy:
        qpu.execute_program(program)
    else:
        queue.append(program)

def on_program_done(msg, target_qpu, second_qpu, queue=[]):
    # Execute the next program in the queue if available
    if len(queue) > 0:
        next_program = queue.popleft()
        print(f"Queuing next program {next_program}")
        execute_program_with_queue(target_qpu, next_program, queue)
    try:
        print(msg, end=' | ')
        q0 = target_qpu.peek(positions=0)[0]
        q1 = second_qpu.peek(positions=0)[0]
        f0 = qapi.fidelity([q0, q1], ks.b00, squared=True)
        f1 = qapi.fidelity([q0, q1], ks.b01, squared=True)
        f2 = qapi.fidelity([q0, q1], ks.b10, squared=True)
        f3 = qapi.fidelity([q0, q1], ks.b11, squared=True)
        print(f"B00: {f0}, B01: {f1}, B10: {f2}, B11: {f3}")
    except Exception as e:
        print(f"Error accessing qubits: {e}")

def run():
    # Initialize program queues
    qpu_a_queue = deque()
    qpu_b_queue = deque()

    # Run simulation
    ns.sim_reset()

    # Setup BSM detector
    detector = BSMDetector("bsm_detector")
    
    # Instantiate the QPU units for Alice and Bob
    qpu_a = create_simple_processor("qpu_a", 2, 0) 
    qpu_b = create_simple_processor("qpu_b", 2, 0) 
    qpu_a.ports['qout'].connect(detector.ports['qin0'])
    qpu_b.ports['qout'].connect(detector.ports['qin1'])
    
    # Setup event handlers
    qpu_a.set_program_done_callback(on_program_done, "Callback hit on A", qpu_a, qpu_b, qpu_a_queue)
    qpu_b.set_program_done_callback(on_program_done, "Callback hit on B", qpu_b, qpu_a, qpu_b_queue)
    qpu_a.set_program_fail_callback(on_program_done, "Callback (FAIL) hit on A", qpu_a, qpu_b, qpu_a_queue)
    qpu_b.set_program_fail_callback(on_program_done, "Callback (FAIL) hit on B", qpu_b, qpu_a, qpu_b_queue)

    # Bind the output ports to the QPU so we can do qubit corrections
    detector.ports['cout0'].connect(qpu_a.ports['correction'])
    detector.ports['cout1'].connect(qpu_b.ports['correction'])
    qpu_a.ports['correction'].bind_input_handler(lambda msg: handle_corrections(msg, 'cout0', qpu_a, qpu_b, qpu_a_queue, qpu_b_queue))
    qpu_b.ports['correction'].bind_input_handler(lambda msg: handle_corrections(msg, 'cout1', qpu_a, qpu_b, qpu_a_queue, qpu_b_queue))
    
    # Setup & run program
    prog = EmitProgram()
    execute_program_with_queue(qpu_a, EmitProgram(), qpu_a_queue)
    execute_program_with_queue(qpu_b, EmitProgram(), qpu_b_queue)
    stats = ns.sim_run()
    #print(stats)

if __name__ == "__main__":
    for _ in range(100):
        print('-------------------------------')
        run()
