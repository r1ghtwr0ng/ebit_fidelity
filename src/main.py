import subprocess
import pickle
import numpy as np


def run_simulation():
    total = 1000
    fidelities = []
    avg_attempts = []
    x = np.linspace(0, 0.5, 20)

    for i, depolar in enumerate(x):
        print(f"Running iteration {i} with depolar: {depolar}")

        # Call the subprocess
        result_hex = subprocess.check_output(
            ["python", "src/simulation_runner.py", str(depolar), str(total)]
        )

        # Deserialize results
        result = pickle.loads(bytes.fromhex(result_hex.decode()))

        # Extract fidelities
        fidelities_per_run = [fidelity for status, fidelity in result if status]
        count = len(fidelities_per_run)
        avg = np.average(fidelities_per_run) if count > 0 else 0

        avg_attempts.append(total / count if count > 0 else np.inf)
        fidelities.append(avg)

        print(
            f"Run: {i}, dephase: {depolar}, count: {count}, fidelity: {avg}, avg attempts: {total/count if count > 0 else np.inf}"
        )

    return fidelities, avg_attempts


if __name__ == "__main__":
    fidelities, avg_attempts = run_simulation()
    print("Simulation complete.")
    print("Fidelities:", fidelities)
    print("Average attempts:", avg_attempts)
