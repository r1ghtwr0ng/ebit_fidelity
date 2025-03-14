import logging
import numpy as np
import matplotlib.pyplot as plt

from utils import switch_parameters, ideal_parameters
from simulation import batch_run
from plotting import plot_norm_success


def single_sim(
    total_runs,
    switch_routing,
    fso_depolar_rates,
    loss_probabilities,
    max_attempts,
    max_distillations,
):
    # Use a 2D numpy array for each element
    arr_dim = (len(fso_depolar_rates), len(loss_probabilities))
    results = {
        "status": np.zeros(arr_dim, dtype="float"),
        "status_std": np.zeros(arr_dim, dtype="float"),
        "attempts": np.zeros(arr_dim, dtype="float"),
        "attempts_std": np.zeros(arr_dim, dtype="float"),
        "fidelity": np.zeros(arr_dim, dtype="float"),
        "fidelity_std": np.zeros(arr_dim, dtype="float"),
        "simtime": np.zeros(arr_dim, dtype="float"),
        "simtime_std": np.zeros(arr_dim, dtype="float"),
        "quantum_ops": np.zeros(arr_dim, dtype="float"),
        "quantum_ops_std": np.zeros(arr_dim, dtype="float"),
        "entanglement_rate": np.zeros(arr_dim, dtype="float"),
        "entanglement_rate_std": np.zeros(arr_dim, dtype="float"),
    }

    # For every loss probability configuration
    for j, loss_prob in enumerate(loss_probabilities):
        # For every depolarization configuration
        for i, fso_drate in enumerate(fso_depolar_rates):
            print(f"Progress: {i}/{len(fso_depolar_rates)}", end="\r")
            # Generate a model parameter configuration and run simulation batch
            # TODO change back to non-ideal
            model_params = switch_parameters(fso_drate, loss_prob)
            run_results = batch_run(
                model_parameters=model_params,
                switch_routing=switch_routing,
                batch_size=total_runs,
                loss_prob=loss_prob,
                max_attempts=max_attempts,
                max_distillations=max_distillations,
            )

            # Populate the results arrays
            results["status"][i][j] = run_results["status"]
            results["status_std"][i][j] = run_results["status_std"]
            results["attempts"][i][j] = run_results["attempts"]
            results["attempts_std"][i][j] = run_results["attempts_std"]
            results["fidelity"][i][j] = run_results["fidelity"]
            results["fidelity_std"][i][j] = run_results["fidelity_std"]
            results["simtime"][i][j] = run_results["simtime"]
            results["simtime_std"][i][j] = run_results["simtime_std"]
            results["quantum_ops"][i][j] = run_results["quantum_ops"]
            results["quantum_ops_std"][i][j] = run_results["quantum_ops_std"]
            results["entanglement_rate"][i][j] = run_results["entanglement_rate"]
            results["entanglement_rate_std"][i][j] = run_results[
                "entanglement_rate_std"
            ]

    return results


# TODO add some comments for the parameters
def main_single():
    # Set logging level
    logging.getLogger().setLevel(logging.ERROR)

    # Simulation parameters
    switch_routing = {"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"}

    # Simulation parameters
    fso_depolar_rates = np.linspace(0, 0.15, 25)
    loss_probabilities = np.linspace(0, 0, 1)
    total_runs = 200
    max_proto_attempts = 10
    max_distillations = 3

    # Create a single figure and axes for the plot
    fig, ax = plt.subplots(figsize=(10, 6))

    for max_distill in range(0, max_distillations):
        # Run simulation and save data (if needed)
        results = single_sim(
            total_runs=total_runs,
            switch_routing=switch_routing,
            fso_depolar_rates=fso_depolar_rates,
            loss_probabilities=loss_probabilities,
            max_attempts=max_proto_attempts,
            max_distillations=max_distill,
        )

        # Extract plot metric (assumed to be a 1D array with length matching loss_probabilities)
        print(f"DEBUG: {results}")
        plot_metric = results["fidelity"].reshape(-1)
        main_metric = fso_depolar_rates
        print(f"DEBUG: plot_metric = {plot_metric}")

        # Plot scatter points
        ax.scatter(
            main_metric,
            plot_metric,
            marker="o",
            label=f"{max_distill} distillations",
        )

        # Compute a best fit line for the current iteration
        coeffs = np.polyfit(main_metric, plot_metric, deg=1)
        best_fit = np.poly1d(coeffs)
        # Generate x-values for the best fit line
        x_fit = np.linspace(np.min(main_metric), np.max(main_metric), 100)
        y_fit = best_fit(x_fit)
        # Plot the best fit line
        ax.plot(x_fit, y_fit, linestyle="-")

        logging.info("========================================================\n\n\n\n")

    # Set plot labels and legend
    ax.set_xlabel("Dephase probability")
    ax.set_ylabel("Average ebit fidelity")
    ax.set_title("Affect of EPL distillation on ebit fiedelity")
    ax.legend()

    # Save the figure
    plt.savefig("plots/2d/distill_plot_fidelity_depol.png")
    print("\nPlot saved")


def main_switching():
    # Set logging level
    logging.getLogger().setLevel(logging.ERROR)

    # Simulation parameters
    switch_routings = [
        {"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"},  # Low, Low
        {"qin0": "qout2", "qin1": "qout1", "qin2": "qout0"},  # Low, Mid
        # {"qin0": "qout0", "qin1": "qout2", "qin2": "qout1"},  # Low, High
        {"qin0": "qout2", "qin1": "qout1", "qin2": "qout0"},  # Mid, Mid
        # {"qin0": "qout2", "qin1": "qout0", "qin2": "qout1"},  # High, Mid
        # {"qin0": "qout1", "qin1": "qout2", "qin2": "qout0"},  # High, High
    ]
    titles = ["(Low, Low)", "(Low, Mid)", "(Mid, Mid)"]

    # Simulation parameters
    # fso_depolar_rates not needed for line plot
    loss_probabilities = np.linspace(0, 0.4, 10)
    total_runs = 20
    max_proto_attempts = 7

    # Create a single figure and axes for the line plot
    fig, ax = plt.subplots(figsize=(10, 6))

    for i, switch_routing in enumerate(switch_routings):
        print(f"Running routing config: {titles[i]}")
        # Run simulation and save data (if needed)
        results = single_sim(
            total_runs=total_runs,
            switch_routing=switch_routing,
            fso_depolar_rates=np.array([0]),  # Dummy value since it's not used
            loss_probabilities=loss_probabilities,
            max_attempts=max_proto_attempts,
            max_distillations=0,
        )

        # Extract plot metric (assumed to be a 1D array with length matching loss_probabilities)
        print(f"DEBUG: {results}")
        plot_metric = results["simtime"][0]
        metric_std_err_mean = results["simtime_std"][0] / np.sqrt(total_runs)

        # Plot the line on the same axes
        ax.errorbar(
            loss_probabilities,
            plot_metric,
            yerr=metric_std_err_mean,
            label=titles[i],
            capsize=5,
            marker="o",
            linestyle="-",
        )

        logging.info("========================================================\n\n\n\n")

    # Set plot labels and legend
    ax.set_xlabel("Loss Probability")
    ax.set_ylabel("Average Simulation Time (ns)")
    ax.set_title(
        "Simulation Time vs Loss Probability for Different Routing Configurations"
    )
    ax.legend()

    # Save the figure
    plt.savefig("plots/2d/errbar_plot_simtime.png")
    print("\nPlot saved")


if __name__ == "__main__":
    main_single()
