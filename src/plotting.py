import logging
import matplotlib.pyplot as plt


def plot_switch_event(dfs, config_names, directory, colors=None):
    print("ENTRY POINT FOR SWITCH PLOTTING CODE (EVT)")
    if colors is None:
        # Use default color cycle if no colors provided
        colors = plt.cm.tab10.colors[: len(dfs)]
    elif len(colors) < len(dfs):
        # Extend colors if not enough provided
        colors = colors + plt.cm.tab10.colors[: (len(dfs) - len(colors))]
    return

    # 1. Fidelity comparison (all vs success)
    plt.figure(figsize=(10, 6))
    for i, (df, config_name) in enumerate(zip(dfs, config_names)):
        grouped = df.groupby("dampening_parameter")
        all_fidelity = grouped["fidelity"].mean().reset_index()
        success_fidelity = (
            df[df["success"]]
            .groupby("dampening_parameter")["fidelity"]
            .mean()
            .reset_index()
        )
        plt.plot(
            all_fidelity["dampening_parameter"],
            all_fidelity["fidelity"],
            marker="o",
            label=f"All attempts [{config_name}]",
        )
        plt.plot(
            success_fidelity["dampening_parameter"],
            success_fidelity["fidelity"],
            marker="x",
            label=f"Successful attempts [{config_name}]",
        )
    plt.xlabel("Dampening Parameter")
    plt.ylabel("Mean Fidelity")
    plt.title("Fidelity Comparison vs Dampening")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{directory}/switched/fidelity_comparison.png")
    plt.clf()

    # 2. Success probability
    for i, (df, config_name, color) in enumerate(zip(dfs, config_names, colors)):
        grouped = df.groupby("dampening_parameter")
        success_rate = grouped["success"].mean().reset_index()
        plt.plot(
            success_rate["dampening_parameter"],
            success_rate["success"],
            marker="o",
            label=f"Success probability [{config_name}]",
            color=color,
        )

    plt.xlabel("Dampening Parameter")
    plt.ylabel("Success Probability")
    plt.title("Success Probability vs Dampening")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{directory}/switched/event_success_prob_comparison.png")
    plt.clf()

    # 3. Phase success histogram
    for i, (df, config_name) in enumerate(zip(dfs, config_names)):
        # Group by phase and dampening
        grouped = df.groupby(["phase", "dampening_parameter"])
        success_rate = (
            grouped["success"].mean().unstack()
        )  # rows: phase, cols: dampening

        # Plot
        for phase in success_rate.index:
            plt.plot(
                success_rate.columns,
                success_rate.loc[phase],
                label=f"{phase} [{config_name}]",
            )

    plt.xlabel("Dampening Parameter")
    plt.ylabel("Success Probability")
    plt.title("Success Probability per Phase")
    plt.legend(title="Phase")
    plt.tight_layout()
    plt.savefig(f"{directory}/switched/phase_success_comparison.png")
    plt.clf()

    # 4. Avg fidelity per phase (success only)
    for i, (df, config_name) in enumerate(zip(dfs, config_names)):
        # Group by phase and dampening
        phases = df["phase"].unique()
        for_phase = df[df["success"]]
        phase_fid = (
            for_phase.groupby(["phase", "dampening_parameter"])["fidelity"]
            .mean()
            .reset_index()
        )

        plt.figure(figsize=(10, 6))
        for phase in phases:
            subset = phase_fid[phase_fid["phase"] == phase]
            plt.plot(
                subset["dampening_parameter"],
                subset["fidelity"],
                marker="o",
                label=f"{phase} [{config_name}]",
            )

    plt.xlabel("Dampening Parameter")
    plt.ylabel("Avg Fidelity (Successful)")
    plt.title("Phase-wise Avg Fidelity vs Dampening")
    plt.legend(title="Phase")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{directory}/switched/fidelity_per_phase_comparison.png")
    plt.clf()


