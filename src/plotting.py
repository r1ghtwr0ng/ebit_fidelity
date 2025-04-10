import matplotlib.pyplot as plt
import pandas as pd
import time
import os

import matplotlib.pyplot as plt
import pandas as pd
import time
import os


def plot_metadata(df_metadata, config_name):
    # Columns: run detector_efficiency dampening_parameter run_id ideal status simtime quantum_ops
    timestamp = int(time.time())

    unique_eff = df_metadata["detector_efficiency"].unique()
    if len(unique_eff) > 1:
        # TODO: implement heatmap if multiple detector efficiencies
        print("Multiple detector_efficiency values detected — skipping plots.")
        pass
    else:
        grouped = df_metadata.groupby("dampening_parameter")

        # 1. Mean simtime
        simtime_stats = grouped["simtime"].agg(["mean", "std"]).reset_index()
        plt.errorbar(
            simtime_stats["dampening_parameter"],
            simtime_stats["mean"],
            yerr=simtime_stats["std"],
            fmt="o-",
            capsize=4,
        )
        plt.xlabel("Dampening Parameter")
        plt.ylabel("Average Simtime")
        plt.title("Average Simtime vs Dampening")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(f"./plots/2d/simtime_vs_dampening_{config_name}_{timestamp}.png")
        plt.clf()

        # 2. Mean quantum_ops
        ops_stats = grouped["quantum_ops"].agg(["mean", "std"]).reset_index()
        plt.errorbar(
            ops_stats["dampening_parameter"],
            ops_stats["mean"],
            yerr=ops_stats["std"],
            fmt="o-",
            capsize=4,
        )
        plt.xlabel("Dampening Parameter")
        plt.ylabel("Average Quantum Ops")
        plt.title("Average Quantum Ops vs Dampening")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(
            f"./plots/2d/quantum_ops_vs_dampening_{config_name}_{timestamp}.png"
        )
        plt.clf()

        # 3. Success probability (status == True)
        success_rate = grouped["status"].mean().reset_index()
        plt.plot(
            success_rate["dampening_parameter"], success_rate["status"], marker="o"
        )
        plt.xlabel("Dampening Parameter")
        plt.ylabel("Success Probability")
        plt.title("Success Probability vs Dampening")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(
            f"./plots/2d/success_prob_vs_dampening_{config_name}_{timestamp}.png"
        )
        plt.clf()


def plot_events(df_events, config_name):
    # Columns: fidelity simtime attempt_log success phase attempt total_attempts time run detector_efficiency dampening_parameter
    timestamp = int(time.time())

    unique_eff = df_events["detector_efficiency"].unique()
    if len(unique_eff) > 1:
        # TODO: implement heatmap if multiple detector efficiencies
        print("Multiple detector_efficiency values detected — skipping plots.")
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
            "o-",
            label="Successful attempts",
        )
        plt.xlabel("Dampening Parameter")
        plt.ylabel("Mean Fidelity")
        plt.title("Fidelity Comparison vs Dampening")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(f"./plots/2d/fidelity_comparison_{config_name}_{timestamp}.png")
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
        plt.savefig(f"./plots/2d/event_success_prob_{config_name}_{timestamp}.png")
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
        plt.savefig(f"./plots/2d/phase_success_{config_name}_{timestamp}.png")
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
        plt.savefig(f"./plots/2d/fidelity_per_phase_{config_name}_{timestamp}.png")
        plt.clf()
