import os
import logging
import datetime
import multiprocessing

from simulation import batch_run
from plotting import (
    plot_adjacency_heatmap,
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
    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("sim_logger").setLevel(logging.WARNING)
    logging.getLogger("fso_logger").setLevel(logging.WARNING)
    logging.getLogger("qpu_logger").setLevel(logging.WARNING)
    logging.getLogger("bsm_logger").setLevel(logging.WARNING)
    logging.getLogger("ctrl_logger").setLevel(logging.WARNING)
    logging.getLogger("data_logger").setLevel(logging.WARNING)
    logging.getLogger("proto_logger").setLevel(logging.WARNING)
    logging.getLogger("qprog_logger").setLevel(logging.WARNING)

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
    visibilities = [0.85]  # np.linspace(0.8, 0.8, 1)
    dampening_parameters = [0.15]  # np.linspace(0.2, 0.2, 1)
    batch_size = 400
    max_distillations = 3
    max_proto_attempts = 10
    ideal_switch = False
    ideal_qpu = False

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
            dampening_parameters=dampening_parameters,
            visibilities=visibilities,
            ideal_switch=ideal_switch,
            ideal_qpu=ideal_qpu,
            max_attempts=max_proto_attempts,
            max_distillations=max_distillations,
        )

        # Append titles
        df_metadata["config"] = title
        df_events["config"] = title

        # Save to paraquet files on disk
        logging.info("Saving dataframes to parquet files")
        df_metadata.to_parquet(f"{save_dir}/df_metadata_{title}.parquet")
        df_events.to_parquet(f"{save_dir}/df_events_{title}.parquet")
        os.sync()  # Flush buffers

        # Append metadata to list
        meta_list.append(df_metadata)
        event_list.append(df_events)

    # Get the config names from the routing configurations
    config_names = [name for _, name in switch_routings]

    # Plot fidelity heatmaps
    low_loss_df = event_list[0]
    plot_adjacency_heatmap(low_loss_df, plot_dir_hmap)
    plot_mean_phase_fidelity_heatmap(low_loss_df, plot_dir_hmap)

    # Plot configuration heatmaps if more than one
    if len(config_names) > 1:
        plot_mean_fidelity_heatmap(event_list, plot_dir_hmap, config_names)
        plot_best_fidelity_phase_heatmap(event_list, plot_dir_hmap, config_names)

    # Filter out the dataframes where visibility is 1
    filtered_event_df = [df.loc[df["visibility"] == 1] for df in event_list]
    filtered_meta_df = [df.loc[df["visibility"] == 1] for df in meta_list]
    low_loss_filter = filtered_event_df[0]

    # Plot 2D plots (perfect detector)
    if len(low_loss_filter) > 0:
        plot_mean_fidelity_2d(low_loss_filter, plot_dir_2d)
        plot_mean_simtime_2d(low_loss_filter, plot_dir_2d)
        plot_mean_success_prob_2d(filtered_event_df, plot_dir_2d)
        plot_mean_operation_count_2d(filtered_meta_df, plot_dir_2d)
        plot_switch_fidelity_2d(filtered_event_df, plot_dir_2d)


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    try:
        main()
    except KeyboardInterrupt:
        print("\r[i] Quitting")
