import math
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns


# ==== Heatmap plots ====
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd


def plot_adjacency_heatmap(df, directory):
    # Step 1: Filter successful entries
    filtered = df[df["success"]]

    # Get unique phases (max 4 for subplot layout)
    phases = sorted(filtered["phase"].unique())
    n_phases = len(phases)

    # Step 2: Set up subplots
    fig, axes = plt.subplots(1, n_phases, figsize=(6 * n_phases, 6), squeeze=False)

    for i, phase in enumerate(phases):
        phase_df = filtered[filtered["phase"] == phase]

        # Step 3: Compute mean fidelities
        fidelity_df = (
            phase_df.groupby(["qnode_1", "qnode_2"])["fidelity"].mean().reset_index()
        )

        # Step 4: Extract numerical node indices
        fidelity_df["qnode_1"] = (
            fidelity_df["qnode_1"].str.extract(r"(\d+)").astype(int)
        )
        fidelity_df["qnode_2"] = (
            fidelity_df["qnode_2"].str.extract(r"(\d+)").astype(int)
        )

        # Step 5: Make matrix symmetric
        mirror_df = fidelity_df.rename(
            columns={"qnode_1": "qnode_2", "qnode_2": "qnode_1"}
        )
        symmetric_df = pd.concat([fidelity_df, mirror_df], ignore_index=True)

        # Step 6: Add diagonal entries (fidelity = 1.0)
        nodes = sorted(set(symmetric_df["qnode_1"]) | set(symmetric_df["qnode_2"]))
        diag_df = pd.DataFrame({"qnode_1": nodes, "qnode_2": nodes, "fidelity": 1.0})
        symmetric_df = pd.concat([symmetric_df, diag_df], ignore_index=True)

        # Step 7: Pivot to square matrix
        matrix = symmetric_df.pivot(
            index="qnode_1", columns="qnode_2", values="fidelity"
        )
        matrix = matrix.sort_index().sort_index(axis=1)
        matrix = matrix.fillna(0)

        # Step 8: Plot the heatmap for this phase
        ax = axes[0, i]
        sns.heatmap(
            matrix,
            annot=True,
            cmap="inferno",
            square=True,
            cbar=False,  # Show colorbar only on last plot to save space
            cbar_kws={"label": "Fidelity"},
            vmin=np.min(matrix),
            vmax=1,
            ax=ax,
        )
        title = phase.replace("_", " ").title()
        ax.set_title(title)
        ax.set_xlabel("QNode ID")
        ax.set_ylabel("QNode ID")

    plt.tight_layout()
    plt.savefig(f"{directory}/adjacency_fidelity_heatmap_phases.png")
    plt.clf()


