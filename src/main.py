import os
import logging
import datetime
import numpy as np

from simulation import batch_run
from plotting import plot_events, plot_metadata, plot_switch_meta, plot_switch_event


def main():
    # Set logging level
    logging.getLogger().setLevel(logging.ERROR)

    # Switch configuration parameters
    switch_routings = [
        ({"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"}, "low_low"),
        ({"qin0": "qout2", "qin1": "qout1", "qin2": "qout0"}, "low_mid"),
        ({"qin0": "qout0", "qin1": "qout2", "qin2": "qout1"}, "low_high"),
        ({"qin0": "qout2", "qin1": "qout1", "qin2": "qout0"}, "mid_mid"),
        ({"qin0": "qout2", "qin1": "qout0", "qin2": "qout1"}, "mid_high"),
        ({"qin0": "qout1", "qin1": "qout2", "qin2": "qout0"}, "high_high"),
    ]

    # Simulation sweep parameters
    detector_efficiencies = np.linspace(1, 1, 1)
    dampening_parameters = np.linspace(0, 0.3, 7)
    batch_size = 100
    max_distillations = 3
    max_proto_attempts = 10
    ideal_switch = False

    # Make directory to save plots in
    timestamp = f"{datetime.datetime.now():%Y-%m-%d_%H-%M-%S}"
    plot_directory = f"./plots/2d/{timestamp}"
    save_directory = f"./savefiles/{timestamp}"
    logging.info(f"Creating directories: {plot_directory} and {save_directory}")
    os.mkdir(plot_directory)
    os.mkdir(f"{plot_directory}/switched")
    os.mkdir(save_directory)

    # Lists for dataframe collection for bulk plotting between switch configs
    meta_list = []
    event_list = []

    # Run simulation for each switch configuration
    for switch_routing, title in switch_routings:
        print(f"Running routing config: {title}")

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
        df_metadata.to_parquet(f"{save_directory}/df_metadata_{switch_routing}.parquet")
        df_events.to_parquet(f"{save_directory}/df_events_{switch_routing}.parquet")

        # Append metadata to list
        meta_list.append(df_metadata)
        event_list.append(df_events)

        # Plot the collected data
        plot_metadata(df_metadata, config_name=title, directory=plot_directory)
        plot_events(df_events, config_name=title, directory=plot_directory)

    print("Done with main loop, printing rest")
    # Get the config names from the routing configurations
    config_names = [name for _, name in switch_routings]

    # Plot switch configuration differences
    plot_switch_meta(dfs=meta_list, config_names=config_names, directory=plot_directory)
    plot_switch_event(
        dfs=event_list, config_names=config_names, directory=plot_directory
    )


if __name__ == "__main__":
    main()
