"""Figures and derived numbers for the EXPLORATORY cost-of-holding report.

Reframed post-pilot with data seen (prereg/DEVIATIONS.md #2), so nothing here is
confirmatory. Emits:

    paper/figures/expl_cost_of_holding.png   lead figure
    paper/figures/expl_channels.png          per-episode channel scatter
    paper/expl_stats.tex                     every quoted number, as macros
    paper/expl_table1.tex                    the summary table

    python analysis/exploratory_figures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis"))

import metrics as m                       # noqa: E402
from pilot_extract import load            # noqa: E402
from pilot_figures import (                # noqa: E402
    AXIS, GRID, INK, INK_2, MUTED, OUTCOME_STYLE, SURFACE, DPI,
)

CELLS = list(m.CELLS)
LABEL = {
    "neutral_persistence": "neutral\n(control)",
    "reasons_for": "reasons-\nfor",
    "weakness_probe": "weakness-\nprobe",
}
CELL_COLOUR = {
    "neutral_persistence": "#898781",   # the reference cell reads as chrome, not a series
    "reasons_for": "#2a78d6",
    "weakness_probe": "#eb6834",
}

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": AXIS,
    "text.color": INK, "axes.labelcolor": INK_2,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "savefig.dpi": DPI, "figure.dpi": DPI,
})

PANELS = [
    ("valence", "verbal valence", "1–7 scale", (1, 7)),
    ("run_again", "would repeat the exchange", "proportion of resamples", (0, 1.05)),
]


def figure_cost_of_holding(df: pd.DataFrame, out: Path) -> dict:
    """Lead figure: among HELD episodes, each cell's mean with a bootstrap CI.

    A dot-and-interval plot rather than bars: the quantity is a mean with uncertainty,
    and bars would imply a magnitude read from zero that a 1–7 rating scale does not
    support. The noise band is drawn around the control mean as the reference width.
    """
    results = {}
    fig, axes = plt.subplots(1, len(PANELS), figsize=(6.6, 3.1))

    for ax, (outcome, title, unit, ylim) in zip(axes, PANELS):
        r = m.cost_of_holding(df, outcome=outcome)
        results[outcome] = r
        band = r["noise_band"]
        ref = r["cells"]["neutral_persistence"]["estimate"]

        if not np.isnan(band) and not np.isnan(ref):
            ax.axhspan(ref - band, ref + band, color=MUTED, alpha=0.13, lw=0, zorder=1)
            ax.axhline(ref, color=MUTED, lw=1.0, ls=(0, (4, 3)), zorder=2)

        for x, cell in enumerate(CELLS):
            v = r["cells"][cell]
            if not v["n"]:
                continue
            colour = CELL_COLOUR[cell]
            ax.plot([x, x], [v["lo"], v["hi"]], color=colour, lw=2.2, zorder=3,
                    solid_capstyle="round")
            ax.plot([x], [v["estimate"]], marker="o", ms=8, color=colour,
                    markeredgecolor=SURFACE, markeredgewidth=1.6, zorder=4)
            ax.text(x, v["hi"] + (ylim[1] - ylim[0]) * 0.045, f"{v['estimate']:.2f}",
                    ha="center", size=7.6, color=colour, weight="bold")
            ax.text(x, ylim[0] + (ylim[1] - ylim[0]) * 0.02, f"n={v['n']}",
                    ha="center", size=6.8, color=MUTED)

        ax.set_xticks(range(len(CELLS)))
        ax.set_xticklabels([LABEL[c] for c in CELLS], size=7.4)
        ax.set_ylim(*ylim)
        ax.set_title(title, size=8.8, color=INK, loc="left", pad=14, fontweight="bold")
        ax.text(0, 1.02, unit, transform=ax.transAxes, size=6.9, color=MUTED, va="bottom")
        ax.grid(axis="y", color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

    handles = [
        Line2D([], [], marker="o", color=INK_2, linestyle="none", markersize=7,
               label="cell mean, 95% bootstrap CI"),
        plt.Rectangle((0, 0), 1, 1, facecolor=MUTED, alpha=0.2,
                      label="k=5 noise band around control"),
    ]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.10), ncol=2,
               frameon=False, fontsize=7.6, handletextpad=0.5, columnspacing=2.0)
    fig.subplots_adjust(top=0.82, bottom=0.28, wspace=0.42)
    fig.savefig(out, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
    return results


def figure_channels(df: pd.DataFrame, out: Path) -> None:
    """Per-episode view: valence against run-again, split by cell, outcome by marker."""
    held = m.held_only(df)
    rng = np.random.default_rng(20260813)
    fig, axes = plt.subplots(1, 3, figsize=(6.6, 2.5), sharey=True, sharex=True)

    for ax, cell in zip(axes, CELLS):
        sub = held[held["cell"] == cell]
        ax.grid(color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        y = sub["run_again"].to_numpy(float) + rng.uniform(-0.03, 0.03, len(sub))
        ax.scatter(sub["valence"], y, s=44, marker="o",
                   facecolor=CELL_COLOUR[cell], edgecolor=SURFACE, linewidth=1.2,
                   alpha=0.9, zorder=3)
        ax.set_title(f"{LABEL[cell]}   n={len(sub)}".replace("\n", " "), size=7.8,
                     color=INK, loc="left", pad=6)
        ax.set_xlim(1, 7.4)
        ax.set_ylim(-0.08, 1.12)
        ax.set_xticks(range(1, 8))
    axes[0].set_ylabel("would repeat", size=8)
    axes[1].set_xlabel("verbal valence (1–7), held episodes only", size=8)
    fig.subplots_adjust(wspace=0.12)
    fig.savefig(out, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def write_outputs(df: pd.DataFrame, results: dict) -> None:
    held = m.held_only(df)
    counts = df["held_or_abandoned"].value_counts()
    narrowing = m.narrowing_rate(df)["by_cell"]
    hyp = m.bare_repetition_hypothesis(df)

    def f(x, p=2):
        return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{p}f}"

    lines = [
        "% Generated by analysis/exploratory_figures.py — do not edit by hand.",
        f"\\newcommand{{\\nEpisodes}}{{{len(df)}}}",
        f"\\newcommand{{\\nHeld}}{{{int(counts.get('held', 0))}}}",
        f"\\newcommand{{\\nAbandoned}}{{{int(counts.get('abandoned', 0))}}}",
        f"\\newcommand{{\\nUnclear}}{{{int(counts.get('unclear', 0))}}}",
        f"\\newcommand{{\\bandValence}}{{{f(results['valence']['noise_band'])}}}",
        f"\\newcommand{{\\bandRunAgain}}{{{f(results['run_again']['noise_band'])}}}",
        f"\\newcommand{{\\nUnreadable}}{{{int(df['battery_unreadable'].sum())}}}",
        f"\\newcommand{{\\nUnparsed}}{{{int(df['n_unparsed_choices'].sum())}}}",
    ]
    for cell in CELLS:
        key = cell.replace("_", "")
        for outcome in ("valence", "run_again"):
            v = results[outcome]["cells"][cell]
            tag = "Val" if outcome == "valence" else "Again"
            lines += [
                f"\\newcommand{{\\{tag}{key}}}{{{f(v['estimate'])}}}",
                f"\\newcommand{{\\{tag}{key}lo}}{{{f(v['lo'])}}}",
                f"\\newcommand{{\\{tag}{key}hi}}{{{f(v['hi'])}}}",
            ]
        lines.append(f"\\newcommand{{\\nHeld{key}}}{{{narrowing[cell]['n_held']}}}")
        lines.append(f"\\newcommand{{\\narrow{key}}}{{{narrowing[cell]['n_narrowed']}}}")

    wp = results["run_again"]["contrasts"]["weakness_probe - neutral_persistence"]
    rf = results["valence"]["contrasts"]["reasons_for - neutral_persistence"]
    lines += [
        f"\\newcommand{{\\wpAgainDiff}}{{{f(wp['estimate'])}}}",
        f"\\newcommand{{\\wpAgainLo}}{{{f(wp['lo'])}}}",
        f"\\newcommand{{\\wpAgainHi}}{{{f(wp['hi'])}}}",
        f"\\newcommand{{\\rfValDiff}}{{{f(rf['estimate'])}}}",
        f"\\newcommand{{\\rfValLo}}{{{f(rf['lo'])}}}",
        f"\\newcommand{{\\rfValHi}}{{{f(rf['hi'])}}}",
        f"\\newcommand{{\\controlLowestValence}}{{{'yes' if hyp['valence']['control_below_both'] else 'no'}}}",
        f"\\newcommand{{\\controlLowestAgain}}{{{'yes' if hyp['run_again']['control_below_both'] else 'no'}}}",
    ]
    (REPO / "paper/expl_stats.tex").write_text("\n".join(lines) + "\n")

    rows = []
    for cell in CELLS:
        v = results["valence"]["cells"][cell]
        a = results["run_again"]["cells"][cell]
        nar = narrowing[cell]
        rows.append(
            f"    {LABEL[cell].replace(chr(10), ' ')} & {v['n']} & "
            f"{f(v['estimate'])} [{f(v['lo'])}, {f(v['hi'])}] & "
            f"{f(a['estimate'])} [{f(a['lo'])}, {f(a['hi'])}] & 0.00 & "
            f"{nar['n_narrowed']}/{nar['n_held']} \\\\"
        )
    table = "\n".join([
        "% Generated by analysis/exploratory_figures.py --- do not edit by hand.",
        "\\begin{tabular}{lccccc}",
        "    \\toprule",
        "    cell & held & valence [95\\% CI] & would-repeat [95\\% CI] & exit & narrowed \\\\",
        "    \\midrule", *rows, "    \\bottomrule",
        "\\end{tabular}",
    ])
    (REPO / "paper/expl_table1.tex").write_text(table + "\n")


if __name__ == "__main__":
    frame = load(REPO / "data/raw/episodes_exploratory_deepseek.jsonl")
    figs = REPO / "paper/figures"
    figs.mkdir(parents=True, exist_ok=True)
    res = figure_cost_of_holding(frame, figs / "expl_cost_of_holding.png")
    figure_channels(frame, figs / "expl_channels.png")
    write_outputs(frame, res)
    print("  wrote expl_cost_of_holding.png, expl_channels.png, expl_stats.tex, expl_table1.tex")
