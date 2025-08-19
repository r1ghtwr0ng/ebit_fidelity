import logging
import numpy as np
import netsquid.qubits.ketstates as ks
import netsquid.qubits.qubitapi as qapi


# Flush all messages from a port
def flush_port(port):
    """
    Receive and drop all messages in a port's queue

    Parameters
    ----------
    port : netsquid.components.component.Port
        The port to be flushed
    """
    while port.input_queue:
        _ = port.rx_input()


def loss_prob(decibels):
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


# ==== FIDELITY & DISTILLATION CALCULATION UTILITIES ====


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

    [qubit0] = alice.processor.peek(qid_1, skip_noise=True)
    [qubit1] = bob.processor.peek(qid_2, skip_noise=True)
    fidelity = (qapi.fidelity([qubit0, qubit1], ks.b00, squared=True),)
    logging.debug(f"[FIDELITY_STATS] Simulation output: {fidelity}")

    return fidelity


# Function to calculate fidelity after entanglement distillation
def analytical_distilled_fidelity(fidelity, n):
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
        if analytical_distilled_fidelity(fidelity, n) >= target_fidelity:
            return n
    return np.inf


def time_to_fidelity(success_probability, time_to_ebit, distillation_ebits):
    """
    Calculate the time (in nanoseconds) needed to get the distillation ebit fidelity.
    This is based on analytical estimations of distillation efficiency.

    Parameters
    ----------
    success_probability : float
        Probability of distillation success, between 0 and 1.
    time_to_ebit : float
        Average time (in nanoseconds) needed to establish an entangled bit
    distillation_ebits : int
        Number of entangled bits used to perform distillation in parallel

    Returns
    -------
    float
        Time estimation in nanoseconds
    """
    return (distillation_ebits * time_to_ebit) / success_probability
