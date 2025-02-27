import logging
import numpy as np
import netsquid as ns

from utils import record_results, configure_parameters, get_fidelities
from qpu_node import QPUNode
from fso_switch import FSOSwitch
from protocols import EntanglementRetryProto
from netsquid.examples.purify import Distil


def setup_network(
    model_parameters,
    loss_prob,
    qpu_dephase=0,
    long=False,
    herald_ports=["qout0", "qout1"],
):
    # Testing detector induced losses
    det_eff = 1 - loss_prob

    # Create nodes
    alice_node = QPUNode("AliceNode", correction=True, depolar_rate=qpu_dephase)
    bob_node = QPUNode("BobNode", depolar_rate=qpu_dephase)
    fsoswitch_node = FSOSwitch("bsm_fsoswitch", model_parameters, det_eff, herald_ports)

    # Connect node-level ports
    alice_node.processor.ports["qout_hdr"].connect(fsoswitch_node.ports["qin0"])
    if long:
        bob_node.processor.ports["qout_hdr"].connect(fsoswitch_node.ports["qin2"])
    else:
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
            model_params = configure_parameters(fso_drate)
            result = batch_run(
                model_params, qpu_depolar_rate, switch_routing, loss_prob, total_runs
            )
            results.append(result)
    return results


def single_run(
    model_parameters, qpu_depolar_rate, switch_routing, loss_prob, max_attempts
):
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
    loss_prob : float
        The probability that any photon is lost in the fibre or detector
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

    # TODO fix and remove the long shit
    long = switch_routing == {"qin0": "qout2", "qin1": "qout1", "qin2": "qout0"}
    herald_ports = (
        ["qout0", "qout2"] if long else [switch_routing["qin0"], switch_routing["qin1"]]
    )
    alice_node, bob_node, fsoswitch_node = setup_network(
        model_parameters, loss_prob, long=long, herald_ports=herald_ports
    )

    # Create and start the simulation protocol

    retry_protocol = EntanglementRetryProto(
        alice_node,
        bob_node,
        fsoswitch_node,
        switch_routing,
        max_attempts=max_attempts,
        timeout=100,
    )

    # TODO setup entanglement distillation protocol

    # Test
    retry_protocol.start()
    # TODO run entanglement distillation if retry successfully establishes ebit

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
    model_parameters,
    qpu_depolar_rate,
    switch_routing,
    batch_size,
    loss_prob,
    max_attempts,
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
    loss_prob : float
        The probability that any photon is lost in the fibre or detector
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
            model_parameters, qpu_depolar_rate, switch_routing, loss_prob, max_attempts
        )
        record_results(full_results, run_results, i, max_attempts)

    # Average calculations and return
    ret_results["status"] = np.average(full_results["status"])
    ret_results["attempts"] = np.average(run_results["attempts"])
    ret_results["fidelity"] = np.average(run_results["fidelity"])
    ret_results["simtime"] = np.average(run_results["simtime"])
    return ret_results
