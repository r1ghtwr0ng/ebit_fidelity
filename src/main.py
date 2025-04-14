import os
import time
import logging
import datetime
import numpy as np

from simulation import batch_run
from plotting import plot_events, plot_metadata


# TODO implement a main function with an amplitude dampening parameter
def main():
    # Set logging level
    logging.getLogger().setLevel(logging.ERROR)

    # Switch configuration parameters
    switch_routings = [
        {"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"},  # Low, Low
        #    {"qin0": "qout2", "qin1": "qout1", "qin2": "qout0"},  # Low, Mid
        #    {"qin0": "qout0", "qin1": "qout2", "qin2": "qout1"},  # Low, High
        #    {"qin0": "qout2", "qin1": "qout1", "qin2": "qout0"},  # Mid, Mid
        #    {"qin0": "qout2", "qin1": "qout0", "qin2": "qout1"},  # High, Mid
        #    {"qin0": "qout1", "qin1": "qout2", "qin2": "qout0"},  # High, High
    ]
    titles = [
        "Low_Low",
        #    "Low_Mid",
        #    "Low_High",
        #    "Mid_Mid",
        #    "Mid_High",
        #    "High_High",
    ]

    # Simulation sweep parameters
    detector_efficiencies = np.linspace(1, 1, 1)
    dampening_parameters = np.linspace(0, 0.3, 15)
    batch_size = 400
    max_distillations = 3
    max_proto_attempts = 10
    ideal_switch = False

    # Make directory to save plots in
    timestamp = f"{datetime.datetime.now():%Y-%m-%d_%H-%M-%S}"
    plot_directory = f"./plots/2d/{timestamp}"
    save_directory = f"./savefiles/{timestamp}"
    logging.info(f"Creating directories: {plot_directory} and {save_directory}")
    os.mkdir(plot_directory)
    os.mkdir(save_directory)

    # Run simulation for each switch configuration
    for i, switch_routing in enumerate(switch_routings):
        logging.info(f"Running routing config: {titles[i]}")

        # Run simulation and save data (if needed)
        df_metadata, df_events = batch_run(
            switch_routing=switch_routing,
            batch_size=batch_size,
            ideal_switch=ideal_switch,
            dampening_parameters=dampening_parameters,
            detector_efficiencies=detector_efficiencies,
            max_attempts=max_proto_attempts,
            max_distillations=max_distillations,
        )

        # Save to paraquet files on disk
        df_metadata.to_parquet(f"{save_directory}/df_metadata.parquet")
        df_events.to_parquet(f"{save_directory}/df_events.parquet")

        # Plot the collected data
        plot_metadata(df_metadata, config_name=titles[i], directory=plot_directory)
        plot_events(df_events, config_name=titles[i], directory=plot_directory)


if __name__ == "__main__":
    main()
