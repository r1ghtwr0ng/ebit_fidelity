import matplotlib.pyplot as plt
from utils import distilled_fidelity


# TODO parameters doc comment
def plot_fidelity(success_fidelities, fso_depolar_rates, n_values=[1, 2, 3, 4, 5]):
    """
    Plot the distilled fidelity for varying qubit counts against the dephase rate.

    Parameters
    ----------
    success_fidelities : list[float]
        List of initial fidelities for successful quantum operations.
    fso_depolar_rates : list[float]
        List of dephase probabilities corresponding to each fidelity.
    n_values : list[int], optional
        Numbers of qubits used in entanglement distillation, by default [1, 2, 3, 4, 5].

    Returns
    -------
    None
        Saves the plot to "plots/distilled.png".
    """
    # Plot the maximal distilled fidelity for 5 cases against the dephase rate
    plt.figure(figsize=(10, 6))

    for n in n_values:
        distilled_fidelities = [distilled_fidelity(f, n) for f in success_fidelities]
        plt.plot(
            fso_depolar_rates,
            distilled_fidelities,
            marker="none",
            linestyle="-",
            label=f"{n} Qubits",
        )

    plt.xlabel("Dephase probability")
    plt.ylabel("Distilled fidelity")
    plt.title("Distilled fidelity vs. dephase probability")
    plt.grid()
    plt.legend()
    plt.savefig("plots/distilled.png")
