import logging
import numpy as np
import netsquid.qubits.ketstates as ks
import netsquid.qubits.qubitapi as qapi


def record_results(full_results, run_results, i, attempt_limit):
    # Check the status of the run and create local vars
    status = run_results["status"]
    norm_fidelity = run_results["fidelity"] if status else 0
    norm_attempts = run_results["attempts"] if status else attempt_limit

    # TODO tweak the entanglement rate metric
    entanglement_rate = status * norm_fidelity * (1 / norm_attempts)

    # Record results in hashmap
    full_results["entanglement_rate"][i] = entanglement_rate
    full_results["simtime"][i] = run_results["simtime"]
    full_results["attempts"][i] = norm_attempts
    full_results["fidelity"][i] = norm_fidelity
    full_results["status"][i] = status


def extract_data(results):
    """Extract average fidelities and attempts from results."""
    avg_fidelities, avg_attempts, avg_simtime = [], [], []

    for result in results:
        # Convert to a NumPy array for vectorized filtering
        data = np.array(result, dtype=object)
        success_mask = data[:, 0].astype(bool)  # Ensure the mask is a boolean array

        successful_fidelities = data[success_mask, 3].astype(float)
        successful_attempts = data[success_mask, 2].astype(float)

        # Compute averages with default values for empty lists
        avg_fidelity = (
            np.mean(successful_fidelities) if successful_fidelities.size > 0 else 0
        )
        avg_attempt = (
            np.mean(successful_attempts)
            if successful_attempts.size > 0
            else float("inf")
        )

        avg_fidelities.append(avg_fidelity)
        avg_attempts.append(avg_attempt)

    return avg_fidelities, avg_attempts, avg_simtime


# TODO add doc comments
def configure_parameters(depolar_rate, loss_prob=0):
    model_parameters = {
        "short": {
            "init_loss": 0,  # loss(1.319),
            "len_loss": 0,  # loss_prob,
            "init_depolar": 0,  # loss(1.319),
            "len_depolar": 0,  # depolar_rate,
            "channel_len": 0,  # 0.005,
        },
        "mid": {
            "init_loss": loss(2.12),
            "len_loss": loss_prob,
            "init_depolar": loss(2.12),
            "len_depolar": depolar_rate,  # depolar_rate,
            "channel_len": 0,  # 0.00587,
        },
        "long": {
            "init_loss": loss(2.005),
            "len_loss": loss_prob,
            "init_depolar": depolar_rate,
            "len_depolar": depolar_rate,  # depolar_rate,
            "channel_len": 0,  # 0.00756,
        },
    }
    return model_parameters


# Get two qubits at positions 0 for alice and bob and calculate their fidelities
def get_fidelities(alice, bob, qid_1=1, qid_2=1):
    """
    Calculate the fidelities of entangled qubits for Alice and Bob.

    Parameters
    ----------
    alice : QPUNode
        The QPU entity representing Alice.
    bob : QPUNode
        The QPU entity representing Bob.

    Returns
    -------
    tuple
        A tuple containing:
        - status (bool): True if both Alice and Bob have valid qubits, False otherwise.
        - fidelity (float): Fidelity of the Bell state |B00>.
    """

    [qubit0] = alice.processor.peek(qid_1)
    [qubit1] = bob.processor.peek(qid_2)
    fidelities = {
        "|00>": qapi.fidelity([qubit0, qubit1], np.array([1, 0, 0, 0]), squared=True),
        "|11>": qapi.fidelity([qubit0, qubit1], np.array([0, 0, 0, 1]), squared=True),
        "B00": qapi.fidelity([qubit0, qubit1], ks.b00, squared=True),
        "B01": qapi.fidelity([qubit0, qubit1], ks.b01, squared=True),
        "B10": qapi.fidelity([qubit0, qubit1], ks.b10, squared=True),
        "B11": qapi.fidelity([qubit0, qubit1], ks.b11, squared=True),
    }

    logging.debug(f"[GREPPABLE] Simulation output: {fidelities}")
    return fidelities["B00"]


# Function to calculate fidelity after entanglement distillation
def distilled_fidelity(fidelity, n):
    """
    Calculate the upper bound of fidelity after entanglement distillation.

    Parameters
    ----------
    fidelity : float
        Initial fidelity of a single qubit.
    n : int
        Number of qubits used for entanglement distillation.

    Returns
    -------
    float
        Fidelity after entanglement distillation.
    """
    if n == 1:
        return fidelity

    numerator = pow(fidelity, n)
    denominator = numerator + pow(1 - fidelity, n)

    # Avoid division by zero
    if denominator == 0:
        return 0.0

    return numerator / denominator


def find_minimum_ebits(fidelity, target_fidelity):
    """
    Calculate the minimum number of ebits required to reach the target fidelity.

    Parameters
    ----------
    fidelity : float
        Initial fidelity of a single qubit (must be > 0.5).
    target_fidelity : float
        Target fidelity to achieve (must be > fidelity).

    Returns
    -------
    float
        Minimum number of ebits required.
    """
    if fidelity <= 0.5:
        return np.inf  # Impossible to reach target fidelity
    elif target_fidelity <= fidelity:
        return 1

    for n in range(100):
        if distilled_fidelity(fidelity, n) >= target_fidelity:
            return n
    return np.inf


def find_minimum_ebitz(fidelity, target_fidelity):
    """
    Calculate the minimum number of ebits required to reach the target fidelity.

    Parameters
    ----------
    fidelity : float
        Initial fidelity of a single qubit (must be > 0.5).
    target_fidelity : float
        Target fidelity to achieve (must be > fidelity).

    Returns
    -------
    int
        Minimum number of ebits required.
    """
    if fidelity <= 0.5:
        return np.inf  # Impossible to reach target fidelity
    elif target_fidelity <= fidelity:
        return 1

    # Binary search initialization
    left, right = 1, 10**6  # Reasonable upper bound

    while left < right:
        mid = (left + right) // 2
        if distilled_fidelity(fidelity, mid) >= target_fidelity:
            right = mid  # Continue searching lower values
        else:
            left = mid + 1

    return left if distilled_fidelity(fidelity, left) >= target_fidelity else np.inf


def loss(decibels):
    """
    Convert signal loss in decibels (dB) to a probability.

    Parameters
    ----------
    decibels : float
        Signal loss in decibels.

    Returns
    -------
    float
        Probability of signal loss (value between 0 and 1).
    """
    return 1 - pow(10, -(decibels / 10))


# Calculate the time (in nanoseconds) needed to get the distillation ebits
def time_to_fidelity(success_probability, time_to_ebit, distillation_ebits):
    return (distillation_ebits * time_to_ebit) / success_probability
