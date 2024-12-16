import numpy as np
from scipy.optimize import fsolve


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