def plot_switch_meta(dfs, config_names, directory, colors=None):
    """
    Plot metadata for multiple dataframes with different colors.

    Parameters:
    -----------
    dfs : list of DataFrames
        List of metadata dataframes to plot
    config_names : list of str
        Names corresponding to each dataframe for the legend
    directory : str
        Directory to save plots
    colors : list, optional
        List of colors to use for each dataframe
    """
    print("ENTRY POINT FOR SWITCH PLOTTING CODE (META)")
    if colors is None:
        # Use default color cycle if no colors provided
        colors = plt.cm.tab10.colors[: len(dfs)]
    elif len(colors) < len(dfs):
        # Extend colors if not enough provided
        colors = colors + plt.cm.tab10.colors[: (len(dfs) - len(colors))]

    # 1. Mean simtime plot
    plt.figure(figsize=(10, 6))
    for i, (df, config_name, color) in enumerate(zip(dfs, config_names, colors)):
        unique_eff = df["detector_efficiency"].unique()
        if len(unique_eff) > 1:
            logging.error(
                f"Multiple detector_efficiency values detected in {config_name}"
            )

        grouped = df.groupby("dampening_parameter")
        simtime_stats = grouped["simtime"].agg(["mean"]).reset_index()

        plt.plot(
            simtime_stats["dampening_parameter"],
            simtime_stats["mean"],
            marker="o",
            color=color,
            label=config_name,
        )

    plt.xlabel("Dampening Parameter")
    plt.ylabel("Average Simtime")
    plt.title("(Metadata) Average Simtime vs Dampening")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{directory}/switched/simtime_vs_dampening_comparison.png")
    plt.clf()

    # 2. Mean quantum_ops plot
    plt.figure(figsize=(10, 6))
    for i, (df, config_name, color) in enumerate(zip(dfs, config_names, colors)):
        grouped = df.groupby("dampening_parameter")
        ops_stats = grouped["quantum_ops"].agg(["mean"]).reset_index()

        plt.plot(
            ops_stats["dampening_parameter"],
            ops_stats["mean"],
            marker="o",
            color=color,
            label=config_name,
        )

    plt.xlabel("Dampening Parameter")
    plt.ylabel("Average Quantum Ops")
    plt.title("(Metadata) Average Quantum Ops vs Dampening")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{directory}/switched/quantum_ops_vs_dampening_comparison.png")
    plt.clf()

    # 3. Success probability plot
    plt.figure(figsize=(10, 6))
    for i, (df, config_name, color) in enumerate(zip(dfs, config_names, colors)):
        grouped = df.groupby("dampening_parameter")
        success_rate = grouped["status"].mean().reset_index()

        plt.plot(
            success_rate["dampening_parameter"],
            success_rate["status"],
            marker="o",
            color=color,
            label=config_name,
        )

    plt.xlabel("Dampening Parameter")
    plt.ylabel("Success Probability")
    plt.title("(Metadata) Success Probability vs Dampening")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{directory}/switched/success_prob_vs_dampening_comparison.png")
    plt.clf()


def plot_metadata(df_metadata, config_name, directory):
    # TODO doc comments
    # Columns: run detector_efficiency dampening_parameter run_id ideal status simtime quantum_ops
    unique_eff = df_metadata["detector_efficiency"].unique()
    if len(unique_eff) > 1:
        # TODO: implement heatmap if multiple detector efficiencies
        logging.error("Multiple detector_efficiency values detected — skipping plots.")
        pass
    else:
        grouped = df_metadata.groupby("dampening_parameter")

        # 1. Mean simtime
        simtime_stats = grouped["simtime"].agg(["mean"]).reset_index()
        plt.plot(
            simtime_stats["dampening_parameter"],
            simtime_stats["mean"],
            marker="o",
        )
        plt.xlabel("Dampening Parameter")
        plt.ylabel("Average Simtime")
        plt.title("(Metadata) Average Simtime vs Dampening")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(f"{directory}/simtime_vs_dampening_{config_name}.png")
        plt.clf()

        # 2. Mean quantum_ops
        ops_stats = grouped["quantum_ops"].agg(["mean"]).reset_index()
        plt.plot(
            ops_stats["dampening_parameter"],
            ops_stats["mean"],
            marker="o",
        )
        plt.xlabel("Dampening Parameter")
        plt.ylabel("Average Quantum Ops")
        plt.title("(Metadata) Average Quantum Ops vs Dampening")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(f"{directory}/quantum_ops_vs_dampening_{config_name}.png")
        plt.clf()

        # 3. Success probability (status == True)
        success_rate = grouped["status"].mean().reset_index()
        plt.plot(
            success_rate["dampening_parameter"], success_rate["status"], marker="o"
        )
        plt.xlabel("Dampening Parameter")
        plt.ylabel("Success Probability")
        plt.title("(Metadata) Success Probability vs Dampening")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(f"{directory}/success_prob_vs_dampening_{config_name}.png")
        plt.clf()


