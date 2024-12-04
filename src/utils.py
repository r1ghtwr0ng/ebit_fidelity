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
    return pow(fidelity, n) / (pow(fidelity, n) + pow(1 - fidelity, n))


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

    # Define the equation to solve
    def equation(n):
        return (
            pow(fidelity, n) / (pow(fidelity, n) + pow(1 - fidelity, n))
            - target_fidelity
        )

    # Use numerical solver to find n
    n_initial_guess = 10  # Reasonable initial guess
    n_solution = fsolve(equation, n_initial_guess)
    return n_solution[0]


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
