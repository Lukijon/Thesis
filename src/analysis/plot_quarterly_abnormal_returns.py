"""Charts for the quarterly abnormal-return checkpoint
(`compute_quarterly_abnormal_returns.py`) -- same palette/conventions as
`notebooks/poc_overview.ipynb`'s charts, for consistency.

Usage:
    python -m src.analysis.plot_quarterly_abnormal_returns
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948",
)
TEXT_PRIMARY, TEXT_SECONDARY, GRID = "#0b0b0b", "#52514e", "#e3e2dd"

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white", "axes.edgecolor": GRID,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "text.color": TEXT_PRIMARY, "axes.labelcolor": TEXT_SECONDARY,
    "xtick.color": TEXT_SECONDARY, "ytick.color": TEXT_SECONDARY, "font.size": 11,
})

OUT_DIR = Path("reports/figures")
POC = Path("data/interim/poc")


def chart_scatter(ar: pd.DataFrame) -> None:
    ar_reliable = ar[(ar["diagnostic_prev"] == "font_heading") & (ar["diagnostic_curr"] == "font_heading")]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True, sharex=True)
    for ax, (label, df, color) in zip(axes, [
        (f"All pairs (n={len(ar)})", ar, YELLOW),
        (f"Reliable extraction only (n={len(ar_reliable)})", ar_reliable, AQUA),
    ]):
        ax.scatter(df["cosine_similarity"], df["abnormal_return"], color=color, alpha=0.5, s=20, edgecolor="white", linewidth=0.3)
        z = np.polyfit(df["cosine_similarity"], df["abnormal_return"], 1)
        xs = np.array([df["cosine_similarity"].min(), df["cosine_similarity"].max()])
        ax.plot(xs, z[0] * xs + z[1], color=TEXT_PRIMARY, linewidth=1.2, linestyle="--")
        ax.axhline(0, color=GRID, linewidth=1)
        ax.set_title(label, loc="left", fontsize=12, color=TEXT_PRIMARY)
        ax.set_xlabel("Cosine similarity (quarter-over-quarter)")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:+.0%}"))
        ax.set_ylim(-1.5, 3)
    axes[0].set_ylabel("~1-quarter abnormal return\n(stock − Ibovespa, buy-and-hold)")
    fig.suptitle("Quarterly textual change vs. subsequent abnormal return", x=0.01, ha="left", fontsize=13, color=TEXT_PRIMARY)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(OUT_DIR / "quarterly_similarity_vs_abnormal_return.png", dpi=150)
    plt.close(fig)


def chart_boxplot_by_group(delisted: pd.DataFrame, current66: set[int], historical: set[int]) -> None:
    def group_of(cd):
        cd = int(cd)
        return "dropped_or_delisted" if cd in historical else ("stayed" if cd in current66 else None)

    delisted = delisted.copy()
    delisted["group"] = delisted["cd_cvm"].apply(group_of)
    delisted = delisted.dropna(subset=["group"])
    reliable = delisted[(delisted["diagnostic_prev"] == "font_heading") & (delisted["diagnostic_curr"] == "font_heading")]

    GROUP_ORDER = ["stayed", "dropped_or_delisted"]
    GROUP_LABELS = {"stayed": "Stayed in IBOV", "dropped_or_delisted": "Dropped / delisted"}
    GROUP_COLORS = {"stayed": AQUA, "dropped_or_delisted": ORANGE}

    fig, ax = plt.subplots(figsize=(7, 4.5))
    data = [reliable.loc[reliable["group"] == g, "cosine_similarity"] for g in GROUP_ORDER]
    bp = ax.boxplot(data, vert=False, widths=0.5, patch_artist=True, medianprops={"color": TEXT_PRIMARY})
    for patch, g in zip(bp["boxes"], GROUP_ORDER):
        patch.set_facecolor(GROUP_COLORS[g])
        patch.set_alpha(0.55)
        patch.set_edgecolor(GROUP_COLORS[g])
    ax.set_yticks([1, 2])
    ax.set_yticklabels([f"{GROUP_LABELS[g]} (n={len(d)})" for g, d in zip(GROUP_ORDER, data)])
    ax.set_xlabel("Cosine similarity, quarter-over-quarter")
    ax.set_title("Quarterly: dropped/delisted vs. stayed companies", loc="left", fontsize=13, color=TEXT_PRIMARY)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "quarterly_stayed_vs_dropped.png", dpi=150)
    plt.close(fig)


def chart_whole_notes_boxplot(full_notes: pd.DataFrame, current66: set[int], historical: set[int]) -> None:
    def group_of(cd):
        cd = int(cd)
        return "dropped_or_delisted" if cd in historical else ("stayed" if cd in current66 else None)

    full_notes = full_notes.copy()
    full_notes["group"] = full_notes["cd_cvm"].apply(group_of)
    full_notes = full_notes.dropna(subset=["group"])

    GROUP_ORDER = ["stayed", "dropped_or_delisted"]
    GROUP_LABELS = {"stayed": "Stayed in IBOV", "dropped_or_delisted": "Dropped / delisted"}
    GROUP_COLORS = {"stayed": AQUA, "dropped_or_delisted": ORANGE}

    fig, ax = plt.subplots(figsize=(7, 4.5))
    data = [full_notes.loc[full_notes["group"] == g, "cosine_similarity"] for g in GROUP_ORDER]
    bp = ax.boxplot(data, vert=False, widths=0.5, patch_artist=True, medianprops={"color": TEXT_PRIMARY})
    for patch, g in zip(bp["boxes"], GROUP_ORDER):
        patch.set_facecolor(GROUP_COLORS[g])
        patch.set_alpha(0.55)
        patch.set_edgecolor(GROUP_COLORS[g])
    ax.set_yticks([1, 2])
    ax.set_yticklabels([f"{GROUP_LABELS[g]} (n={len(d)})" for g, d in zip(GROUP_ORDER, data)])
    ax.set_xlabel("Cosine similarity, whole notes document, year-over-year")
    ax.set_title("Whole notes: dropped/delisted vs. stayed (p=0.0014)", loc="left", fontsize=12, color=TEXT_PRIMARY)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "full_notes_stayed_vs_dropped.png", dpi=150)
    plt.close(fig)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    from src.acquisition.b3_ibov_historical import NEW_HISTORICAL_CD_CVM

    current66 = set(pd.read_csv("data/interim/ibov_non_financial_universe.csv")["CD_CVM"].astype(int))
    historical = set(NEW_HISTORICAL_CD_CVM.keys())

    ar = pd.read_csv(POC / "abnormal_returns_itr.csv")
    chart_scatter(ar)

    delisted = pd.read_csv(POC / "itr_similarity_results.csv")
    delisted_labeled = delisted.rename(columns={"quarter_prev": "year_prev", "quarter_curr": "year_curr"})
    chart_boxplot_by_group(delisted, current66, historical)

    full_notes = pd.read_csv(POC / "full_notes_similarity_results.csv")
    chart_whole_notes_boxplot(full_notes, current66, historical)

    print(f"Charts written to {OUT_DIR}/")


if __name__ == "__main__":
    main()
