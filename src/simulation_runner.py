import sys
import pickle
import numpy as np
import netsquid as ns
from network import run, loss


def main():
    # Parse arguments from command-line input
    depolar = float(sys.argv[1])
    total = int(sys.argv[2])

    # Define model parameters
    model_parameters = {
        "short": {
            "init_loss": loss(1.319),
            "len_loss": 0.25,
            "init_depolar": depolar,
            "len_depolar": 0,
            "channel_len": 0.005,
        },
        "mid": {
            "init_loss": loss(2.12),
            "len_loss": 0.25,
            "init_depolar": depolar,
            "len_depolar": 0,
            "channel_len": 0.00587,
        },
        "long": {
            "init_loss": loss(2.005),
            "len_loss": 0.25,
            "init_depolar": depolar,
            "len_depolar": 0,
            "channel_len": 0.00756,
        },
    }

    # Run the simulation for the given depolarization rate
    result = []
    for _ in range(total):
        status, fidelity = run(model_parameters, depolar)
        result.append((status, fidelity))

    # Serialize the result and print it to stdout
    print(
        pickle.dumps(result).hex()
    )  # Use hex to avoid binary issues in subprocess output


if __name__ == "__main__":
    main()
