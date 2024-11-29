# Function to calculate fidelity after entanglement distillation
def distilled_fidelity(f, n):
    """
    Calculate the upper bound of fidelity after entanglement distillation.

    Parameters:
    f : float
        Initial fidelity of a single qubit.
    n : int
        Number of qubits used for entanglement distillation.

    Returns:
    float
        Fidelity after entanglement distillation.
    """
    if n == 1:
        return f  # For 1 qubit, distilled fidelity is the same as the initial fidelity
    return f**n / (f**n + (1 - f) ** n)


# Convert dB loss to probability
# TODO check validity of formula
def loss(decibels):
    return 1 - pow(10, -(decibels / 10))
