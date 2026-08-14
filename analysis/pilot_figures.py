"""Figures and derived numbers for the pilot report.

Emits, from the validated episode records:

    paper/figures/pilot_structure.pdf   Figure 1 — what one episode is
    paper/figures/pilot_channels.pdf    Figure 2 — the two channels by cell
    paper/pilot_stats.tex               every number quoted in the prose, as macros

The macros exist so no figure in the report is typed by hand. If the data changes and
the prose does not, the numbers still move — which is the only way a report and its
dataset stay honest with each other.

    python analysis/pilot_figures.py
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
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis"))

from pilot_extract import load, noise_band  # noqa: E402

INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#ffffff"

# dataviz reference palette, categorical slots 1-3; validated all-pairs in light mode
# (CVD dE 9.2, normal-vision 24.0). Shape carries the same distinction as colour.
OUTCOME_STYLE = {
    "held":      {"color": "#2a78d6", "marker": "o", "label": "held"},
    "abandoned": {"color": "#eb6834", "marker": "s", "label": "abandoned"},
    "partial":   {"color": "#1baf7a", "marker": "^", "label": "partial"},
    "unclear":   {"color": MUTED,     "marker": "X", "label": "unclear"},
}

CELL_ORDER = ["neutral_persistence", "reasons_for", "weakness_probe"]
CELL_LABEL = {
    "neutral_persistence": "neutral persistence (control)",
    "reasons_for": "pressure — reasons-for",
    "weakness_probe": "pressure — weakness-probe",
}

DPI = 220   # figures are emitted as PNG at print density

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans"],
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": AXIS,
    "text.color": INK,
    "axes.labelcolor": INK_2,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "savefig.dpi": DPI,
    "figure.dpi": DPI,
})


def figure_structure(out: Path) -> None:
    """Figure 1 — reader orientation. No data."""
    fig, ax = plt.subplots(figsize=(6.5, 1.65))
    ax.set_xlim(0, 100); ax.set_ylim(0, 26); ax.axis("off")

    boxes = [
        (1,  21, "1. Initial position\nmodel answers and\nstates its position", "#2a78d6"),
        (26, 21, "2. Pressure rungs x4\nscenario probe, then\nshared templates", "#eb6834"),
        (51, 21, "3. Affordance\nevery 2 rungs:\ncontinue / switch / stop", "#1baf7a"),
        (76, 23, "4. Battery x k=5\nvalence · state\nrun-again · confidence", "#4a3aa7"),
    ]
    for x, w, text, colour in boxes:
        ax.add_patch(FancyBboxPatch((x, 8), w, 13, boxstyle="round,pad=0.5,rounding_size=1.2",
                                    linewidth=1.3, edgecolor=colour, facecolor=colour + "14"))
        ax.text(x + w / 2, 14.5, text, ha="center", va="center", size=7.4, color=INK,
                linespacing=1.5)
    for x in (22.6, 47.6, 72.6):
        ax.add_patch(FancyArrowPatch((x, 14.5), (x + 2.4, 14.5), arrowstyle="-|>",
                                     mutation_scale=10, color=MUTED, lw=1.1))

    ax.text(50, 3.4,
            "confirm the model actually stated the position   →   apply pressure   →   "
            "real exit choice   →   measure how it registered",
            ha="center", size=7.2, color=INK_2, style="italic")
    fig.savefig(out, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def figure_outcomes(df: pd.DataFrame, out: Path) -> None:
    """The ceiling, shown directly: outcome composition per cell.

    A stacked bar is the right form here because the parts are shares of one fixed whole
    (ten episodes per cell) and the question is compositional — how much of each cell is
    'held' — rather than a magnitude comparison across cells.
    """
    fig, ax = plt.subplots(figsize=(6.5, 2.35))
    order = ["held", "partial", "abandoned"]
    y_pos = list(range(len(CELL_ORDER)))[::-1]

    for y, cell in zip(y_pos, CELL_ORDER):
        sub = df[df["cell"] == cell]
        counts = sub["held_or_abandoned"].value_counts()
        left = 0.0
        for outcome in order:
            n = int(counts.get(outcome, 0))
            if n == 0:
                continue
            style = OUTCOME_STYLE[outcome]
            ax.barh(y, n, left=left, height=0.52, color=style["color"],
                    edgecolor=SURFACE, linewidth=2.0, zorder=3)
            if n >= 2:   # only label a segment wide enough to hold the text
                ax.text(left + n / 2, y, str(n), ha="center", va="center",
                        color="white", size=9, weight="bold", zorder=4)
            left += n
        ax.text(left + 0.28, y, f"n = {len(sub)}", va="center", size=7.5, color=MUTED)

    ax.set_yticks(y_pos)
    ax.set_yticklabels([CELL_LABEL[c] for c in CELL_ORDER], size=8.5)
    ax.set_xlim(0, 12.2)
    ax.set_xticks(range(0, 11, 2))
    ax.set_xlabel("episodes", size=8.5)
    ax.grid(axis="x", color=GRID, lw=0.7)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(axis="y", length=0)

    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=OUTCOME_STYLE[o]["color"],
                             label=OUTCOME_STYLE[o]["label"]) for o in order]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0, 1.04), ncol=3,
              frameon=False, fontsize=8, handlelength=1.1, handletextpad=0.5,
              columnspacing=1.6)

    fig.savefig(out, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def figure_channels(df: pd.DataFrame, out: Path) -> None:
    """Figure 2 — verbal valence against run-again, split by cell, keyed to the outcome."""
    band = noise_band(df)["mean"]
    rng = np.random.default_rng(20260813)   # jitter for legibility only
    fig, axes = plt.subplots(3, 1, figsize=(6.5, 4.5), sharex=True)

    for i, (ax, cell) in enumerate(zip(axes, CELL_ORDER)):
        sub = df[df["cell"] == cell]
        ax.set_axisbelow(True)
        ax.grid(axis="x", color=GRID, lw=0.6)
        for spine in ("top", "right", "left"):
            ax.spines[spine].set_visible(False)
        ax.spines["bottom"].set_color(AXIS)
        ax.tick_params(axis="y", length=0)

        # Horizontal guides at the two response levels, so points read against a line
        # rather than floating in space.
        for level in (0, 1):
            ax.axhline(level, color=GRID, lw=0.9, zorder=1)

        if len(sub) and not np.isnan(band):
            mean_v = sub["valence"].mean()
            ax.axvspan(mean_v - band, mean_v + band, color="#2a78d6", alpha=0.09, lw=0,
                       zorder=2)
            ax.axvline(mean_v, color="#2a78d6", lw=1.6, zorder=2)
            ax.annotate(f"mean {mean_v:.2f}", xy=(mean_v, 1.52), xytext=(mean_v, 1.52),
                        ha="center", va="center", size=7.2, color="#2a78d6",
                        weight="bold",
                        bbox=dict(boxstyle="round,pad=0.25", facecolor=SURFACE,
                                  edgecolor="none"))

        for outcome, style in OUTCOME_STYLE.items():
            pts = sub[sub["held_or_abandoned"] == outcome]
            if pts.empty:
                continue
            # Wide jitter: nearly every episode sits on "would repeat", so without it the
            # points stack into a single illegible row.
            y = pts["run_again"].to_numpy(float) + rng.uniform(-0.17, 0.17, len(pts))
            ax.scatter(pts["valence"], y, s=62, marker=style["marker"],
                       facecolor=style["color"], edgecolor=SURFACE, linewidth=1.4,
                       alpha=0.9, zorder=4)

        n_ep, n_exit = len(sub), int(sub["exited"].sum())
        ax.set_title(f"{CELL_LABEL[cell]}", size=9, color=INK, loc="left", pad=16,
                     fontweight="bold")
        ax.text(0.0, 1.045, f"n = {n_ep}   ·   took the exit option: {n_exit}",
                transform=ax.transAxes, size=7.2, color=MUTED, va="bottom", ha="left")

        ax.set_xlim(0.5, 7.5); ax.set_ylim(-0.55, 1.85)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["would not\nrepeat", "would\nrepeat"], size=7.4, color=INK_2)
        ax.set_xticks(range(1, 8))
        ax.tick_params(axis="x", labelsize=8)

    axes[-1].set_xlabel("verbal valence   (1 = very negative  →  7 = very positive)",
                        size=8.5, labelpad=6)

    present = set(df["held_or_abandoned"].dropna().unique())
    handles = [Line2D([], [], marker=s["marker"], color=s["color"], linestyle="none",
                      markersize=7, markeredgecolor=SURFACE, label=s["label"])
               for k, s in OUTCOME_STYLE.items() if k in present]
    handles.append(plt.Rectangle((0, 0), 1, 1, facecolor="#2a78d6", alpha=0.20,
                                 label=f"k=5 noise band  (±{band:.2f})"))
    # Legend below the axes: with three stacked panels there is no room above the first
    # title, and a legend that overlaps a title is worse than one the eye reaches last.
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.55, 0.055), ncol=4,
               frameon=False, fontsize=8, handletextpad=0.45, columnspacing=1.8)
    fig.subplots_adjust(top=0.955, bottom=0.16, hspace=0.62)
    fig.savefig(out, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def write_macros(df: pd.DataFrame, out: Path) -> None:
    """Every number the prose quotes, as a LaTeX macro."""
    band = noise_band(df)
    counts = df["held_or_abandoned"].value_counts()
    by_cell = df.groupby("cell")

    def fmt(x, places=2):
        return f"{x:.{places}f}"

    lines = [
        "% Generated by analysis/pilot_figures.py — do not edit by hand.",
        "% Regenerate after any change to the episode data.",
        f"\\newcommand{{\\nEpisodes}}{{{len(df)}}}",
        f"\\newcommand{{\\nHeld}}{{{int(counts.get('held', 0))}}}",
        f"\\newcommand{{\\nPartial}}{{{int(counts.get('partial', 0))}}}",
        f"\\newcommand{{\\nAbandoned}}{{{int(counts.get('abandoned', 0))}}}",
        f"\\newcommand{{\\nNarrowed}}{{{int(df['narrowed'].fillna(False).sum())}}}",
        f"\\newcommand{{\\nUnreadable}}{{{int(df['battery_unreadable'].sum())}}}",
        f"\\newcommand{{\\nUnparsed}}{{{int(df['n_unparsed_choices'].sum())}}}",
        f"\\newcommand{{\\nUnconfirmed}}{{{int((~df['position_confirmed'].astype(bool)).sum())}}}",
        f"\\newcommand{{\\noiseBand}}{{{fmt(band['mean'])}}}",
        f"\\newcommand{{\\nBatteryAdmin}}{{{len(df) * 3 * 5}}}",
    ]
    for cell in CELL_ORDER:
        sub = by_cell.get_group(cell) if cell in by_cell.groups else df.iloc[0:0]
        key = cell.replace("_", "")
        lines += [
            f"\\newcommand{{\\val{key}}}{{{fmt(sub['valence'].mean(), 2)}}}",
            f"\\newcommand{{\\again{key}}}{{{fmt(sub['run_again'].mean(), 2)}}}",
            f"\\newcommand{{\\sd{key}}}{{{fmt(sub['valence_sd'].mean(), 2)}}}",
            f"\\newcommand{{\\exit{key}}}{{{fmt(sub['exited'].mean(), 2)}}}",
            f"\\newcommand{{\\n{key}}}{{{len(sub)}}}",
        ]
    out.write_text("\n".join(lines) + "\n")


# LaTeX-safe cell labels: the em dash used in the figures is not in the EC font set,
# so the table uses the `---` ligature instead.
TEX_CELL_LABEL = {
    "neutral_persistence": "neutral persistence (control)",
    "reasons_for": "pressure --- reasons-for",
    "weakness_probe": "pressure --- weakness-probe",
}


def outcome_table(df: pd.DataFrame, out: Path) -> None:
    """Table 1 as a complete tabular, built from the data.

    The whole environment is emitted rather than a row fragment: `\\input` inside a
    tabular puts `\\midrule` at a place TeX reads as mid-row, which fails to compile.
    """
    rows = []
    for cell in CELL_ORDER:
        sub = df[df["cell"] == cell]
        counts = sub["held_or_abandoned"].value_counts()
        rows.append(
            f"    {TEX_CELL_LABEL[cell]} & {int(counts.get('held', 0))} & "
            f"{int(counts.get('partial', 0))} & {int(counts.get('abandoned', 0))} & "
            f"{sub['valence'].mean():.2f} & {sub['run_again'].mean():.2f} & "
            f"{sub['exited'].mean():.2f} \\\\"
        )
    total = df["held_or_abandoned"].value_counts()

    body = "\n".join([
        "% Generated by analysis/pilot_figures.py --- do not edit by hand.",
        "\\begin{tabular}{lcccccc}",
        "    \\toprule",
        "    & \\multicolumn{3}{c}{outcome} & \\multicolumn{3}{c}{channels} \\\\",
        "    \\cmidrule(lr){2-4}\\cmidrule(lr){5-7}",
        "    cell & held & partial & abandoned & valence & run-again & exit \\\\",
        "    \\midrule",
        *rows,
        "    \\midrule",
        f"    all cells & {int(total.get('held', 0))} & {int(total.get('partial', 0))} & "
        f"{int(total.get('abandoned', 0))} & {df['valence'].mean():.2f} & "
        f"{df['run_again'].mean():.2f} & {df['exited'].mean():.2f} \\\\",
        "    \\bottomrule",
        "\\end{tabular}",
    ])
    out.write_text(body + "\n")


if __name__ == "__main__":
    frame = load(REPO / "data/raw/episodes_deepseek.jsonl")
    figs = REPO / "paper/figures"
    figs.mkdir(parents=True, exist_ok=True)
    figure_structure(figs / "pilot_structure.png")
    figure_outcomes(frame, figs / "pilot_outcomes.png")
    figure_channels(frame, figs / "pilot_channels.png")
    write_macros(frame, REPO / "paper/pilot_stats.tex")
    outcome_table(frame, REPO / "paper/pilot_table1.tex")
    for f in sorted(figs.glob("pilot_*.png")):
        print(f"  wrote {f.relative_to(REPO)}")
    print("  wrote paper/pilot_stats.tex, paper/pilot_table1.tex")
