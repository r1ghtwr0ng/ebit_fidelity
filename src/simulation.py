import gc
import math
import logging
import pandas as pd
import netsquid as ns

from itertools import combinations

from qpu_node import QPUNode
from fso_switch import FSOSwitch
from control_node import ControlNode
from protocols import ContinuousDistillationProtocol
from netsquid.protocols import Signals
from netsquid.nodes.network import Network
from netsquid.components import ClassicalChannel
from netsquid.nodes.connections import DirectConnection
from netsquid.components.models.delaymodels import FibreDelayModel


def setup_tree_network(
    dampening_parameter,
    routing,
    ideal_switch,
    ideal_qpu,
    visibility,
    idx_1,
    idx_2,
    qpu_count=9,
):
    """
    Setup a tree topology network of FSO switches and QPUs.

    Parameters
    ----------
    dampening_parameter : float
        Photon state amplitude dampening parameter applied to FSO channels.
    routing : dict
        Switch configuration (e.g. {"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"}).
    ideal_switch : bool
        If True, use an ideal switch model (no loss, no noise).
    ideal_qpu : bool
        If True, use ideal QPU nodes.
    visibility : float
        Photon indistinguishability (HOM visibility) (0–1).
    idx_1 : int
        Index of the first QPU to include in the network (memory optimization).
    idx_2 : int
        Index of the second QPU to include in the network (memory optimization).
    qpu_count : int, optional
        Total number of QPUs (default is 9).

    Returns
    -------
    Network
        The constructed tree network.
    ControlNode
        The control node managing the network.
    list of QPUNode
        The selected QPU nodes corresponding to idx_1 and idx_2.

    Examples
    --------
    >>> network, ctrl_node, [q1, q2] = setup_tree_network(
    ...     dampening_parameter=0.1,
    ...     routing={"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"},
    ...     ideal_switch=False,
    ...     ideal_qpu=True,
    ...     visibility=0.9,
    ...     idx_1=0,
    ...     idx_2=5,
    ...     qpu_count=9
    ... )
    """
    # Hardcoded vars, maybe we can dynamically determine the fso_count
    fso_count = 4

    # Setup control node
    ctrl_node = ControlNode(id=0, network_type="tree")
    ctrl_port = ctrl_node.ports["switch_herald"]
    tree_network = Network("tree_network")

    # Determine herald ports depending on switch configuration
    if routing != {"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"}:
        # TODO throw
        pass

    herald_ports = ["qout0", "qout1"]

    # Create FSO switches
    fsoswitch_nodes = []
    for i in range(fso_count):
        fsoswitch_node = FSOSwitch(
            switch_id=i,
            ctrl_port=ctrl_port,
            dampening_parameter=dampening_parameter,
            ideal=ideal_switch,
            herald_ports=herald_ports,
            visibility=visibility,
        )
        fsoswitch_nodes.append(fsoswitch_node)

    # Create QPU nodes and connect to switch ports
    qpu_nodes = []
    for i in range(qpu_count):
        if i == idx_1 or i == idx_2:
            inbound_port = f"qin{i%3}"
            qpu_node = QPUNode(qnode_id=i, ideal_qpu=ideal_qpu)
            qpu_node.processor.ports["qout_hdr"].connect(
                fsoswitch_nodes[i // 3].ports[inbound_port]
            )
            qpu_nodes.append(qpu_node)
            fsoswitch_nodes[i // 3].register(qpu_node.name, inbound_port)

    # Connect the FSO switches in a heirerachy
    for i in range(3):
        inbound_port = f"qin{i}"
        fsoswitch_nodes[i].ports["qout2"].connect(
            fsoswitch_nodes[3].ports[inbound_port]
        )
        # Forward and reverse port lookup registration
        fsoswitch_nodes[3].register(fsoswitch_nodes[i].name, inbound_port)
        fsoswitch_nodes[i].register(fsoswitch_nodes[3].name, "qout2")

    # Add nodes to network
    all_nodes = qpu_nodes + fsoswitch_nodes
    tree_network.add_nodes(nodes=all_nodes)

    # Register nodes with the control node's registry for UUID lookups
    ctrl_node.register_nodes(all_nodes)
    return tree_network, ctrl_node, qpu_nodes


def setup_ring_network(
    dampening_parameter,
    routing,
    ideal_switch,
    ideal_qpu,
    visibility,
    idx_1,
    idx_2,
    qpu_count=8,
):
    """
    Setup a ring topology network of FSO switches and QPUs.

    Parameters
    ----------
    dampening_parameter : float
        Photon state amplitude dampening parameter applied to FSO channels.
    routing : dict
        Switch configuration (e.g. {"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"}).
    ideal_switch : bool
        If True, use an ideal switch model (no loss, no noise).
    ideal_qpu : bool
        If True, use ideal QPU nodes.
    visibility : float
        Photon indistinguishability (HOM visibility) (0–1).
    idx_1 : int
        Index of the first QPU to include in the network (memory optimization).
    idx_2 : int
        Index of the second QPU to include in the network (memory optimization).
    qpu_count : int, optional
        Total number of QPUs (default is 8).

    Returns
    -------
    Network
        The constructed ring network.
    ControlNode
        The control node managing the network.
    list of QPUNode
        The selected QPU nodes corresponding to idx_1 and idx_2.

    Examples
    --------
    >>> network, ctrl_node, [q1, q2] = setup_ring_network(
    ...     dampening_parameter=0.05,
    ...     routing={"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"},
    ...     ideal_switch=True,
    ...     ideal_qpu=False,
    ...     visibility=0.85,
    ...     idx_1=2,
    ...     idx_2=6,
    ...     qpu_count=8
    ... )
    """
    # Hardcoded vars, maybe we can dynamically determine the fso_count
    fso_count = math.ceil(qpu_count / 2)

    # Setup control node
    ctrl_node = ControlNode(id=0, network_type="ring")
    ctrl_port = ctrl_node.ports["switch_herald"]
    ring_network = Network("ring_network")

    # Determine herald ports depending on switch configuration
    if routing != {"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"}:
        # TODO throw
        pass

    herald_ports = ["qout0", "qout1"]

    # Create FSO switches
    fsoswitch_nodes = []
    for i in range(fso_count):
        fsoswitch_node = FSOSwitch(
            switch_id=i,
            ctrl_port=ctrl_port,
            dampening_parameter=dampening_parameter,
            ideal=ideal_switch,
            herald_ports=herald_ports,
            visibility=visibility,
        )
        fsoswitch_nodes.append(fsoswitch_node)

    # Create QPU nodes and connect to switch ports
    qpu_nodes = []
    for i in range(qpu_count):
        if i == idx_1 or i == idx_2:
            inbound_port = f"qin{i%2}"
            qpu_node = QPUNode(qnode_id=i, ideal_qpu=ideal_qpu)
            qpu_node.processor.ports["qout_hdr"].connect(
                fsoswitch_nodes[i // 2].ports[inbound_port]
            )
            qpu_nodes.append(qpu_node)
            fsoswitch_nodes[i // 2].register(qpu_node.name, inbound_port)

    # Connect the FSO switches in a heirerachy
    for curr_switch in range(fso_count):
        inbound_port = "qin2"
        outbound_port = "qout2"
        next_switch = (curr_switch + 1) % fso_count
        fsoswitch_nodes[curr_switch].ports[outbound_port].connect(
            fsoswitch_nodes[next_switch].ports[inbound_port]
        )
        # Register forward and reverse port lookups
        fsoswitch_nodes[next_switch].register(
            fsoswitch_nodes[curr_switch].name, inbound_port
        )
        fsoswitch_nodes[curr_switch].register(
            fsoswitch_nodes[next_switch].name, outbound_port
        )

    # Add nodes to network
    all_nodes = qpu_nodes + fsoswitch_nodes
    ring_network.add_nodes(nodes=all_nodes)

    # Register nodes with the control node's registry for UUID lookups
    ctrl_node.register_nodes(all_nodes)
    return ring_network, ctrl_node, qpu_nodes


def setup_simple_network(
    dampening_parameter,
    routing,
    ideal_switch,
    ideal_qpu,
    visibility,
):
    """
    Setup a simple 2-node network connected via a single FSO switch.

    Parameters
    ----------
    dampening_parameter : float
        Photon state amplitude dampening parameter applied to FSO channels.
    routing : dict
        Switch configuration (e.g. {"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"}).
    ideal_switch : bool
        If True, use an ideal switch model (no loss, no noise).
    ideal_qpu : bool
        If True, use ideal QPU nodes.
    visibility : float
        Photon indistinguishability (HOM visibility) (0–1).

    Examples
    --------
    >>> network, ctrl_node, [qnode_1, qnode_2] = setup_simple_network(
    ...     dampening_parameter=0.1,
    ...     routing={"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"},
    ...     ideal_switch=False,
    ...     ideal_qpu=False,
    ...     visibility=0.9
    ... )
    """

    # Setup control node and network
    ctrl_node = ControlNode(id=0, network_type="simple")
    ctrl_port = ctrl_node.ports["switch_herald"]
    network = Network("switch_test_network")

    # Determine herald ports depending on switch configuration
    long_paths = routing == {"qin0": "qout2", "qin1": "qout1", "qin2": "qout0"}
    if long_paths:
        herald_ports = ["qout0", "qout2"]
    else:
        herald_ports = ["qout1", "qout2"]

    # Create nodes
    node_1 = QPUNode(qnode_id=0, ideal_qpu=ideal_qpu)
    node_2 = QPUNode(qnode_id=1, ideal_qpu=ideal_qpu)
    fsoswitch_node = FSOSwitch(
        switch_id=0,
        ctrl_port=ctrl_port,
        dampening_parameter=dampening_parameter,
        ideal=ideal_switch,
        herald_ports=herald_ports,
        visibility=visibility,
    )

    # Connect node-level ports
    node_1.processor.ports["qout_hdr"].connect(fsoswitch_node.ports["qin0"])
    fsoswitch_node.register(node_1.name, "qin0")

    if long_paths:
        node_2.processor.ports["qout_hdr"].connect(fsoswitch_node.ports["qin2"])
        fsoswitch_node.register(node_2.name, "qin2")
    else:
        node_2.processor.ports["qout_hdr"].connect(fsoswitch_node.ports["qin1"])
        fsoswitch_node.register(node_2.name, "qin1")

    # Add nodes to network and register with control node
    all_nodes = [node_1, node_2, fsoswitch_node]
    network.add_nodes(nodes=all_nodes)
    ctrl_node.register_nodes(all_nodes)

    # Group QNodes and FSO switches in two lists
    return network, ctrl_node, [node_1, node_2]


def single_run(
    switch_routing,
    dampening_parameter,
    ideal_switch,
    ideal_qpu,
    visibility,
    max_attempts,
    max_distillations,
    run,
):
    """
    Run a single simulation of the continuous distillation protocol
    over all QPU pairs in a given network topology.

    Parameters
    ----------
    switch_routing : dict
        Switch configuration (e.g. {"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"}).
    dampening_parameter : float
        Photon state amplitude dampening parameter applied to FSO channels.
    ideal_switch : bool
        If True, use an ideal switch model (no loss, no noise).
    ideal_qpu : bool
        If True, use ideal QPU nodes.
    visibility : float
        Photon indistinguishability (HOM visibility) (0–1).
    max_attempts : int
        Maximum number of entanglement generation attempts.
    max_distillations : int
        Maximum number of distillation rounds attempted.
    run : int
        Run index identifier.

    Returns
    -------
    pd.DataFrame
        Metadata dataframe summarizing run statistics.
    pd.DataFrame
        Event-level dataframe with detailed protocol execution logs.

    Examples
    --------
    >>> metadata_df, events_df = single_run(
    ...     switch_routing={"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"},
    ...     dampening_parameter=0.1,
    ...     max_attempts=50,
    ...     max_distillations=10,
    ...     ideal_switch=False,
    ...     ideal_qpu=False,
    ...     visibility=0.9,
    ...     run=0
    ... )
    """

    # Fetch logger
    logger = logging.getLogger("sim_logger")

    # Initialize simulation
    ns.sim_reset()

    # Dataframe lists
    all_metadata = []
    all_event_dataframes = []

    # Benchmark different pairs
    qpu_count = 8  # 8 for ring, 9 for tree
    qpu_indices = list(combinations(range(qpu_count), 2))
    for i, j in qpu_indices:
        # Setup network connections
        network, ctrl_node, [qnode_1, qnode_2] = setup_tree_network(
            routing=switch_routing,
            dampening_parameter=dampening_parameter,
            visibility=visibility,
            ideal_switch=ideal_switch,
            ideal_qpu=ideal_qpu,
            idx_1=i,
            idx_2=j,
            qpu_count=qpu_count,
        )

        # Get nodes from indices
        logger.info(f"Testing: QPU 1: {qnode_1.name} with QPU 2: {qnode_2.name}")

        # Create and start the simulation protocol
        distill_proto = ContinuousDistillationProtocol(
            ctrl_node,
            qnode_1,
            qnode_2,
            switch_routing,
            max_attempts=max_attempts,
            max_distillations=max_distillations,
        )

        # Run protocol(s)
        distill_proto.start()

        # Run the simulation
        stats = ns.sim_run()
        quantum_ops = stats.data["quantum_ops_total"]
        simtime = ns.sim_time()

        # Get the protocol status
        protocol_status, full_events_dataframe = distill_proto.get_signal_result(
            Signals.FINISHED
        )
        logger.info(
            f"[Simulation] Continuous distill protocol returned: {protocol_status}"
        )

        # Make sure to reset the protocol
        distill_proto.reset()

        # Construct simulation statistics metadata dataframe
        run_id = f"{run}_{dampening_parameter}_{visibility}"
        run_metadata = {
            "run": run,
            "qnode_1": qnode_1.name,
            "qnode_2": qnode_2.name,
            "visibility": visibility,
            "dampening_parameter": dampening_parameter,
            "run_id": run_id,
            "ideal_switch": ideal_switch,
            "ideal_qpu": ideal_qpu,
            "status": protocol_status,
            "simtime": simtime,
            "quantum_ops": quantum_ops,
        }
        run_metadata_df = pd.DataFrame([run_metadata])

        # Fill in the run information for the full dataframe
        full_events_dataframe["run"] = run
        full_events_dataframe["visibility"] = visibility
        full_events_dataframe["dampening_parameter"] = dampening_parameter
        full_events_dataframe["run_id"] = run_id

        # Append data to list
        all_metadata.append(run_metadata_df)
        all_event_dataframes.append(full_events_dataframe)

        # Reset the nodes and simulation
        qnode_1.reset()
        qnode_2.reset()
        network.reset()
        ctrl_node.reset()
        del qnode_1
        del qnode_2
        del network
        del ctrl_node
        ns.sim_reset()

        logger.info("Reset node processors and simulation")

    # Combine list of pandas dataframes into a single dataframe
    run_metadata_df = pd.concat(all_metadata, ignore_index=True)
    full_events_dataframe = pd.concat(all_event_dataframes, ignore_index=True)

    # Return results
    return run_metadata_df, full_events_dataframe


def batch_run(
    switch_routing,
    batch_size,
    ideal_switch,
    ideal_qpu,
    dampening_parameters,
    visibilities,
    max_attempts,
    max_distillations,
):
    """
    Run multiple simulations across batches of parameter combinations.

    Parameters
    ----------
    switch_routing : dict
        Switch configuration (e.g. {"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"}).
    batch_size : int
        Number of independent runs per parameter combination.
    dampening_parameters : list[float]
        List of photon state amplitude dampening parameter applied to FSO channels.
    visibilities : list[float]
        List of photon indistinguishability (HOM visibility) parameters.
    ideal_switch : bool
        If True, use an ideal switch model (no loss, no noise).
    ideal_qpu : bool
        If True, use ideal QPU nodes.
    max_attempts : int
        Maximum number of entanglement generation attempts.
    max_distillations : int
        Maximum number of distillation rounds attempted.

    Returns
    -------
    pd.DataFrame
        Combined metadata dataframe across all runs.
    pd.DataFrame
        Combined event dataframe across all runs.

    Examples
    --------
    >>> metadata_df, events_df = batch_run(
    ...     switch_routing={"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"},
    ...     batch_size=3,
    ...     ideal_switch=False,
    ...     ideal_qpu=False,
    ...     dampening_parameters=[0.05, 0.1],
    ...     visibilities=[0.8, 0.9],
    ...     max_attempts=100,
    ...     max_distillations=20
    ... )
    """
    total_params = len(dampening_parameters) * len(visibilities)
    print(f"[i] Starting processing of {total_params} parameter combinations")

    # Prepare all parameter combinations
    param_combinations = [
        (
            batch_size,
            switch_routing,
            dampening_parameter,
            visibility,
            ideal_switch,
            ideal_qpu,
            max_attempts,
            max_distillations,
            i * len(visibilities) + j,
        )
        for i, dampening_parameter in enumerate(dampening_parameters)
        for j, visibility in enumerate(visibilities)
    ]

    # Use a custom processing method to ensure better memory management
    all_event_dfs = []
    all_metadata_dfs = []

    # Split parameter combinations into chunks to control parallel processing
    def process_chunk(chunk):
        # Debug
        print(f"[DEBUG] New workload: {len(chunk)} allocated")

        # Create a new pool for each chunk to ensure clean process lifecycle
        chunk_results = [batch_proc(*params) for params in chunk]

        # Collect results from this chunk
        chunk_event_dfs = []
        chunk_metadata_dfs = []
        for batch_event_dfs, batch_metadata_dfs in chunk_results:
            chunk_event_dfs.extend(batch_event_dfs)
            chunk_metadata_dfs.extend(batch_metadata_dfs)

        # Trigger garbage collection
        gc.collect()

        return chunk_event_dfs, chunk_metadata_dfs

    # Process parameters in smaller chunks
    for i in range(0, len(param_combinations)):
        chunk = param_combinations[i : i + 1]
        chunk_event_dfs, chunk_metadata_dfs = process_chunk(chunk)

        all_event_dfs.extend(chunk_event_dfs)
        all_metadata_dfs.extend(chunk_metadata_dfs)

        # Additional garbage collection between chunks
        gc.collect()

    # Concatenate all dataframes into a single entity
    df_all_events = pd.concat(all_event_dfs, ignore_index=True)
    df_all_metadata = pd.concat(all_metadata_dfs, ignore_index=True)

    # Final garbage collection
    gc.collect()

    # Print completion message
    print(
        f"[i] Processing complete: {total_params}/{total_params} parameter combinations"
    )

    return df_all_metadata, df_all_events


# Single worker process instance
def batch_proc(
    batch_size,
    switch_routing,
    dampening_parameter,
    visibility,
    max_attempts,
    max_distillations,
    ideal_switch,
    ideal_qpu,
    run_id,
):
    """
    Worker function for executing a batch of single_run simulations
    for a given parameter set.

    Parameters
    ----------
    batch_size : int
        Number of independent runs to perform.
    switch_routing : dict
        Switch configuration (e.g. {"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"}).
    dampening_parameter : float
        Photon state amplitude dampening parameter applied to FSO channels.
    visibility : float
        Photon indistinguishability (HOM visibility) parameters.
    max_attempts : int
        Maximum number of entanglement generation attempts.
    max_distillations : int
        Maximum number of distillation rounds attempted.
    ideal_switch : bool
        If True, use an ideal switch model (no loss, no noise).
    ideal_qpu : bool
        If True, use ideal QPU nodes.
    run_id : int
        Identifier for the parameter set.

    Returns
    -------
    list[pd.DataFrame]
        List of event-level dataframes for all runs in the batch.
    list[pd.DataFrame]
        List of metadata dataframes for all runs in the batch.

    Examples
    --------
    >>> event_dfs, metadata_dfs = batch_proc(
    ...     batch_size=2,
    ...     switch_routing={"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"},
    ...     dampening_parameter=0.1,
    ...     max_attempts=50,
    ...     max_distillations=10,
    ...     ideal_switch=False,
    ...     ideal_qpu=True,
    ...     visibility=0.9,
    ...     run_id=0
    ... )
    """

    # Fetch logger
    logger = logging.getLogger("sim_logger")
    logger.info(
        f"""[i] Processing combination {run_id}
        dampening={dampening_parameter}, visibility={visibility}"""
    )
    batch_event_dfs = []
    batch_metadata_dfs = []
    for batch_run_id in range(batch_size):
        print(f"{batch_run_id}/{batch_size}", end="\r")
        gc.collect()
        run_metadata_df, full_events_df = single_run(
            switch_routing,
            dampening_parameter,
            max_attempts,
            max_distillations,
            ideal_switch,
            ideal_qpu,
            visibility,
            batch_run_id,
        )
        batch_event_dfs.append(full_events_df)
        batch_metadata_dfs.append(run_metadata_df)

    # Explicitly delete large objects and trigger garbage collection
    del run_metadata_df
    del full_events_df
    gc.collect()

    return batch_event_dfs, batch_metadata_dfs
