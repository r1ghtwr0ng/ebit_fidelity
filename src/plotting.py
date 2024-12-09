import math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from utils import distilled_fidelity, find_minimum_ebits, time_to_fidelity


def plot_ttf_3d(
    fso_depolar_probs,
    loss_probs,
    plot_data,
    threshold=0.95,
):
    """
    Generate a 3D surface plot showing time to fidelity for different loss probabilities and FSO dephase probabilities.

    Parameters
    ----------
    loss_probs : list or array
        Array of loss probabilities.
    fso_depolar_probs : list or array
        Array of FSO depolarization probabilities.
    plot_data : dictionary
        Dictionary containing simulation datapoints.
    threshold : float
        Fidelity threshold for the heatmap.
    """
    # Create an empty data array
    heatmap_data = np.zeros((len(fso_depolar_probs), len(loss_probs)))

    # Populate data array
    for j, loss_prob in enumerate(loss_probs):
        (fidelity_arr, success_probs, sim_timings) = plot_data[loss_prob]

        for i, fso_rate in enumerate(fso_depolar_probs):
            try:
                # Calculate the number of ebits required
                ebit_count = find_minimum_ebits(fidelity_arr[i], threshold)

                # Compute the time to fidelity
                ttf = time_to_fidelity(success_probs[i], sim_timings[i], ebit_count)

                # Handle cases where ttf might be infinite or not defined
                heatmap_data[i, j] = np.inf if np.isinf(ttf) else ttf
            except Exception as _e:
                # Assign np.inf in case of errors
                heatmap_data[i, j] = np.inf

    # Replace np.inf with a large value for visualization (optional)
    max_finite_value = np.nanmax(heatmap_data[np.isfinite(heatmap_data)])
    heatmap_data[~np.isfinite(heatmap_data)] = max_finite_value * 10
    vmin, vmax = 4, 10**3
    heatmap_data = np.clip(heatmap_data, vmin, vmax)

    # Create a 3D plot
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")

    # Create meshgrid for 3D plotting
    X, Y = np.meshgrid(loss_probs, fso_depolar_probs)
    Z = heatmap_data

    # Invert Z-axis and apply logarithmic scale
    Z = np.log10(Z)  # Take the logarithm of the values
    ax.invert_zaxis()  # Invert the Z-axis

    # Plot the surface
    surf = ax.plot_surface(
        X,
        Y,
        Z,
        cmap="viridis_r",
        edgecolor="none",
    )

    # Rotate the plot
    ax.view_init(elev=30, azim=90)

    # Add color bar
    fig.colorbar(
        surf,
        ax=ax,
        shrink=0.5,
        aspect=10,
        label=f"log10(Time to fidelity {threshold}) (ns)",
    )

    # Label axes
    ax.set_xlabel("Loss Probability")
    ax.set_ylabel("FSO Depolarization Probability")
    ax.set_zlabel(f"log10(Time to Fidelity {threshold}) (ns)")
    ax.set_title(f"3D Surface Plot: Time to Fidelity {threshold} (Inverted Z-axis)")

    # Show the plot
    plt.savefig(f"plots/3d/ttf_3d_{threshold}_heatmap.png")


def plot_ttf(
    fso_depolar_probs,
    loss_probs,
    plot_data,
    threshold=0.95,
):
    """
    Generate a heatmap showing time to fidelity for different loss probabilities and FSO dephase probabilities.

    Parameters
    ----------
    loss_probs : list or array
        Array of loss probabilities.
    fso_depolar_probs : list or array
        Array of FSO depolarization probabilities.
    plot_data : dictionary
        Dictionary containing simulation datapoints.
    threshold : float
        Fidelity threshold for the heatmap.
    """
    # Create an empty heatmap data array
    heatmap_data = np.zeros((len(fso_depolar_probs), len(loss_probs)))

    # Populate heatmap data
    for j, loss_prob in enumerate(loss_probs):
        (fidelity_arr, success_probs, sim_timings) = plot_data[loss_prob]

        for i, fso_rate in enumerate(fso_depolar_probs):
            try:
                # Calculate the number of ebits required
                ebit_count = find_minimum_ebits(fidelity_arr[i], threshold)

                # Compute the time to fidelity
                ttf = time_to_fidelity(success_probs[i], sim_timings[i], ebit_count)

                # Handle cases where ttf might be infinite or not defined
                heatmap_data[i, j] = np.inf if np.isinf(ttf) else ttf
            except Exception as _e:
                # Assign np.inf in case of errors
                heatmap_data[i, j] = np.inf

    # Replace np.inf with a large value for visualization (optional)
    max_finite_value = np.nanmax(heatmap_data[np.isfinite(heatmap_data)])
    heatmap_data[~np.isfinite(heatmap_data)] = max_finite_value * 10
    vmin, vmax = 4, 10**3
    heatmap_data = np.clip(heatmap_data, vmin, vmax)

    # Create the heatmap
    plt.figure(figsize=(8, 6))
    plt.imshow(
        heatmap_data,
        origin="lower",
        aspect="auto",
        extent=[
            min(loss_probs),
            max(loss_probs),
            min(fso_depolar_probs),
            max(fso_depolar_probs),
        ],
        cmap="viridis_r",
        norm=LogNorm(vmin=vmin, vmax=vmax),  # Exponential color scale
    )
    plt.colorbar(label=f"Time to fidelity {threshold} (ns)")
    plt.xlabel("Loss probability")
    plt.ylabel("FSO dephase probability")
    plt.title(f"Time needed to establish ebit of fidelity: {threshold}")
    plt.savefig(f"plots/heatmaps/ttf_{threshold}_heatmap.png")


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
    plt.xlim(0, 0.4)
    plt.savefig("plots/2d/distilled.png")