def plot_mean_fidelity_heatmap(dfs, directory, config_names):
    """
    Plot mean fidelities as heatmaps in a grid layout for multiple dataframes.

    Parameters:
    - dfs: List of dataframes, each representing a different switch configuration
    - config_names: List of configuration names corresponding to the dataframes
    - figsize: Tuple for figure size (default: (12, 10))

    Returns:
    - matplotlib.pyplot object
    """
    figsize = (12, 10)
    num_plots = len(dfs)
    cols = 2
    rows = math.ceil(num_plots / cols)

    fig, axes = plt.subplots(rows, cols, figsize=figsize)
    axes = axes.flatten()  # Makes it easier to index

    for i, (df, config_name) in enumerate(zip(dfs, config_names)):
        ax = axes[i]

        success_df = df[df["success"]]

        heatmap_data = (
            success_df.groupby(["dampening_parameter", "visibility"])["fidelity"]
            .mean()
            .reset_index()
        )

        pivot_data = heatmap_data.pivot(
            index="dampening_parameter", columns="visibility", values="fidelity"
        )

        # Format x/y ticks to 3 decimal places
        pivot_data.index = [f"{x:.3f}" for x in pivot_data.index]
        pivot_data.columns = [f"{x:.3f}" for x in pivot_data.columns]

        sns.heatmap(
            pivot_data,
            cmap="inferno",
            annot=True,
            fmt=".2f",
            cbar_kws={"label": "Mean Fidelity"},
            ax=ax,
        )

        ax.set_title(f"Mean Fidelity Heatmap - {config_name}")
        ax.set_xlabel("HOM Visibility")
        ax.set_ylabel("Dampening Parameter")

    # Hide any unused subplots
    for j in range(i + 1, len(axes)):
        fig.delaxes(axes[j])

    fig.tight_layout()

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

        # Find the best phase for each dampening_parameter and visibility combination
        best_phase_data = success_df.loc[
            success_df.groupby(["dampening_parameter", "visibility"])[
                "fidelity"
            ].idxmax()
        ]

        # Create pivot table with best phases converted to numeric values
        pivot_data = best_phase_data.pivot(
            index="dampening_parameter", columns="visibility", values="phase"
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

        # Format dampening and HOM visibility to 3 significant figures
        dampening_ticks = [f"{x:.3g}" for x in pivot_data.index]
        visibility_ticks = [f"{x:.3g}" for x in pivot_data.columns]

        # Set x and y ticks
        plt.xticks(
            range(len(pivot_data.columns)), visibility_ticks, rotation=45, ha="right"
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
                        columns="visibility",
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
        plt.xlabel("HOM Visibility")
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
    success_df = df  # [df["success"]]
    phases = sorted(success_df["phase"].unique())[:4]
    n_phases = len(phases)
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()
    fidelities, heatmap_data_list = [], []
    for phase in phases:
        phase_df = success_df[success_df["phase"] == phase]
        heatmap_data = (
            phase_df.groupby(["dampening_parameter", "visibility"])["fidelity"]
            .mean()
            .reset_index()
            .pivot(index="dampening_parameter", columns="visibility", values="fidelity")
        )
        heatmap_data_list.append(heatmap_data)
        fidelities.append(heatmap_data.values)
    all_vals = np.concatenate([vals[~np.isnan(vals)] for vals in fidelities])
    vmin, vmax = all_vals.min(), all_vals.max()
    for i, phase in enumerate(phases):
        ax = axes[i]
        pivot_data = heatmap_data_list[i]
        xticks = [f"{x:.2f}" for x in pivot_data.columns]
        yticks = [f"{y:.2f}" for y in pivot_data.index]
        sns.heatmap(
            pivot_data,
            cmap="inferno",
            annot=False,
            cbar=False,
            vmin=vmin,
            vmax=vmax,
            ax=ax,
            xticklabels=xticks,
            yticklabels=yticks,
        )
        title = phase.replace("_", " ").title()
        ax.set_title(f"{title}", pad=12)
        ax.set_xlabel("HOM Visibility")
        ax.set_ylabel("Dampening Parameter")
        ax.tick_params(axis="x", labelrotation=45)
    for j in range(n_phases, 4):
        fig.delaxes(axes[j])
    cbar_ax = fig.add_axes([0.92, 0.25, 0.015, 0.5])
    norm = plt.Normalize(vmin=vmin, vmax=vmax)
    sm = plt.cm.ScalarMappable(cmap="inferno", norm=norm)
    sm.set_array([])
    fig.colorbar(sm, cax=cbar_ax, label="Mean Fidelity")
    fig.subplots_adjust(wspace=0.4, hspace=0.4)  # tweak spacing as needed
    fig.suptitle("Mean Fidelity", fontsize=16)
    fig.savefig(f"{directory}/mean_phase_fidelity_heatmaps.png")
    fig.clf()


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
def plot_mean_success_prob_2d(dfs, directory):
    df = pd.concat(dfs, ignore_index=True)
    plt.figure(figsize=(10, 6))

    for config_name, group in df.groupby("config"):
        success_rate = (
            group.groupby("dampening_parameter")["success"].mean().reset_index()
        )
        plt.plot(
            success_rate["dampening_parameter"],
            success_rate["success"],
            marker="o",
            label=config_name,
        )

    plt.xlabel("Dampening parameter")
    plt.ylabel("Success probability")
    plt.title("Success probability per switching configuration")
    plt.ylim(0, 1.05)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{directory}/switched/success_prob_comparison.png")
    plt.clf()


# TODO
def plot_mean_operation_count_2d(dfs, directory):
    df = pd.concat(dfs, ignore_index=True)
    plt.figure(figsize=(10, 6))

    for config_name, group in df.groupby("config"):
        ops_stats = (
            group.groupby("dampening_parameter")["quantum_ops"].mean().reset_index()
        )
        plt.plot(
            ops_stats["dampening_parameter"],
            ops_stats["quantum_ops"],
            marker="o",
            label=config_name,
        )

    plt.xlabel("Dampening parameter")
    plt.ylabel("Mean quantum operations")
    plt.title("Mean quantum ops per switching configuration")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{directory}/switched/quantum_ops_comparison.png")
    plt.clf()


# TODO
def plot_switch_fidelity_2d(dfs, directory):
    df = pd.concat(dfs, ignore_index=True)
    plt.figure(figsize=(10, 6))

    for config_name, group in df[df["success"]].groupby("config"):
        mean_fidelity = (
            group.groupby("dampening_parameter")["fidelity"].mean().reset_index()
        )
        plt.plot(
            mean_fidelity["dampening_parameter"],
            mean_fidelity["fidelity"],
            marker="o",
            label=config_name,
        )

    plt.xlabel("Dampening parameter")
    plt.ylabel("Mean ebit fidelity")
    plt.title("Fidelity per switching configuration")
    plt.ylim(0, 1.05)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{directory}/switched/switched_fidelity_comparison.png")
    plt.clf()
