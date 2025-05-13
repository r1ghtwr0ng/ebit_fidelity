import logging
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns


# ==== Heatmap plots ====
def plot_mean_fidelity_heatmap(dfs, directory, config_names):
    """
    Plot mean fidelities as heatmaps for multiple dataframes (switch configurations)

    Parameters:
    - dfs: List of dataframes, each representing a different switch configuration
    - directory: Directory to save the plots
    - config_names: List of configuration names corresponding to the dataframes
    """
    plt.figure(figsize=(15, 5 * len(dfs)))

    for i, (df, config_name) in enumerate(zip(dfs, config_names)):
        # Filter successful runs
        success_df = df[df["success"]]

        # Group by dampening_parameter and depolar_rate, calculate mean fidelity
        heatmap_data = (
            success_df.groupby(["dampening_parameter", "depolar_rate"])["fidelity"]
            .mean()
            .reset_index()
        )

        # Pivot the data to create a matrix suitable for heatmap
        pivot_data = heatmap_data.pivot(
            index="dampening_parameter", columns="depolar_rate", values="fidelity"
        )

        # Create subplot for this configuration
        plt.subplot(len(dfs), 1, i + 1)

        # Create heatmap with explicit x and y ticks
        sns.heatmap(
            pivot_data,
            cmap="inferno",
            annot=True,
            fmt=".3f",
            cbar_kws={"label": "Mean Fidelity"},
            xticklabels=pivot_data.columns,
            yticklabels=pivot_data.index,
        )

        plt.title(f"Mean Fidelity Heatmap - {config_name}")
        plt.xlabel("Depolarization Rate")
        plt.ylabel("Dampening Parameter")

    plt.tight_layout()
    plt.savefig(f"{directory}/mean_fidelity_heatmaps.png")
    plt.clf()


def plot_best_fidelity_phase_heatmap(dfs, directory, config_names):
    """
    Plot heatmaps showing the best phase for each parameter configuration based on fidelity

    Parameters:
    - dfs: List of dataframes, each representing a different switch configuration
    - directory: Directory to save the plots
    - config_names: List of configuration names corresponding to the dataframes
    """
    # Define phase to numeric mapping
    phase_order = ["initial", "distillation_1", "distillation_2", "distillation_3"]
    phase_to_num = {phase: idx for idx, phase in enumerate(phase_order)}

    plt.figure(figsize=(15, 5 * len(dfs)))

    for i, (df, config_name) in enumerate(zip(dfs, config_names)):
        # Filter successful runs
        success_df = df[df["success"]]

        # Find the best phase for each dampening_parameter and depolar_rate combination
        best_phase_data = success_df.loc[
            success_df.groupby(["dampening_parameter", "depolar_rate"])[
                "fidelity"
            ].idxmax()
        ]

        # Create pivot table with best phases converted to numeric values
        pivot_data = best_phase_data.pivot(
            index="dampening_parameter", columns="depolar_rate", values="phase"
        ).applymap(lambda x: phase_to_num.get(x, np.nan))

        # Create subplot for this configuration
        plt.subplot(len(dfs), 1, i + 1)

        # Create custom colormap with distinct colors for each phase
        colors = [
            "#1f77b4",
            "#ff7f0e",
            "#2ca02c",
            "#d62728",
        ]  # blue, orange, green, red
        cmap = mcolors.ListedColormap(colors[: len(phase_order)])
        bounds = np.arange(len(phase_order) + 1) - 0.5
        norm = mcolors.BoundaryNorm(bounds, cmap.N)

        # Plot heatmap
        im = plt.imshow(pivot_data, cmap=cmap, norm=norm, aspect="auto")

        # Format dampening and depolar rate to 3 significant figures
        dampening_ticks = [f"{x:.3g}" for x in pivot_data.index]
        depolar_ticks = [f"{x:.3g}" for x in pivot_data.columns]

        # Set x and y ticks
        plt.xticks(
            range(len(pivot_data.columns)), depolar_ticks, rotation=45, ha="right"
        )
        plt.yticks(range(len(pivot_data.index)), dampening_ticks)

        # Add text annotations
        for y in range(pivot_data.shape[0]):
            for x in range(pivot_data.shape[1]):
                val = pivot_data.iloc[y, x]
                if not np.isnan(val):
                    # Use the original phase name for text
                    phase_name = best_phase_data.pivot(
                        index="dampening_parameter",
                        columns="depolar_rate",
                        values="phase",
                    ).iloc[y, x]
                    plt.text(
                        x,
                        y,
                        phase_name,
                        ha="center",
                        va="center",
                        color="white" if val > len(phase_order) / 2 else "black",
                        fontweight="bold",
                    )

        # Create colorbar with phase names
        cbar = plt.colorbar(im, ticks=range(len(phase_order)))
        cbar.set_ticklabels(phase_order)

        plt.title(f"Best Fidelity Phase Heatmap - {config_name}")
        plt.xlabel("Depolarization Rate")
        plt.ylabel("Dampening Parameter")

    plt.tight_layout()
    plt.savefig(f"{directory}/best_fidelity_phase_heatmaps.png")
    plt.clf()


