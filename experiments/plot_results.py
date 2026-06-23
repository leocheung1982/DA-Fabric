#!/usr/bin/env python3
"""
Generate publication-ready figures from experiment CSV results.

Reads aggregated/per-run CSVs under results/ and writes PNG + PDF figures
under results/figures/ suitable for IEEE two-column papers.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RESULTS_DIR = ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"

# IEEE-friendly palette (colorblind-safe, prints well in grayscale)
COLORS = ["#000000", "#555555", "#888888", "#AAAAAA", "#CCCCCC", "#333333"]
METHOD_ORDER = [
    "KW-Catalog",
    "Semantic-Only",
    "Supply-Fabric",
    "DA-Fabric",
    "DA-Fabric+Feedback",
]
ORCH_ORDER = ["Supply-Fabric", "DA-Fabric"]
PROACTIVE_ORDER = ["Subscription-Only", "DA-Proactive"]


def apply_ieee_style() -> None:
    """Configure matplotlib for IEEE-style figures."""
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "DejaVu Serif", "serif"],
            "font.size": 10,
            "axes.labelsize": 10,
            "axes.titlesize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.02,
            "axes.linewidth": 0.8,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "grid.linewidth": 0.5,
            "lines.linewidth": 1.5,
            "lines.markersize": 5,
            "patch.linewidth": 0.6,
        }
    )


def save_figure(fig: plt.Figure, stem: str) -> None:
    """Save figure as PNG and PDF."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    png_path = FIGURES_DIR / f"{stem}.png"
    pdf_path = FIGURES_DIR / f"{stem}.pdf"
    fig.savefig(png_path)
    fig.savefig(pdf_path)
    plt.close(fig)
    print(f"  Saved {png_path.name} and {pdf_path.name}")


def load_csv(name: str) -> pd.DataFrame | None:
    path = RESULTS_DIR / name
    if not path.exists():
        print(f"  Skipping {name} (not found — run experiments first)")
        return None
    return pd.read_csv(path)


def grouped_bar(
    ax: plt.Axes,
    labels: list[str],
    metrics: dict[str, list[float]],
    ylabel: str,
    *,
    ylim: tuple[float, float] | None = None,
    rotate: int = 35,
) -> None:
    """Draw grouped bar chart for multiple metrics over categorical labels."""
    metric_names = list(metrics.keys())
    n_groups = len(labels)
    n_metrics = len(metric_names)
    x = np.arange(n_groups)
    width = 0.8 / max(n_metrics, 1)

    for i, name in enumerate(metric_names):
        offset = (i - (n_metrics - 1) / 2) * width
        ax.bar(
            x + offset,
            metrics[name],
            width,
            label=name,
            color=COLORS[i % len(COLORS)],
            edgecolor="black",
            linewidth=0.4,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=rotate, ha="right")
    ax.set_ylabel(ylabel)
    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.22), ncol=min(n_metrics, 4), frameon=False)


def plot_matching_metrics(df: pd.DataFrame) -> None:
    summary = (
        df.groupby("method")[["precision_at_5", "recall_at_5", "ndcg_at_5", "mrr"]]
        .mean()
        .reindex(METHOD_ORDER)
        .dropna(how="all")
    )
    if summary.empty:
        print("  Skipping matching_metrics (no data)")
        return

    labels = [m.replace("DA-Fabric+Feedback", "DA-Fabric\n+Feedback") for m in summary.index.tolist()]
    metrics = {
        "P@5": summary["precision_at_5"].tolist(),
        "R@5": summary["recall_at_5"].tolist(),
        "NDCG@5": summary["ndcg_at_5"].tolist(),
        "MRR": summary["mrr"].tolist(),
    }

    fig, ax = plt.subplots(figsize=(7.0, 3.2))
    grouped_bar(ax, labels, metrics, "Score", ylim=(0, 1.05))
    fig.subplots_adjust(top=0.78)
    save_figure(fig, "matching_metrics")


def plot_view_construction_latency(df: pd.DataFrame) -> None:
    df = df.sort_values("resource_scale")
    scales = df["resource_scale"].astype(int).tolist()

    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    ax.plot(
        scales,
        df["avg_matching_time_ms"],
        marker="o",
        color=COLORS[0],
        label="Matching",
    )
    ax.plot(
        scales,
        df["avg_view_construction_time_ms"],
        marker="s",
        color=COLORS[1],
        linestyle="--",
        label="View construction",
    )
    ax.set_xscale("log")
    ax.set_xticks(scales)
    ax.set_xticklabels([str(s) for s in scales])
    ax.set_xlabel("Resource catalog size")
    ax.set_ylabel("Latency (ms)")
    ax.legend(loc="upper left", frameon=False)
    save_figure(fig, "view_construction_latency")


