import numpy as np
import matplotlib.pyplot as plt
from utils import distilled_fidelity


def plot_heatmap(plot_data, fso_depolar_rates, metric="fidelity"):
    """
    Generates a heatmap where one axis is the error probability (keys of plot_data),
    the other axis is the FSO dephase rate, and the color intensity represents either
    average fidelity or success probability.

    Parameters:
    - plot_data (dict): Keys are loss probabilities, values are tuples containing average fidelities and success probabilities.
    - fso_depolar_rates (array): Array of FSO dephase rates.
    - metric (str): "fidelity" or "success_prob" to choose what the color intensity represents.
    """
    # Extract loss probabilities (keys) and organize data
    loss_probs = list(plot_data.keys())
    loss_probs.sort()  # Ensure the keys are sorted for a structured heatmap

    # Initialize 2D arrays for the selected metric
    heatmap_data = np.zeros((len(fso_depolar_rates), len(loss_probs)))

    for j, loss_prob in enumerate(loss_probs):
        avg_fidelity_arr, avg_success_arr = plot_data[loss_prob]
        for i, fso_rate in enumerate(fso_depolar_rates):
            # Extract average fidelity or success probability from the results
            avg_fidelity = avg_fidelity_arr[i]
            avg_success_prob = avg_success_arr[i]
            if metric == "fidelity":
                heatmap_data[i, j] = avg_fidelity
            elif metric == "success_prob":
                heatmap_data[i, j] = avg_success_prob
            else:
                raise ValueError("Invalid metric. Choose 'fidelity' or 'success_prob'.")

    # Create the heatmap
    plt.figure(figsize=(8, 6))
    plt.imshow(
        heatmap_data,
        origin="lower",
        aspect="auto",
        extent=[
            min(loss_probs),
            max(loss_probs),
            min(fso_depolar_rates),
            max(fso_depolar_rates),
        ],
        cmap="viridis",
    )
    plt.colorbar(label=f"Average {metric.capitalize()}")
    plt.xlabel("Loss Probability")
    plt.ylabel("FSO Dephase Rate")
    plt.title(f"Heatmap of Average {metric.capitalize()} vs. Loss and FSO Dephase Rate")
    plt.savefig("plots/heatmap.png")


# Example usage:
# plot_heatmap(plot_data, fso_depolar_rates, metric="fidelity")
# plot_heatmap(plot_data, fso_depolar_rates, metric="success_prob")
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
