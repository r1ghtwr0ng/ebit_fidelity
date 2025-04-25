import os
import logging
import datetime
import numpy as np

from simulation import batch_run
from plotting import (
    plot_mean_fidelity_heatmap,
    plot_best_fidelity_phase_heatmap,
    plot_average_phase_time_heatmap,
    plot_average_phase_fidelity_heatmap,
    plot_switch_fidelity_2d,
    plot_mean_fidelity_2d,
    plot_mean_simtime_2d,
    plot_mean_success_prob_2d,
    plot_mean_operation_count_2d,
)


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
    dampening_parameters = np.linspace(0, 0.5, 5)
    batch_size = 100
    max_distillations = 3
    max_proto_attempts = 10
    ideal_switch = False
    workers = 4

    # Make directory to save plots in
    timestamp = f"{datetime.datetime.now():%Y-%m-%d_%H-%M-%S}"
    plot_directory_2d = f"./plots/2d/{timestamp}"
    plot_directory_heatmap = f"./plots/heatmap/{timestamp}"
    save_directory = f"./savefiles/{timestamp}"
    logging.info(
        f"Creating directories: {plot_directory_2d}, {plot_directory_heatmap} and {save_directory}"
    )
    os.mkdir(plot_directory_2d)
    os.mkdir(plot_directory_heatmap)
    os.mkdir(f"{plot_directory_2d}/switched")
    os.mkdir(f"{plot_directory_heatmap}/switched")
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
            workers=workers,
        )

        # Save to paraquet files on disk
        df_metadata.to_parquet(f"{save_directory}/df_metadata_{title}.parquet")
        df_events.to_parquet(f"{save_directory}/df_events_{title}.parquet")

        # Append metadata to list
        meta_list.append(df_metadata)
        event_list.append(df_events)

    # Get the config names from the routing configurations
    config_names = [name for _, name in switch_routings]

    # Plot heatmaps
    low_loss_df = event_list[0]
    plot_mean_fidelity_heatmap(
        dfs=event_list, directory=plot_directory_heatmap, config_names=config_names
    )
    plot_best_fidelity_phase_heatmap(
        dfs=event_list, directory=plot_directory_heatmap, config_names=config_names
    )
    plot_average_phase_time_heatmap(df=low_loss_df, directory=plot_directory_heatmap)
    plot_average_phase_fidelity_heatmap(
        df=low_loss_df, directory=plot_directory_heatmap
    )

    # Filter out the dataframes where detector efficiency is 1
    filtered_event_df = [df.loc[df["detector_efficiency"] == 1] for df in event_list]
    filtered_meta_df = [df.loc[df["detector_efficiency"] == 1] for df in meta_list]

    # Plot 2D plots (perfect detector)
    plot_mean_fidelity_2d(
        filtered_event_df, directory=plot_directory_2d, config_names=config_names
    )
    plot_mean_success_prob_2d(
        filtered_event_df, directory=plot_directory_2d, config_names=config_names
    )
    plot_mean_simtime_2d(filtered_event_df[0], directory=plot_directory_2d)
    plot_mean_operation_count_2d(
        filtered_meta_df, directory=plot_directory_2d, config_names=config_names
    )


if __name__ == "__main__":
    main()
