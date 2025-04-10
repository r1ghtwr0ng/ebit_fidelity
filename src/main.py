import time
import logging
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
        "(Low, Low)",
        #    "(Low, Mid)",
        #    "(Low, High)",
        #    "(Mid, Mid)",
        #    "(Mid, High)",
        #    "(High, High)",
    ]

    # Simulation sweep parameters
    detector_efficiencies = np.linspace(1, 1, 1)
    dampening_parameters = np.linspace(0, 0.3, 15)
    batch_size = 500
    max_distillations = 3
    max_proto_attempts = 10
    ideal_switch = False

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
        timestamp = int(time.time())
        df_metadata.to_parquet(f"./savefiles/df_metadata_{timestamp}.parquet")
        df_events.to_parquet(f"./savefiles/df_events_{timestamp}.parquet")

        # Plot the collected data
        plot_metadata(df_metadata, config_name=titles[i])
        plot_events(df_events, config_name=titles[i])


if __name__ == "__main__":
    main()