def plot_events(df_events, config_name, directory):
    # TODO doc comments
    # Columns: fidelity simtime attempt_log success phase attempt total_attempts time run detector_efficiency dampening_parameter
    unique_eff = df_events["detector_efficiency"].unique()
    if len(unique_eff) > 1:
        # TODO: implement heatmap if multiple detector efficiencies
        logging.error("Multiple detector_efficiency values detected — skipping plots.")
        pass
    else:
        grouped = df_events.groupby("dampening_parameter")

        # 1. Fidelity comparison (all vs success)
        all_fidelity = grouped["fidelity"].mean().reset_index()
        success_fidelity = (
            df_events[df_events["success"]]
            .groupby("dampening_parameter")["fidelity"]
            .mean()
            .reset_index()
        )

        plt.plot(
            all_fidelity["dampening_parameter"],
            all_fidelity["fidelity"],
            "o-",
            label="All attempts",
        )
        plt.plot(
            success_fidelity["dampening_parameter"],
            success_fidelity["fidelity"],
            "x-",
            label="Successful attempts",
        )
        plt.xlabel("Dampening Parameter")
        plt.ylabel("Mean Fidelity")
        plt.title("Fidelity Comparison vs Dampening")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(f"{directory}/fidelity_comparison_{config_name}.png")
        plt.clf()

        # 2. Success probability
        success_rate = grouped["success"].mean().reset_index()
        plt.plot(
            success_rate["dampening_parameter"], success_rate["success"], marker="o"
        )
        plt.xlabel("Dampening Parameter")
        plt.ylabel("Success Probability")
        plt.title("Success Probability vs Dampening")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(f"{directory}/event_success_prob_{config_name}.png")
        plt.clf()

        # 3. Phase success histogram
        # Group by phase and dampening
        grouped = df_events.groupby(["phase", "dampening_parameter"])
        success_rate = (
            grouped["success"].mean().unstack()
        )  # rows: phase, cols: dampening

        # Plot
        for phase in success_rate.index:
            plt.plot(success_rate.columns, success_rate.loc[phase], label=phase)

        plt.xlabel("Dampening Parameter")
        plt.ylabel("Success Probability")
        plt.title("Success Probability per Phase")
        plt.legend(title="Phase")
        plt.tight_layout()
        plt.savefig(f"{directory}/phase_success_{config_name}.png")
        plt.clf()

        # 4. Avg fidelity per phase (success only)
        phases = df_events["phase"].unique()
        for_phase = df_events[df_events["success"]]
        phase_fid = (
            for_phase.groupby(["phase", "dampening_parameter"])["fidelity"]
            .mean()
            .reset_index()
        )

        plt.figure(figsize=(10, 6))
        for phase in phases:
            subset = phase_fid[phase_fid["phase"] == phase]
            plt.plot(
                subset["dampening_parameter"],
                subset["fidelity"],
                marker="o",
                label=phase,
            )

        plt.xlabel("Dampening Parameter")
        plt.ylabel("Avg Fidelity (Successful)")
        plt.title("Phase-wise Avg Fidelity vs Dampening")
        plt.legend(title="Phase")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(f"{directory}/fidelity_per_phase_{config_name}.png")
        plt.clf()
