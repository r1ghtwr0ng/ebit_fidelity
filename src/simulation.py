import logging
import numpy as np
import netsquid as ns

from utils import record_results, configure_parameters, get_fidelities
from qpu_entity import QPUNode
from fso_switch import FSOSwitch
from protocols import EntanglementRetryProto


def setup_network(model_parameters):
    # Create nodes
    alice_node = QPUNode("AliceNode", correction=True)
    bob_node = QPUNode("BobNode")
    fsoswitch_node = FSOSwitch("bsm_fsoswitch", model_parameters)

    # Connect node-level ports
    alice_node.processor.ports["qout_hdr"].connect(fsoswitch_node.ports["qin0"])
    bob_node.processor.ports["qout_hdr"].connect(fsoswitch_node.ports["qin1"])
    fsoswitch_node.ports["cout0"].connect(alice_node.processor.ports["correction"])
    fsoswitch_node.ports["cout1"].connect(bob_node.processor.ports["correction"])

    return alice_node, bob_node, fsoswitch_node


def single_sim(
    total_runs, switch_routing, fso_depolar_rates, qpu_depolar_rate, loss_probs
):
    results = []
    for fso_drate in fso_depolar_rates:
        for loss_prob in loss_probs:
            model_params = configure_parameters(fso_drate, loss_prob)
            result = batch_run(
                model_params, qpu_depolar_rate, switch_routing, total_runs
            )
            results.append(result)
    return results


def single_run(model_parameters, qpu_depolar_rate, switch_routing, max_attempts):
    """
    Run a single quantum simulation with specified configurations and collect results.

    Parameters
    ----------
    model_parameters : dict
        Configuration parameters for the FSO switch model.
    qpu_depolar_rate : float
        Depolarization rate for the QPU entities.
    switch_routing : dict
        Routing table for the FSO switch, defining how quantum information is routed.
    max_attempts : int
        The maximum number of attempts for establishing an entanglement link before the
        protocol gives up.

    Returns
    -------
    tuple
        A tuple containing the simulation status, fidelity, and simulation time.
        Example: (status, fidelity, simtime)
    """
    # Initialize simulation
    ns.sim_reset()
    alice_node, bob_node, fsoswitch_node = setup_network(model_parameters)

    # Create and start the simulation protocol

    retry_protocol = EntanglementRetryProto(
        alice_node,
        bob_node,
        fsoswitch_node,
        switch_routing,
        max_attempts=max_attempts,
        timeout=100,
    )

    # Test
    retry_protocol.start()

    # Run the simulation
    ns.sim_run()
    simtime = ns.sim_time()
    logging.info(
        f"[QPU] Status: {alice_node.processor.status} | queue: {alice_node.get_queue()}"
    )
    fidelity = get_fidelities(alice_node, bob_node) if retry_protocol.success else 0
    logging.debug(f"FIDELITY: {fidelity}")

    # Return results
    return {
        "status": retry_protocol.success,
        "attempts": retry_protocol.attempts,
        "fidelity": fidelity,
        "simtime": simtime,
    }


# Runs the simulation several times, determined by the batch size.
def batch_run(
    model_parameters, qpu_depolar_rate, switch_routing, batch_size, max_attempts
):
    """
    Run multiple quantum simulations with specified configurations and collect results.

    Parameters
    ----------
    model_parameters : dict
        Configuration parameters for the FSO switch model.
    qpu_depolar_rate : float
        Depolarization rate for the QPU entities.
    switch_routing : dict
        Routing table for the FSO switch.
    batch_size : int
        Number of simulation runs in the batch.
    max_attempts : int
        The maximum number of attempts for establishing an entanglement link before the
        protocol gives up.

    Returns
    -------
    dictionary
        A dictionary containing the simulation status, attempt count, fidelity and
        simulation duration for each run.
    """
    ret_results = {"status": 0, "attempts": 0, "fidelity": 0, "simtime": 0}
    full_results = {
        "status": np.zeros(batch_size, dtype="bool"),
        "attempts": np.zeros(batch_size, dtype="uint"),
        "fidelity": np.zeros(batch_size, dtype="float"),
        "simtime": np.zeros(batch_size, dtype="float"),
    }
    for i in range(batch_size):
        # Perform single run of the simulation and record the results into the dict
        run_results = single_run(
            model_parameters, qpu_depolar_rate, switch_routing, max_attempts
        )
        record_results(full_results, run_results, i, max_attempts)

    # Average calculations and return
    ret_results["status"] = np.average(full_results["status"])
    ret_results["attempts"] = np.average(run_results["attempts"])
    ret_results["fidelity"] = np.average(run_results["fidelity"])
    ret_results["simtime"] = np.average(run_results["simtime"])
    return ret_results
