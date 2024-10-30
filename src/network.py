# Imports section
import numpy as np
import netsquid as ns
import pydynaa

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
        print(f"Detector out: {port_outcomes.items()}")
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

class QPUEntity(ns.pydynaa.Entity):
    """Represents a quantum processing unit (QPU) with program queue and callback functionality."""

    def __init__(self, name, correction, qbit_count=2, depolar_rate=0):
        super().__init__()
        self.name = name
        self.correction = correction
        self.processor = self._create_processor(name, qbit_count, depolar_rate)
        self.program_queue = deque()
        self._setup_callbacks()

    def _create_processor(self, name, qbit_count, depolar_rate):
        """Initialize the quantum processor for this QPU."""
        physical_instructions = [
            ns.components.qprocessor.PhysicalInstruction(ns.components.instructions.INSTR_INIT, duration=3, parallel=True),
            ns.components.qprocessor.PhysicalInstruction(ns.components.instructions.INSTR_H, duration=1, parallel=True),
            ns.components.qprocessor.PhysicalInstruction(ns.components.instructions.INSTR_X, duration=1, parallel=True),
            ns.components.qprocessor.PhysicalInstruction(ns.components.instructions.INSTR_Z, duration=1, parallel=True),
            ns.components.qprocessor.PhysicalInstruction(ns.components.instructions.INSTR_CNOT, duration=4, parallel=True, topology=[(0, 1)]),
            ns.components.qprocessor.PhysicalInstruction(ns.components.instructions.INSTR_EMIT, duration=1, parallel=True),
            ns.components.qprocessor.PhysicalInstruction(ns.components.instructions.INSTR_MEASURE, duration=7, parallel=False)
        ]
        memory_noise_model = ns.components.models.DepolarNoiseModel(depolar_rate=depolar_rate)
        processor = QuantumProcessor(name, num_positions=qbit_count,
                                     memory_noise_models=[memory_noise_model] * qbit_count,
                                     phys_instructions=physical_instructions)
        processor.add_ports(['correction'])
        return processor

    def _setup_callbacks(self):
        """Set up callback handling for when programs complete."""
        self.processor.set_program_done_callback(lambda: self.on_program_done(self.name, self.processor, self.program_queue))
        self.processor.set_program_fail_callback(lambda: self.on_program_done(self.name, self.processor, self.program_queue))
        self.processor.ports['correction'].bind_input_handler(lambda msg: self.correction_callback(msg, self.name, self.processor, self.correction))

    def add_program(self, program):
        """Add a program to the queue and execute if the processor is available."""
        if not self.processor.busy:
            self.processor.execute_program(program)
        else:
            self.program_queue.append(program)

    # Fucks sake, this might not work since it's not a static method
    @staticmethod
    def correction_callback(msg, name, qpu, correction):
        print(f"{name} received: {msg}")
        status = msg.items[0]
        if status == 1 and correction == 'X':
            # TODO
            print(f"{name} : Performing X correction")
            pass
        elif status == 2 and correction == 'Z':
            # TODO perform Z correction
            print(f"{name} : Performing Z correction")
            pass
        else:
            print(f"No correction needed for {name}")

    @staticmethod
    def on_program_done(name, qpu, queue):
        """Handle completion of a program, and process the next one if queued."""
        print(f"{name} program complete")
        if len(queue) > 0:
            next_program = queue.popleft()
            print(f"{name} queuing next program:", next_program)
            qpu.execute_program(next_program)

class EmitProgram(QuantumProgram):
    """Program to create a qubit and emit an entangled photon to the 'qout' port.
    """
    def __init__(self):
        super().__init__(num_qubits=2)

    def program(self):
        print("Fucking EMIT man")
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
        print("Fucking Z man")
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
        print("Fucking X man")
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

# Calculate the fidelity between two qubits in Alice and Bob's QPUs
def calculate_fidelity(alice_qpu, bob_qpu):
    """Calculate the fidelity between qubits at position 0 in Alice's and Bob's QPUs."""
    try:
        # Peek at the qubits in position 0 for both Alice and Bob
        q_alice = alice_qpu.processor.peek(positions=[0])[0]
        q_bob = bob_qpu.processor.peek(positions=[0])[0]
        
        # Calculate fidelities with respect to the Bell states
        fidelities = {
            'B00': qapi.fidelity([q_alice, q_bob], ks.b00, squared=True),
            'B01': qapi.fidelity([q_alice, q_bob], ks.b01, squared=True),
            'B10': qapi.fidelity([q_alice, q_bob], ks.b10, squared=True),
            'B11': qapi.fidelity([q_alice, q_bob], ks.b11, squared=True)
        }
        print(f"Fidelities between Alice and Bob qubits:", fidelities)
        return fidelities
    except Exception as e:
        print(f"Error calculating fidelity between Alice and Bob: {e}")
        return None

def run():
    # Reset simulation
    ns.sim_reset()
    
    # Integration with the BSMDetector
    alice = QPUEntity("AliceQPU", "X")
    bob = QPUEntity("BobQPU", "Z")

    # TODO add quantum fibre channel between QPU and detector
    # Connect QPU output ports to the detector input
    detector = BSMDetector("bsm_detector")
    alice.processor.ports['qout'].connect(detector.ports['qin0'])
    bob.processor.ports['qout'].connect(detector.ports['qin1'])

    # Connect detector correction outputs to QPU correction inputs
    detector.ports['cout0'].connect(alice.processor.ports['correction'])
    detector.ports['cout1'].connect(bob.processor.ports['correction'])

    # Start program
    alice.add_program(EmitProgram())
    bob.add_program(EmitProgram())
        
    # Run simulation
    stats = ns.sim_run()
    #print(stats)

if __name__ == "__main__":
    for _ in range(100):
        print('-------------------------------')
        run()
