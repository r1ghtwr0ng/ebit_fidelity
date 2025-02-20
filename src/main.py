import pickle
import logging
import numpy as np

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
                model_params, qpu_depolar_rate, switch_routing, total_runs, max_attempts
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
    switch_routing = {"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"}
    fso_depolar_rates = np.linspace(0, 0.5, 15)
    loss_probabilities = np.linspace(0, 1, 15)
    qpu_depolar_rate = 0
    total_runs = 50
    max_proto_attempts = 10

    # Run single-threaded simulation, get results
    results = single_sim(
        total_runs=total_runs,
        switch_routing=switch_routing,
        fso_depolar_rates=fso_depolar_rates,
        qpu_depolar_rate=qpu_depolar_rate,
        loss_probabilities=loss_probabilities,
        max_attempts=max_proto_attempts,
    )

    # Save data to file
    save_filename = "plotdata/data_file.pkl"
    logging.debug(f"Saving results data to file: {save_filename}")
    with open(save_filename, "wb") as file:
        pickle.dump(results, file)

    # Plotting code
    plot_success(fso_depolar_rates, loss_probabilities, results)


if __name__ == "__main__":
    main()
