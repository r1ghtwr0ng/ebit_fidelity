import uuid
import json
import logging
import numpy as np

from netsquid.nodes import Node
import netsquid.components.instructions as instr
from netsquid.components.models.qerrormodels import T1T2NoiseModel
from netsquid.components.qprocessor import QuantumProcessor, PhysicalInstruction


class QPUNode(Node):
    """
    Represents an entity (i.e. the legendary Alice and Bob) with a quantum processing
    unit (QPU) with a program queue and callback functionality. If a program needs to be
    executed it should be added to the queue using the add_program method.

    Qubit mapping:
    0 - Emission qubit
    1 - Communications qubit, entangled with emission qubit
    2 - Shielded qubit, used for storing & distilling entanglement

    Parameters
    ----------
    qbit_count : int, optional
        Number of qubits in the processor, by default 2.
    depolar_rate : float, optional
        Depolarization rate for the noise model, by default 0.
    """

    def __init__(self, qnode_id, ideal_qpu, qbit_count=3):
        # Changed: generate name from ID
        self.id = qnode_id
        name = f"qnode_{qnode_id}"
        super().__init__(name, port_names=["corrections"])

        # The last qubit slot is used for photon emission into fibre
        self.processor = self.__create_processor(qbit_count, ideal_qpu)
        self.__setup_callbacks()

        # Keep track of qubit mappings
        self.emit_idx = 0
        self.comm_idx = 1
        self.shielded_idx = 2

        # Fetch logger
        self.__logger = logging.getLogger("qpu_logger")

    # ======== PRIVATE METHODS ========
    # Helper function to create a simple QPU with a few useful instructions
    def __create_processor(self, qbit_count, ideal_qpu):
        """
        Private helper method used to initialize the quantum processor for the entity.
        We have nonphysical instructions as we use an abstract QPU architecture.

        Communication qubit coherence times:
        T1: 2.68ms
        T2: 1ms

        Memory (shielded) qubit coherence times:
        T1: inf
        T2: 3.5ms

        Parameters
        ----------
        ideal_qpu : bool
            Whether the QPU has noise and delay models applied.
        qbit_count : int
            Number of qubits in the processor.
        depolar_rate : float
            Depolarization rate for the noise model.

        Returns
        -------
        QuantumProcessor
            A configured quantum processor with fallback to nonphysical instructions.
        """
        qproc_name = f"qproc_{self.id}"

        if ideal_qpu:
            # Build ideal QPU
            processor = QuantumProcessor(
                qproc_name,
                num_positions=qbit_count,
                fallback_to_nonphysical=True,
            )
            processor.add_ports(["qout_hdr", "qout0_hdr"])
        else:
            # Build a noisy QPU
            memory_noise_models = [
                None,  # Utility qubit: no noise applied
                T1T2NoiseModel(
                    T1=2_680_000, T2=1_000_000
                ),  # Communication qubit: high error (short coherence times)
                T1T2NoiseModel(
                    T1=np.inf, T2=3_500_000
                ),  # Shielded qubit: low error (long coherence times)
            ]
            processor = QuantumProcessor(
                qproc_name,
                num_positions=qbit_count,
                memory_noise_models=memory_noise_models,
                phys_instructions=None,
                fallback_to_nonphysical=False,
            )
            processor.add_ports(["qout_hdr", "qout0_hdr"])
            processor.add_physical_instruction(
                PhysicalInstruction(instruction=instr.INSTR_INIT, duration=200.0)
            )
            processor.add_physical_instruction(
                PhysicalInstruction(
                    instruction=instr.INSTR_X,
                    duration=50.0,
                    # quantum_noise_model=T1T2NoiseModel(T1=0.5, T2=0.3),
                )
            )
            processor.add_physical_instruction(
                PhysicalInstruction(
                    instruction=instr.INSTR_Y,
                    duration=50.0,
                    # quantum_noise_model=T1T2NoiseModel(T1=0.5, T2=0.3),
                )
            )
            processor.add_physical_instruction(
                PhysicalInstruction(instruction=instr.INSTR_EMIT, duration=20.0)
            )
            processor.add_physical_instruction(
                PhysicalInstruction(instruction=instr.INSTR_SWAP, duration=900.0)
            )
            processor.add_physical_instruction(
                PhysicalInstruction(
                    instruction=instr.INSTR_CNOT,
                    duration=300.0,
                    # quantum_noise_model=DepolarNoiseModel(
                    #    depolar_rate=1e6, time_independent=False
                    # ),
                )
            )
            processor.add_physical_instruction(
                PhysicalInstruction(
                    instruction=instr.INSTR_MEASURE, duration=400.0, parallel=True
                )
            )
        return processor

    # Helper for setting up the callbacks and handlers
    def __setup_callbacks(self):
        """Set up callback handling for when programs complete."""
        self.processor.ports["qout"].bind_output_handler(
            self.__setup_header_wrapper, tag_meta=True
        )
        self.processor.ports["qout0"].bind_output_handler(
            self.__setup_header_wrapper, tag_meta=True
        )

    def __debug(self, msg):
        port = msg.meta.get("rx_port_name", "missing_port_metadata")
        self.__logger.debug(f"Received message on port: {port}, MSG: {msg}")

    def __setup_header_wrapper(self, msg):
        """
        Add metadata headers to outbound messages for routing and identification.

        Parameters
        ----------
        msg : object
            The message object containing metadata and payload to be transmitted.

        Returns
        -------
        None
            Modifies the message in place by adding a JSON-serialized header.
        """
        port = msg.meta.get("rx_port_name", "missing_port_metadata")
        event_id = msg.meta["put_event"].id

        if self.request_uuid is None:
            self.__logger.error(
                f"[Emission header callback]: {self.name}, request_uuid not set for port {port}, event_id: {event_id}"
            )
            # TODO consider throwing an error
        else:
            header = {"event_id": event_id, "request_uuid": self.request_uuid}
            msg.meta["header"] = json.dumps(header)
            self.processor.ports[f"{port}_hdr"].tx_output(msg)
            self.request_uuid = None  # Remove old UUID once request is transmitted

    # Set UUID for next message coming out of the emission port
    def set_emit_uuid(self, request_uuid):
        self.request_uuid = request_uuid
