import pickle
import logging
import numpy as np
import multiprocessing as mp

from utils import loss
from simulation import batch_run
from plotting import plot_fidelity, plot_ttf, plot_ttf_3d


# TODO add doc comments
def configure_parameters(depolar_rate, loss_prob=0):
    model_parameters = {
        "short": {
            "init_loss": loss_prob,  # loss(1.319)
            "len_loss": 0,  # 0.25,
            "init_depolar": depolar_rate,
            "len_depolar": 0,
            "channel_len": 0,  # 0.005,
        },
        "mid": {
            "init_loss": loss_prob,  # loss(2.12),
            "len_loss": 0,  # 0.25,
            "init_depolar": depolar_rate,
            "len_depolar": 0,
            "channel_len": 0,  # 0.00587,
        },
        "long": {
            "init_loss": loss_prob,  # loss(2.005)
            "len_loss": 0,  # 0.25,
            "init_depolar": depolar_rate,
            "len_depolar": 0,
            "channel_len": 0,  # 0.00756,
        },
    }
    return model_parameters


def worker(
    model_parameters,
    qpu_depolar_rate,
    switch_routing,
    total_runs,
    output_queue,
    job_index,
):
    """
    Worker function to run the simulation in a separate process.
    Logs the start of the process and sends results via output_queue.

    Parameters:
    ----------
    model_parameters : dict
        Simulation parameters.
    qpu_depolar_rate : float
        QPU depolarization rate.
    total_runs : int
        Number of runs.
    output_queue : multiprocessing.Queue
        Queue to store results.
    job_index : int
        Index of the job for logging purposes.
    """
    logging.info(f"Starting process {job_index} (PID: {mp.current_process().pid})")
    try:
        result = batch_run(
            model_parameters, qpu_depolar_rate, switch_routing, total_runs
        )
        output_queue.put((job_index, result))
    except Exception as e:
        logging.error(
            f"Process {job_index} (PID: {mp.current_process().pid}) failed: {e}"
        )
        output_queue.put((job_index, None))
    finally:
        logging.info(f"Process {job_index} (PID: {mp.current_process().pid}) finished.")


def run_simulation(
    total_runs,
    switch_routing,
    fso_depolar_rates,
    qpu_depolar_rate=0,
    process_count=4,
    loss_prob=0,
):
    """
    Run simulations for given depolarization rates using multiple processes.

    Parameters
    ----------
    total_runs : int
        Number of runs per depolarization rate.
    fso_depolar_rates : list
        List of depolarization rates.
    qpu_depolar_rate : float
        Depolarization rate for QPU.
    process_count : int
        Number of concurrent processes.
    """
    model_parameters_list = [
        configure_parameters(rate, loss_prob) for rate in fso_depolar_rates
    ]

    # Initialize process management
    active_processes = []
    output_queue = mp.Queue()
    results = [None] * len(model_parameters_list)  # To store results in order
    next_job_index = 0  # Index of the next job to be started

    # Process scheduling loop
    while next_job_index < len(model_parameters_list) or active_processes:
        # Start new processes if the pool isn't full
        while len(active_processes) < process_count and next_job_index < len(
            model_parameters_list
        ):
            process = mp.Process(
                target=worker,
                args=(
                    model_parameters_list[next_job_index],
                    qpu_depolar_rate,
                    switch_routing,
                    total_runs,
                    output_queue,
                    next_job_index,
                ),
            )
            process.start()
            active_processes.append((process, next_job_index))
            logging.debug(f"Scheduled process {next_job_index} (PID: {process.pid}).")
            next_job_index += 1

        # Check for completed processes
        for process, job_index in active_processes:
            if not process.is_alive():
                process.join()
                logging.debug(f"Process {job_index} (PID: {process.pid}) terminated.")
                active_processes.remove((process, job_index))

        # Collect results
        while not output_queue.empty():
            job_index, result = output_queue.get()
            results[job_index] = result  # Store result in the correct order

    logging.info("All processes completed.")

    # Results formatting
    total_fidelities = []
    success_fidelities = []
    success_attempts = []
    success_probabilities = []
    simulation_times = []

    for i, result in enumerate(results):
        success_run_fidelities = [
            fidelity for status, fidelity, _simtime in result if status
        ]
        # Calculate the average time for a simulation (successful or not)
        simulation_times.append(np.average([t for _, _, t in result]))

        success_count = len(success_run_fidelities)
        success_fidelity_avg = (
            np.average(success_run_fidelities) if success_count > 0 else 0
        )
        success_fidelities.append(success_fidelity_avg)

        success_attempts.append(success_count)
        total_fidelity_avg = np.average([fidelity for _, fidelity, _simtime in result])
        total_fidelities.append(total_fidelity_avg)
        success_prob = success_count / total_runs
        success_probabilities.append(success_prob)
        print(
            """Run: {i}, loss: {loss_prob}
        Depolar rate: {depolar_rate}
        Successful fidelity: {success_fidelity_avg}
        Total fidelity: {total_fidelity_avg}
        Successful attempts: {success_count}
        Success probability: {success_prob}
        """.format(
                i=i,
                loss_prob=loss_prob,
                depolar_rate=fso_depolar_rates[i],
                success_fidelity_avg=success_fidelity_avg,
                total_fidelity_avg=total_fidelity_avg,
                success_count=success_count,
                success_prob=success_prob,
            )
        )

    return success_fidelities, success_probabilities, simulation_times
    # Plot the distilled fidelity results
    # plot_fidelity(success_fidelities, fso_depolar_rates)


# TODO add some comments for the parameters
def main():
    # Set logging level
    logging.getLogger().setLevel(logging.INFO)

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

    fso_depolar_rates = np.linspace(0, 0.5, 40)
    loss_probabilities = np.linspace(0, 1, 40)
    qpu_depolar_rate = 0
    total_runs = 18000
    process_count = 20
    plot_data = {}
    for loss_prob in loss_probabilities:
        success_fidelities, success_probabilities, simulation_times = run_simulation(
            total_runs=total_runs,
            switch_routing=switch_routing,
            fso_depolar_rates=fso_depolar_rates,
            qpu_depolar_rate=qpu_depolar_rate,
            process_count=process_count,
            loss_prob=loss_prob,
        )
        plot_data[loss_prob] = (
            success_fidelities,
            success_probabilities,
            simulation_times,
        )
    print(plot_data)

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
