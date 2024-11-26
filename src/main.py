import logging
import numpy as np
import multiprocessing as mp
import matplotlib.pyplot as plt

from simulation import batch_run
from utils import loss, distilled_fidelity


# TODO add doc comments
def configure_parameters(depolar_rate):
    model_parameters = {
        "short": {
            "init_loss": loss(1.319),
            "len_loss": 0.25,
            "init_depolar": depolar_rate,
            "len_depolar": 0,
            "channel_len": 0.005,
        },
        "mid": {
            "init_loss": loss(2.12),
            "len_loss": 0.25,
            "init_depolar": depolar_rate,
            "len_depolar": 0,
            "channel_len": 0.00587,
        },
        "long": {
            "init_loss": loss(2.005),
            "len_loss": 0.25,
            "init_depolar": depolar_rate,
            "len_depolar": 0,
            "channel_len": 0.00756,
        },
    }
    return model_parameters


def worker(model_parameters, qpu_depolar_rate, total_runs, output_queue, job_index):
    """
    Worker function to run the simulation in a separate process.
    Logs the start of the process and sends results via output_queue.

    Args:
        model_parameters (dict): Simulation parameters.
        qpu_depolar_rate (float): QPU depolarization rate.
        total_runs (int): Number of runs.
        output_queue (multiprocessing.Queue): Queue to store results.
        job_index (int): Index of the job for logging purposes.
    """
    logging.info(f"Starting process {job_index} (PID: {mp.current_process().pid})")
    try:
        result = batch_run(model_parameters, qpu_depolar_rate, total_runs)
        output_queue.put((job_index, result))
    except Exception as e:
        logging.error(
            f"Process {job_index} (PID: {mp.current_process().pid}) failed: {e}"
        )
        output_queue.put((job_index, None))
    finally:
        logging.info(f"Process {job_index} (PID: {mp.current_process().pid}) finished.")


def run_simulation(total_runs, fso_depolar_rates, qpu_depolar_rate=0, process_count=4):
    """
    Run simulations for given depolarization rates using multiple processes.

    Args:
        total_runs (int): Number of runs per depolarization rate.
        fso_depolar_rates (list): List of depolarization rates.
        qpu_depolar_rate (float): Depolarization rate for QPU.
        process_count (int): Number of concurrent processes.

    Returns:
        None
    """
    model_parameters_list = [configure_parameters(rate) for rate in fso_depolar_rates]

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

    for i, result in enumerate(results):
        success_run_fidelities = [fidelity for status, fidelity in result if status]
        success_count = len(success_run_fidelities)
        success_fidelity_avg = (
            np.average(success_run_fidelities) if success_count > 0 else 0
        )
        success_fidelities.append(success_fidelity_avg)

        success_attempts.append(success_count)
        total_fidelity_avg = np.average([fidelity for _, fidelity in result])
        total_fidelities.append(total_fidelity_avg)
        success_prob = success_count / total_runs
        success_probabilities.append(success_prob)
        print(
            """Run: {i}
        Depolar rate: {depolar_rate}
        Successful fidelity: {success_fidelity_avg}
        Total fidelity: {total_fidelity_avg}
        Successful attempts: {success_count}
        Success probability: {success_prob}
        """.format(
                i=i,
                depolar_rate=fso_depolar_rates[i],
                success_fidelity_avg=success_fidelity_avg,
                total_fidelity_avg=total_fidelity_avg,
                success_count=success_count,
                success_prob=success_prob,
            )
        )

    # Plot Average Attempts vs Loss Probability
    # plt.figure(figsize=(8, 6))
    # plt.plot(
    #    fso_depolar_rates,
    #    success_probabilities,
    #    marker="s",
    #    linestyle="-",
    #    label="Average attempt probability",
    # )
    # plt.xlabel("Loss probability")
    # plt.ylabel("Average attempts")
    # plt.title("Average attempts vs. loss probability")
    # plt.grid()
    # plt.legend()
    # plt.savefig("attempts.png")

    n_values = [1, 2, 3, 4, 5]

    # Plot the maximal distilled fidelity for 5 cases against the dephase rate
    plt.figure(figsize=(10, 6))

    for n in n_values:
        distilled_fidelities = [distilled_fidelity(f, n) for f in success_fidelities]
        plt.plot(
            fso_depolar_rates,
            distilled_fidelities,
            marker="o",
            linestyle="-",
            label=f"{n} Qubits",
        )

    plt.xlabel("Dephase probability")
    plt.ylabel("Distilled fidelity")
    plt.title("Distilled fidelity vs. dephase probability for n Qubits")
    plt.grid()
    plt.legend()
    plt.savefig("plots/distilled.png")


# TODO add some comments for the parameters
def main():
    # Set logging level
    logging.getLogger().setLevel(logging.INFO)
    fso_depolar_rates = np.linspace(0, 0.5, 100)
    qpu_depolar_rate = 0
    total_runs = 10000
    process_count = 4
    run_simulation(
        total_runs,
        fso_depolar_rates=fso_depolar_rates,
        qpu_depolar_rate=qpu_depolar_rate,
        process_count=process_count,
    )


if __name__ == "__main__":
    main()