def plot_mean_phase_fidelity_heatmap(df, directory):
    """
    Plot mean fidelity heatmaps for each phase in a single dataframe

    Parameters:
    - df: Dataframe for a single switch configuration
    - directory: Directory to save the plots
    """
    # Filter successful runs
    success_df = df[df["success"]]

    # Get unique phases
    phases = sorted(success_df["phase"].unique())

    # Create subplots for each phase
    plt.figure(figsize=(15, 5 * len(phases)))

    for i, phase in enumerate(phases):
        # Filter for specific phase
        phase_df = success_df[success_df["phase"] == phase]

        # Group by dampening_parameter and depolar_rate, calculate mean fidelity
        heatmap_data = (
            phase_df.groupby(["dampening_parameter", "depolar_rate"])["fidelity"]
            .mean()
            .reset_index()
        )

        # Pivot the data to create a matrix suitable for heatmap
        pivot_data = heatmap_data.pivot(
            index="dampening_parameter", columns="depolar_rate", values="fidelity"
        )

        # Create subplot for this phase
        plt.subplot(len(phases), 1, i + 1)

        # Create heatmap with explicit x and y ticks
        sns.heatmap(
            pivot_data,
            cmap="inferno",
            annot=True,
            fmt=".3f",
            cbar_kws={"label": "Mean Fidelity"},
            xticklabels=pivot_data.columns,
            yticklabels=pivot_data.index,
        )

        plt.title(f"Mean Fidelity Heatmap - Phase: {phase}")
        plt.xlabel("Depolarization Rate")
        plt.ylabel("Dampening Parameter")

    plt.tight_layout()
    plt.savefig(f"{directory}/mean_phase_fidelity_heatmaps.png")
    plt.clf()


# ==== 2D plots ====
def plot_mean_fidelity_2d(df, directory):
    plt.figure(figsize=(10, 6))

    # Get unique phases from the dataframe
    phases = df["phase"].unique()

    # Colors
    colors = plt.cm.tab10.colors[: len(phases)]

    # Plot for each phase
    for phase, color in zip(phases, colors):
        # Filter data for this phase
        phase_data = df[(df["phase"] == phase) & df["success"]]

        # Only plot if we have successful runs for this phase
        if not phase_data.empty:
            # Calculate mean simulation time for each dampening parameter
            mean_simtime = (
                phase_data.groupby("dampening_parameter")["fidelity"]
                .mean()
                .reset_index()
            )
            plt.plot(
                mean_simtime["dampening_parameter"],
                mean_simtime["fidelity"],
                marker="o",
                label=f"Phase: {phase}",
                color=color,
            )

    plt.xlabel("Dampening parameter")
    plt.ylabel("Mean ebit fidelity")
    plt.title("Mean fidelity per phase")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{directory}/mean_fidelity_comparison.png")
    plt.clf()

    return


# def plot_switch_fidelity_2d(dfs, directory, config_names):
#    colors = plt.cm.tab10.colors[: len(dfs)]
#    plt.figure(figsize=(10, 6))
#
#    for i, (df, config_name, color) in enumerate(zip(dfs, config_names, colors)):
#        # Filter successful entries first
#        success_df = df[df["success"]]
#
#        # Then group by dampening parameter and calculate mean fidelity
#        mean_fidelity = (
#            success_df.groupby("dampening_parameter")["fidelity"].mean().reset_index()
#        )
#
#        plt.plot(
#            mean_fidelity["dampening_parameter"],
#            mean_fidelity["fidelity"],
#            marker="o",
#            label=config_name,
#            color=color,
#        )
#
#    plt.xlabel("Dampening parameter")
#    plt.ylabel("Mean ebit fidelity")
#    plt.title("Fidelity comparison per switching configuration")
#    plt.legend()
#    plt.grid(True)
#    plt.tight_layout()
#    plt.savefig(f"{directory}/switched/switched_fidelity_comparison.png")
#    plt.clf()


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

    plt.xlabel("Dampening parameter")
    plt.ylabel("Simulation time (ns)")
    plt.title("Mean simulation time per phase")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{directory}/mean_simtime_comparison.png")
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

    plt.xlabel("Dampening parameter")
    plt.ylabel("Success probability")
    plt.title("Success probability per switching configuration")
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

    plt.xlabel("Dampening parameter")
    plt.ylabel("Mean quantum ops")
    plt.title("Mean quantum ops per switching configuration")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{directory}/switched/quantum_ops_comparison.png")
    plt.clf()
