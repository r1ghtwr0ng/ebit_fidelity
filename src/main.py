import os
import logging
import datetime
import numpy as np

from simulation import batch_run
from plotting import (
    plot_mean_fidelity_heatmap,
    plot_best_fidelity_phase_heatmap,
    plot_mean_phase_fidelity_heatmap,
    plot_mean_fidelity_2d,
    plot_mean_simtime_2d,
    plot_mean_success_prob_2d,
    plot_mean_operation_count_2d,
    plot_switch_fidelity_2d,
)


def main():
    # Set logging level
    logging.getLogger().setLevel(logging.ERROR)

    # Switch configuration parameters
    switch_routings = [
        ({"qin0": "qout0", "qin1": "qout1", "qin2": "qout2"}, "low_low"),
        # ({"qin0": "qout2", "qin1": "qout1", "qin2": "qout0"}, "low_mid"),
        # ({"qin0": "qout0", "qin1": "qout2", "qin2": "qout1"}, "low_high"),
        # ({"qin0": "qout2", "qin1": "qout1", "qin2": "qout0"}, "mid_mid"),
        # ({"qin0": "qout2", "qin1": "qout0", "qin2": "qout1"}, "mid_high"),
        # ({"qin0": "qout1", "qin1": "qout2", "qin2": "qout0"}, "high_high"),
    ]

    # Simulation sweep parameters
    visibilities = np.linspace(1, 0.7, 4)
    dampening_parameters = np.linspace(0, 0.3, 4)
    batch_size = 1000
    max_distillations = 3
    max_proto_attempts = 5
    ideal_switch = False
    ideal_qpu = False
    workers = 4

    # Make directory to save plots in
    timestamp = f"{datetime.datetime.now():%Y-%m-%d_%H-%M-%S}"
    plot_dir_2d = f"./plots/2d/{timestamp}"
    plot_dir_hmap = f"./plots/heatmap/{timestamp}"
    save_dir = f"./savefiles/{timestamp}"
    logging.info(f"Creating directories: {plot_dir_2d}, {plot_dir_hmap} and {save_dir}")
    os.mkdir(plot_dir_2d)
    os.mkdir(plot_dir_hmap)
    os.mkdir(f"{plot_dir_2d}/switched")
    os.mkdir(f"{plot_dir_hmap}/switched")
    os.mkdir(save_dir)

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
            ideal_qpu=ideal_qpu,
            dampening_parameters=dampening_parameters,
            visibilities=visibilities,
            max_attempts=max_proto_attempts,
            max_distillations=max_distillations,
            workers=workers,
        )

        # Append titles
        df_metadata["config"] = title
        df_events["config"] = title

        # Save to paraquet files on disk
        df_metadata.to_parquet(f"{save_dir}/df_metadata_{title}.parquet")
        df_events.to_parquet(f"{save_dir}/df_events_{title}.parquet")

        # Append metadata to list
        meta_list.append(df_metadata)
        event_list.append(df_events)

    # Get the config names from the routing configurations
    config_names = [name for _, name in switch_routings]

    # Plot heatmaps
    low_loss_df = event_list[0]
    plot_mean_fidelity_heatmap(event_list, plot_dir_hmap, config_names)
    plot_best_fidelity_phase_heatmap(event_list, plot_dir_hmap, config_names)
    plot_mean_phase_fidelity_heatmap(low_loss_df, plot_dir_hmap)

    # Filter out the dataframes where visibility is 0
    filtered_event_df = [df.loc[df["visibility"] == 1] for df in event_list]
    filtered_meta_df = [df.loc[df["visibility"] == 1] for df in meta_list]
    low_loss_filter = filtered_event_df[0]

    # Plot 2D plots (perfect detector)
    plot_mean_fidelity_2d(low_loss_filter, plot_dir_2d)
    plot_mean_simtime_2d(low_loss_filter, plot_dir_2d)

    plot_mean_success_prob_2d(filtered_event_df, plot_dir_2d)
    plot_mean_operation_count_2d(filtered_meta_df, plot_dir_2d)
    plot_switch_fidelity_2d(filtered_event_df, plot_dir_2d)


if __name__ == "__main__":
    main()
