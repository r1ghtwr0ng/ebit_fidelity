import logging
import numpy as np
import matplotlib.pyplot as plt

from utils import configure_parameters
from simulation import batch_run
from plotting import plot_norm_success


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
        "entanglement_rate": np.zeros(arr_dim, dtype="float"),
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
            results["entanglement_rate"][i][j] = run_results["entanglement_rate"]

    return results


# TODO add some comments for the parameters
def main():
    # Set logging level
    logging.getLogger().setLevel(logging.ERROR)

    # Simulation parameters
    switch_routings = [
        {"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"},  # Low, Low
        #    {"qin0": "qout2", "qin1": "qout1", "qin2": "qout0"},  # Low, Mid
        #    {"qin0": "qout0", "qin1": "qout2", "qin2": "qout1"},  # Low, High
        #    {"qin0": "qout2", "qin1": "qout1", "qin2": "qout0"},  # Mid, Mid
        #    {"qin0": "qout2", "qin1": "qout0", "qin2": "qout1"},  # High, Mid
        #    {"qin0": "qout1", "qin1": "qout2", "qin2": "qout0"},  # High, High
    ]
    switch_routing = {"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"}

    titles = [
        "(Low, Low)",
        #    "(Low, Mid)",
        #    "(Low, High)",
        #    "(Mid, Mid)",
        #    "(Mid, High)",
        #    "(High, High)",
    ]

    # Simulation parameters
    fso_depolar_rates = np.linspace(0, 0.4, 15)
    loss_probabilities = np.linspace(0, 0.4, 15)
    qpu_depolar_rate = 0
    total_runs = 50
    max_proto_attempts = 5

    # Create a figure with 6 subplots (2 rows x 3 columns)
    fig, axs = plt.subplots(2, 3, figsize=(15, 10), constrained_layout=True)

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

    # Assuming fso_depolar_rates, loss_probabilities, results, and title are defined
    fig, ax = plt.subplots(figsize=(8, 6))
    im = plot_norm_success(
        ax, fso_depolar_rates, loss_probabilities, results, "Loss/Dephase plot"
    )
    fig.colorbar(im, ax=ax, label="Entanglement establishment", shrink=0.6)
    plt.savefig("plots/heatmaps/single_heatmap.png")
    plt.show()

    # Add colorbar
    plt.savefig("plots/heatmaps/success_heatmap.png")
    print("\nPlot saved")


if __name__ == "__main__":
    main()
