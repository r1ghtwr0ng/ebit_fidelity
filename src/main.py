import pickle
import logging
import numpy as np
import matplotlib.pyplot as plt

from utils import configure_parameters
from simulation import batch_run
from plotting import plot_success


def single_sim(
    total_runs,
    switch_routing,
    fso_depolar_rates,
    qpu_depolar_rate,
    loss_probabilities,
    max_attempts,
):
    # Use a 2D numpy array for each element
    arr_dim = (len(fso_depolar_rates), len(loss_probabilities))
    results = {
        "status": np.zeros(arr_dim, dtype="float"),
        "attempts": np.zeros(arr_dim, dtype="float"),
        "fidelity": np.zeros(arr_dim, dtype="float"),
        "simtime": np.zeros(arr_dim, dtype="float"),
    }

    # For every depolarization configuration
    for i, fso_drate in enumerate(fso_depolar_rates):
        print(f"Progress: {i}/{len(fso_depolar_rates)}", end="\r")
        # For every loss probability configuration
        for j, loss_prob in enumerate(loss_probabilities):
            # Generate a model parameter configuration and run simulation batch
            model_params = configure_parameters(fso_drate, loss_prob)
            run_results = batch_run(
                model_params,
                qpu_depolar_rate,
                switch_routing,
                total_runs,
                loss_prob,
                max_attempts,
            )
            # Populate the results arrays
            results["status"][i][j] = run_results["status"]
            results["attempts"][i][j] = run_results["attempts"]
            results["fidelity"][i][j] = run_results["fidelity"]
            results["simtime"][i][j] = run_results["simtime"]

    return results


# TODO add some comments for the parameters
def main():
    # Set logging level
    logging.getLogger().setLevel(logging.ERROR)

    # Simulation parameters
    switch_routings = [
        {"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"},  # Low, Low
        {"qin0": "qout2", "qin1": "qout1", "qin2": "qout0"},  # Low, Mid
        {"qin0": "qout0", "qin1": "qout2", "qin2": "qout1"},  # Low, High
        {"qin0": "qout2", "qin1": "qout1", "qin2": "qout0"},  # Mid, Mid
        {"qin0": "qout2", "qin1": "qout0", "qin2": "qout1"},  # High, Mid
        {"qin0": "qout1", "qin1": "qout2", "qin2": "qout0"},  # High, High
    ]
    titles = [
        "(Low, Low)",
        "(Low, Mid)",
        "(Low, High)",
        "(Mid, Mid)",
        "(Mid, High)",
        "(High, High)",
    ]

    # Create a figure with 6 subplots (2 rows x 3 columns)
    fig, axs = plt.subplots(2, 3, figsize=(15, 10), constrained_layout=True)

    for i, switch_routing in enumerate(switch_routings):
        print(f"Running routing config: {titles[i]}")

        fso_depolar_rates = np.linspace(0, 0.8, 15)
        loss_probabilities = np.linspace(0, 0.8, 15)
        qpu_depolar_rate = 0
        total_runs = 50
        max_proto_attempts = 15

        # Run simulation and save data (if needed)
        results = single_sim(
            total_runs=total_runs,
            switch_routing=switch_routing,
            fso_depolar_rates=fso_depolar_rates,
            qpu_depolar_rate=qpu_depolar_rate,
            loss_probabilities=loss_probabilities,
            max_attempts=max_proto_attempts,
        )
        # with open(f"plotdata/data_file_{i}.pkl", "wb") as file:
        #    pickle.dump(results, file)

        # Select the appropriate subplot
        ax = axs[i // 3, i % 3]
        # Plot the heatmap on the current subplot and get the image object
        im = plot_success(ax, fso_depolar_rates, loss_probabilities, results, titles[i])

    # Add colorbar
    fig.colorbar(im, ax=axs.ravel().tolist(), label="Success probability", shrink=0.6)
    plt.savefig("plots/heatmaps/success_heatmap.png")
    print("\nPlot saved")


if __name__ == "__main__":
    main()
