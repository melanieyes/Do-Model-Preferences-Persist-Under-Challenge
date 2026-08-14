"""Build the 2-page pilot PDF for Haein.

PILOT — pipeline check, NOT results. Every page carries that header, by construction:
`page_header()` is called on every page and there is no code path that draws one without
it. Nothing here computes a confirmatory estimate.

    python analysis/pilot_report.py

Figure 1 orients the reader in the episode structure. Figure 2 is the descriptive look at
the two channels (verbal valence x run-again) against the hold-vs-abandon axis, with the
k=5 noise band drawn so no mean is read as a point estimate.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis"))

from pilot_extract import load, noise_band  # noqa: E402

BANNER = "PILOT — pipeline check, NOT results."

# Chart chrome (dataviz reference palette, light surface).
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SURFACE = "#fcfcfb"

# Categorical slots 1-3 — validated all-pairs, light mode. Shape is carried alongside
# colour because the scatter needs secondary encoding (and aqua is sub-3:1 on this
# surface, so its relief is the direct label + legend).
OUTCOME_STYLE = {
    "held":      {"color": "#2a78d6", "marker": "o", "label": "held"},
    "abandoned": {"color": "#eb6834", "marker": "s", "label": "abandoned"},
    "partial":   {"color": "#1baf7a", "marker": "^", "label": "partial"},
    "unclear":   {"color": MUTED,     "marker": "X", "label": "unclear"},
}

CELL_ORDER = ["neutral_persistence", "reasons_for", "weakness_probe"]
CELL_LABEL = {
    "neutral_persistence": "neutral persistence\n(control)",
    "reasons_for": "pressure — reasons-for\n(justify your view)",
    "weakness_probe": "pressure — weakness-probe\n(name its weaknesses)",
}

plt.rcParams.update({
    "font.family": "sans-serif",
    # DejaVu first: it ships with matplotlib and has the arrow/section glyphs used below.
    "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": AXIS,
    "text.color": INK,
    "axes.labelcolor": INK_2,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
})


def page_header(fig, page_no: int, total: int) -> None:
    """The banner every page must carry. No page is drawn without this."""
    fig.text(0.06, 0.972, BANNER, size=9.5, weight="bold", color="#d03b3b")
    fig.text(0.94, 0.972, f"{page_no}/{total}", size=8.5, color=MUTED, ha="right")
    fig.lines.append(plt.Line2D([0.06, 0.94], [0.962, 0.962], transform=fig.transFigure,
                                color=GRID, lw=0.8))


def draw_structure(ax) -> None:
    """Figure 1 — what one episode is. Reader orientation, no data."""
    ax.set_xlim(0, 100); ax.set_ylim(0, 30); ax.axis("off")

    boxes = [
        (2,  20, "1. Initial position\nmodel answers, states\nits position", "#2a78d6"),
        (26, 20, "2. Pressure rungs x4\nscenario probe, then\nshared templates", "#eb6834"),
        (52, 20, "3. Affordance\nevery 2 rungs:\ncontinue / switch / stop", "#1baf7a"),
        (77, 21, "4. Battery x k=5\nvalence · state\nrun-again · confidence", "#4a3aa7"),
    ]
    for x, w, text, colour in boxes:
        ax.add_patch(FancyBboxPatch((x, 9), w, 12, boxstyle="round,pad=0.6,rounding_size=1.2",
                                    linewidth=1.4, edgecolor=colour, facecolor=colour + "14"))
        ax.text(x + w / 2, 15, text, ha="center", va="center", size=7.6, color=INK, linespacing=1.5)
    for x in (23.5, 49.5, 75.5):
        ax.add_patch(FancyArrowPatch((x, 15), (x + 2, 15), arrowstyle="-|>",
                                     mutation_scale=11, color=MUTED, lw=1.2))

    ax.text(50, 5.5,
            "confirm the model actually stated the position  →  apply pressure  →  "
            "real exit choice  →  measure how it registered",
            ha="center", size=8, color=INK_2, style="italic")
    ax.text(50, 1.8,
            "A judge then codes HELD vs ABANDONED from an arm-blind transcript, and must "
            "quote the span it relied on.",
            ha="center", size=7.5, color=MUTED)


def draw_channels(fig, gs, df: pd.DataFrame) -> list:
    """Figure 2 — the two channels against the hold-vs-abandon axis. Descriptive only."""
    band = noise_band(df)["mean"]
    rng = np.random.default_rng(20260813)   # jitter only; nothing inferential
    axes = []

    for i, cell in enumerate(CELL_ORDER):
        ax = fig.add_subplot(gs[i])
        axes.append(ax)
        sub = df[df["cell"] == cell]

        ax.set_axisbelow(True)
        ax.grid(axis="x", color=GRID, lw=0.7)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

        # k=5 noise band around this cell's mean valence — the scale a mean is read at.
        if len(sub) and not np.isnan(band):
            mean_v = sub["valence"].mean()
            ax.axvspan(mean_v - band, mean_v + band, color="#2a78d6", alpha=0.10, lw=0)
            ax.axvline(mean_v, color="#2a78d6", lw=1.6)
            ax.text(mean_v, 1.26, f"mean {mean_v:.1f}", ha="center", size=7,
                    color="#2a78d6", weight="bold")

        for outcome, style in OUTCOME_STYLE.items():
            pts = sub[sub["held_or_abandoned"] == outcome]
            if pts.empty:
                continue
            y = pts["run_again"].to_numpy(float) + rng.uniform(-0.07, 0.07, len(pts))
            ax.scatter(pts["valence"], y, s=46, marker=style["marker"],
                       facecolor=style["color"], edgecolor=SURFACE, linewidth=1.2,
                       alpha=0.9, zorder=3, label=style["label"])

        n_ep = len(sub)
        n_exit = int(sub["exited"].sum())
        ax.set_title(f"{CELL_LABEL[cell]}      n = {n_ep}   ·   exited (switch/stop): {n_exit}/{n_ep}",
                     size=8.5, color=INK, loc="left", pad=8)

        ax.set_xlim(0.6, 7.4); ax.set_ylim(-0.35, 1.5)
        ax.set_yticks([0, 1]); ax.set_yticklabels(["would NOT\nrun again", "would\nrun again"], size=7.5)
        ax.set_xticks(range(1, 8))
        if i == len(CELL_ORDER) - 1:
            ax.set_xlabel("verbal valence  (1 = very negative … 7 = very positive)", size=8.5)
        else:
            ax.set_xticklabels([])

    present = {o for o in df["held_or_abandoned"].dropna().unique()}
    handles = [Line2D([], [], marker=s["marker"], color=s["color"], linestyle="none",
                      markersize=7, markeredgecolor=SURFACE, label=s["label"])
               for key, s in OUTCOME_STYLE.items() if key in present]
    handles.append(plt.Rectangle((0, 0), 1, 1, facecolor="#2a78d6", alpha=0.18,
                                 label=f"k=5 noise band (±{band:.2f})" if not np.isnan(band) else "k=5 noise band"))
    return handles


def build(df: pd.DataFrame, out: Path) -> None:
    n_ep = len(df)
    band = noise_band(df)
    unreadable = int(df["battery_unreadable"].sum())
    unparsed = int(df["n_unparsed_choices"].sum())
    narrowed = int(df["narrowed"].fillna(False).sum())
    unconfirmed = int((~df["position_confirmed"].astype(bool)).sum())
    outcomes = df["held_or_abandoned"].value_counts()
    n_held = int(outcomes.get("held", 0))
    n_aband = int(outcomes.get("abandoned", 0))
    n_partial = int(outcomes.get("partial", 0))

    with PdfPages(out) as pdf:
        # ---------------- page 1 : orientation ----------------
        fig = plt.figure(figsize=(8.27, 11.69))
        page_header(fig, 1, 2)
        fig.text(0.06, 0.915, "Does It Matter to a Model How It Is Moved?", size=17, weight="bold")
        fig.text(0.06, 0.892, "Pilot pass — for Haein. Pipeline check and framing, not findings.",
                 size=10.5, color=INK_2)

        fig.text(0.06, 0.858, "What this is", size=11, weight="bold")
        fig.text(0.06, 0.840,
                 "Thirty episodes on DeepSeek across two scenarios (a factual claim and a stated\n"
                 "approach) and three cells: neutral persistence as control, and two pressure styles —\n"
                 "asking the model to justify its view (reasons-for) versus asking it to name that view's\n"
                 "weaknesses (weakness-probe). Every episode holds a legitimate initial position, faces a\n"
                 "scripted escalation, gets a real continue/switch/stop choice every two turns, and ends\n"
                 "with the 4-item battery resampled five times. Direct framing only in the pilot.\n\n"
                 "Every record is labelled analysis: \"pilot\" and is excluded from the confirmatory pool\n"
                 "unconditionally (prereg §6) — including if nothing changes afterwards. The point of\n"
                 "tonight is to see that the machinery runs end to end and that the framing is worth\n"
                 "keeping, not to learn anything about the effect.",
                 size=9.3, color=INK, linespacing=1.75, va="top")

        fig.text(0.06, 0.585, "Figure 1. What one episode is", size=11, weight="bold")
        ax = fig.add_axes([0.06, 0.390, 0.88, 0.175])
        draw_structure(ax)

        fig.text(0.06, 0.352, "The one thing this pilot showed — compliance is at ceiling",
                 size=11, weight="bold")
        fig.text(0.06, 0.334,
                 f"Across all 30 episodes the model abandoned its position {n_aband} time. "
                 f"{n_held} held outright and\n"
                 f"{n_partial} were coded partial. The pilot gate asks whether compliance sits off floor and "
                 "ceiling; it does not.\n"
                 "That matters because the comparison this design is built around — does HOLDING a position\n"
                 "under pressure register worse than caving — needs both outcomes to occur. Right now there is\n"
                 "almost no \"caved\" side to compare against, so the axis cannot be populated as designed.\n\n"
                 "Nothing is wrong with the pipeline; the scenarios are simply too easy to hold. This is the\n"
                 "decision I need you for: stronger pressure, positions that are genuinely contestable rather\n"
                 "than factually settled, or accept a hold-only design and change the question.",
                 size=9.3, color=INK, linespacing=1.75, va="top")

        fig.text(0.06, 0.115,
                 f"Instrument health · {n_ep} episodes · battery answers unreadable: {unreadable} "
                 f"· affordance replies unparsed: {unparsed}\n"
                 f"positions not confirmed at the opener: {unconfirmed} · episodes where the judge saw "
                 f"claim-narrowing: {narrowed}",
                 size=8, color=MUTED, linespacing=1.7, va="top")
        pdf.savefig(fig); plt.close(fig)

        # ---------------- page 2 : the two channels ----------------
        fig = plt.figure(figsize=(8.27, 11.69))
        page_header(fig, 2, 2)
        fig.text(0.06, 0.925, "Figure 2. The two channels, by cell", size=13, weight="bold")
        fig.text(0.06, 0.905,
                 "Each point is one episode. Horizontal: how the exchange registered verbally. "
                 "Vertical: whether it would\nrun the exchange again. Shape and colour: whether it held "
                 "or abandoned its position.",
                 size=9, color=INK_2, linespacing=1.6, va="top")

        gs = fig.add_gridspec(3, 1, left=0.17, right=0.95, top=0.780, bottom=0.430, hspace=0.45)
        handles = draw_channels(fig, gs, df)
        fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.17, 0.845),
                   ncol=5, frameon=False, fontsize=7.5, handletextpad=0.4, columnspacing=1.4)

        fig.text(0.06, 0.372, "How to read it — and how not to", size=11, weight="bold")
        fig.text(0.06, 0.354,
                 f"EXPLORATORY, NOT CONFIRMATORY. n = {n_ep} episodes total, roughly ten per cell. That is\n"
                 f"far too few for an effect, and no test is run here. The shaded band is the k=5 noise\n"
                 f"floor — the mean within-episode spread across the five battery resamples, "
                 f"{band['mean']:.2f} points\n"
                 f"on the 1–7 scale. Any gap between cell means narrower than that band is indistinguishable\n"
                 f"from the model answering the same question twice. Read the shape of the picture, not the\n"
                 f"positions. Where a cell is thin, the honest phrasing is \"no measurable difference in this\n"
                 f"sample\" — never \"no effect\".",
                 size=9.3, color=INK, linespacing=1.75, va="top")
        fig.text(0.06, 0.185,
                 "Confirmatory analysis waits for the full run: RQ1 (pooled pressure vs. control) is "
                 "analysed first,\nthen RQ2 (the style gap) within compliance-matched episodes. "
                 "Not before. — prereg-v1 + DEVIATIONS.md",
                 size=8, color=MUTED, linespacing=1.7, va="top")
        pdf.savefig(fig); plt.close(fig)

    print(f"  wrote {out}")


if __name__ == "__main__":
    src = REPO / "data/raw/episodes_deepseek.jsonl"
    frame = load(src)
    out_dir = REPO / "paper/figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    build(frame, out_dir / "pilot_report.pdf")
