import logging
import matplotlib.pyplot as plt


# ==== Heatmap plots ====
# TODO (multiple dataframes, one per switch config)
def plot_mean_fidelity_heatmap(dfs, directory, config_names):
    pass


# TODO (multiple dataframes, one per switch config)
def plot_best_fidelity_phase_heatmap(dfs, directory, config_names):
    pass


# TODO (single dataframe, one switch config only)
def plot_average_phase_time_heatmap(df, directory):
    pass


# TODO (single dataframe, one switch config only)
def plot_average_phase_fidelity_heatmap(df, directory):
    pass


# ==== 2D plots ====
def plot_mean_fidelity_2d(dfs, directory, config_names):
    return


def plot_switch_fidelity_2d(dfs, directory, config_names):
    colors = plt.cm.tab10.colors[: len(dfs)]
    plt.figure(figsize=(10, 6))

    for i, (df, config_name, color) in enumerate(zip(dfs, config_names, colors)):
        # Filter successful entries first
        success_df = df[df["success"]]

        # Then group by dampening parameter and calculate mean fidelity
        mean_fidelity = (
            success_df.groupby("dampening_parameter")["fidelity"].mean().reset_index()
        )

        plt.plot(
            mean_fidelity["dampening_parameter"],
            mean_fidelity["fidelity"],
            marker="o",
            label=config_name,
            color=color,
        )

    plt.xlabel("Dampening Parameter")
    plt.ylabel("Mean Fidelity")
    plt.title("Fidelity Comparison vs Dampening")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{directory}/switched/mean_fidelity_comparison.png")
    plt.clf()


def plot_mean_simtime_2d(df, directory):
    plt.figure(figsize=(10, 6))

    # get unique phases from the dataframe
    phases = df["phase"].unique()

    # colors
    colors = plt.cm.tab10.colors[: len(phases)]

    # plot for each phase
    for phase, color in zip(phases, colors):
        # filter data for this phase
        phase_data = df[(df["phase"] == phase) & df["success"]]

        # Only plot if we have successful runs for this phase
        if not phase_data.empty:
            # Calculate mean simulation time for each dampening parameter
            mean_simtime = (
                phase_data.groupby("dampening_parameter")["simtime"]
                .mean()
                .reset_index()
            )
            plt.plot(
                mean_simtime["dampening_parameter"],
                mean_simtime["simtime"],
                marker="o",
                label=f"Phase: {phase}",
                color=color,
            )

    plt.xlabel("dampening parameter")
    plt.ylabel("simulation time (s)")
    plt.title("mean simulation time per phase")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{directory}/switched/mean_simtime_comparison.png")
    plt.clf()


# TODO
def plot_mean_success_prob_2d(dfs, directory, config_names):
    colors = plt.cm.tab10.colors[: len(dfs)]
    for i, (df, config_name, color) in enumerate(zip(dfs, config_names, colors)):
        # Group by phase and dampening
        success_rate = df.groupby("dampening_parameter")["success"].mean().reset_index()
        # Plot
        plt.plot(
            success_rate["dampening_parameter"],
            success_rate["success"],
            marker="o",
            label=config_name,
            color=color,
        )

    plt.xlabel("Dampening Parameter")
    plt.ylabel("Success Probability")
    plt.title("Success Probability vs Dampening Parameter")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{directory}/switched/success_prob_comparison.png")
    plt.clf()


# TODO
def plot_mean_operation_count_2d(dfs, directory, config_names):
    colors = plt.cm.tab10.colors[: len(dfs)]
    plt.figure(figsize=(10, 6))
    for i, (df, config_name, color) in enumerate(zip(dfs, config_names, colors)):
        ops_stats = (
            df.groupby("dampening_parameter")["quantum_ops"].mean().reset_index()
        )

        plt.plot(
            ops_stats["dampening_parameter"],
            ops_stats["quantum_ops"],
            marker="o",
            label=config_name,
            color=color,
        )

    plt.xlabel("Dampening Parameter")
    plt.ylabel("Mean Quantum Ops")
    plt.title("Mean Quantum Ops vs Dampening")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{directory}/switched/quantum_ops_comparison.png")
    plt.clf()
