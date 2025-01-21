import pickle
import logging
import numpy as np

from utils import extract_data, configure_parameters
from simulation import batch_run
from plotting import plot_fidelity, plot_ttf, plot_ttf_3d


def single_sim(
    total_runs, switch_routing, fso_depolar_rates, qpu_depolar_rate, loss_probabilities
):
    results = []
    for fso_drate in fso_depolar_rates:
        for loss_prob in loss_probabilities:
            model_params = configure_parameters(fso_drate, loss_prob)
            result = batch_run(
                model_params, qpu_depolar_rate, switch_routing, total_runs
            )
            results.append(result)
    return results


# TODO add some comments for the parameters
def main():
    # Set logging level
    logging.getLogger().setLevel(logging.DEBUG)

    # Set switch routing configuration
    # All possible routing configurations, Alice and Bob bindings
    # and route lengths for the 3x3
    # 0: 2, 1: 1, 2: 0 (A: 1, B: 2) 1 1
    # 0: 2, 1: 0, 2: 1 (A: 1, B: 2) 0 2
    # 0: 0, 1: 2, 2: 1 (A: 0, B: 2) 0 1
    # 0: 1, 1: 2, 2: 0 (A: 0, B: 2) 1 2
    # 0: 0, 1: 1, 2: 2 (A: 0, B: 1) 0 0
    # 0: 2, 1: 1, 2: 2 (A: 0, B: 2) 2 2
    _switch_routings = [
        (
            {"qin0": "qout2", "qin1": "qout1", "qin2": "qout0"},
            {"Alice": "qin1", "Bob": "qin2"},
        ),
        (
            {"qin0": "qout2", "qin1": "qout0", "qin2": "qout1"},
            {"Alice": "qin1", "Bob": "qin2"},
        ),
        (
            {"qin0": "qout0", "qin1": "qout2", "qin2": "qout1"},
            {"Alice": "qin0", "Bob": "qin2"},
        ),
        (
            {"qin0": "qout1", "qin1": "qout2", "qin2": "qout0"},
            {"Alice": "qin0", "Bob": "qin2"},
        ),
        (
            {"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"},
            {"Alice": "qin0", "Bob": "qin1"},
        ),
        (
            {"qin0": "qout2", "qin1": "qout1", "qin2": "qout2"},
            {"Alice": "qin0", "Bob": "qin2"},
        ),
    ]
    switch_routing = {"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"}

    fso_depolar_rates = np.linspace(0, 0.5, 2)
    fso_depolar_rates = [0]
    loss_probabilities = np.linspace(0, 1, 1)
    loss_probabilities = [0]
    qpu_depolar_rate = 0
    total_runs = 1
    plot_data = {}
    results = single_sim(
        total_runs=total_runs,
        switch_routing=switch_routing,
        fso_depolar_rates=fso_depolar_rates,
        qpu_depolar_rate=qpu_depolar_rate,
        loss_probabilities=loss_probabilities,
    )

    avg_fidelities = extract_data(results)
    logging.info(f"Average fidelities: {avg_fidelities}")
    print("Early exit until I fix plot code")
    return  # Early break for now
    # Plotting code
    thresholds = [0.9995, 0.995, 0.95, 0.9, 0.8, 0.7]
    for threshold in thresholds:
        plot_ttf(
            fso_depolar_rates,
            loss_probabilities,
            plot_data,
            threshold=threshold,
        )
        plot_ttf_3d(
            fso_depolar_rates,
            loss_probabilities,
            plot_data,
            threshold=threshold,
        )
    plot_fidelity(plot_data[0][0], fso_depolar_rates)

    # Save data to file
    with open("plotdata/data_file.pkl", "wb") as file:
        pickle.dump(
            (fso_depolar_rates, loss_probabilities, thresholds, plot_data), file
        )


if __name__ == "__main__":
    main()