def plot_orchestration_comparison(df: pd.DataFrame) -> None:
    summary = (
        df.groupby("method")
        .agg(
            invoked_nodes=("invoked_nodes", "mean"),
            invoked_resources=("invoked_resources", "mean"),
            redundant_ratio=("redundant_invocation_ratio", "mean"),
            latency_ms=("end_to_end_latency_ms", "mean"),
        )
        .reindex(ORCH_ORDER)
        .dropna(how="all")
    )
    if summary.empty:
        print("  Skipping orchestration_comparison (no data)")
        return

    labels = summary.index.tolist()
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.0))

    left_metrics = {
        "Invoked nodes": summary["invoked_nodes"].tolist(),
        "Invoked resources": summary["invoked_resources"].tolist(),
    }
    grouped_bar(axes[0], labels, left_metrics, "Count", rotate=0)
    axes[0].legend(loc="upper right", frameon=False)

    right_metrics = {
        "Redundant ratio": summary["redundant_ratio"].tolist(),
        "Latency (ms)": summary["latency_ms"].tolist(),
    }
    grouped_bar(axes[1], labels, right_metrics, "Value", rotate=0)
    axes[1].legend(loc="upper right", frameon=False)

    fig.subplots_adjust(wspace=0.35)
    save_figure(fig, "orchestration_comparison")


def plot_proactive_delivery(df: pd.DataFrame) -> None:
    summary = (
        df.groupby("method")
        .agg(
            delivery_precision=("delivery_precision", "mean"),
            adoption_rate=("adopted", "mean"),
            ignored_rate=("ignored", "mean"),
            time_to_awareness_ms=("time_to_awareness_ms", "mean"),
        )
        .reindex(PROACTIVE_ORDER)
        .dropna(how="all")
    )
    if summary.empty:
        print("  Skipping proactive_delivery (no data)")
        return

    labels = summary.index.tolist()
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.0))

    rate_metrics = {
        "Delivery precision": summary["delivery_precision"].tolist(),
        "Adoption rate": summary["adoption_rate"].tolist(),
        "Ignored rate": summary["ignored_rate"].tolist(),
    }
    grouped_bar(axes[0], labels, rate_metrics, "Rate", ylim=(0, 1.05), rotate=15)
    axes[0].legend(loc="upper right", frameon=False)

    latency_metrics = {
        "Time-to-awareness (ms)": summary["time_to_awareness_ms"].tolist(),
    }
    grouped_bar(axes[1], labels, latency_metrics, "Latency (ms)", rotate=15)
    axes[1].legend(loc="upper right", frameon=False)

    fig.subplots_adjust(wspace=0.35)
    save_figure(fig, "proactive_delivery")


def plot_ablation_results(df: pd.DataFrame) -> None:
    if df.empty:
        print("  Skipping ablation_results (no data)")
        return

    labels = [
        c.replace("w/o ", "−")
        .replace("Full DA-Fabric", "Full")
        .replace("semantic mapping", "sem. map.")
        .replace("application-side nodes", "app nodes")
        for c in df["config"]
    ]

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.2))

    quality = {
        "P@5": df["precision_at_5"].tolist(),
        "NDCG@5": df["ndcg_at_5"].tolist(),
    }
    grouped_bar(axes[0], labels, quality, "Score", ylim=(0, max(df["precision_at_5"].max(), 0.25)), rotate=40)
    axes[0].legend(loc="upper right", frameon=False)

    operational = {
        "Invoked nodes": df["invoked_nodes"].tolist(),
        "Delivery precision": df["delivery_precision"].tolist(),
    }
    grouped_bar(axes[1], labels, operational, "Value", rotate=40)
    axes[1].legend(loc="upper right", frameon=False)

    fig.subplots_adjust(wspace=0.35, top=0.88)
    save_figure(fig, "ablation_results")


def main() -> None:
    print("Generating figures...")
    apply_ieee_style()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    matching = load_csv("matching_results.csv")
    if matching is not None:
        plot_matching_metrics(matching)

    view = load_csv("view_results.csv")
    if view is not None:
        plot_view_construction_latency(view)

    orchestration = load_csv("orchestration_results.csv")
    if orchestration is not None:
        plot_orchestration_comparison(orchestration)

    proactive = load_csv("proactive_results.csv")
    if proactive is not None:
        plot_proactive_delivery(proactive)

    ablation = load_csv("ablation_results.csv")
    if ablation is not None:
        plot_ablation_results(ablation)

    print(f"\nFigures saved to {FIGURES_DIR}")


if __name__ == "__main__":
    main()
