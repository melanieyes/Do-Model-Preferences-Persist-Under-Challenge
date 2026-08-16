"""Figure and derived numbers for the preference-pair instrument.

Two findings, one figure:

  (a) the forced choice follows the SLOT unless reasoning is on — the elicitation
      had to be fixed before any pair could be judged;
  (b) once it follows content, almost every pair is at ceiling — the model does not
      waver, so there is little for a challenge to move.

Emits:
    paper/figures/pair_balance.png   two-panel figure
    paper/pair_stats.tex             every quoted number, as macros
    paper/pair_table1.tex            per-domain kept/dropped table

    python analysis/pair_balance_figures.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis"))

from pilot_figures import AXIS, DPI, GRID, INK, INK_2, MUTED, SURFACE  # noqa: E402

PAIRS = REPO / "data" / "pairs"
FIGS = REPO / "paper" / "figures"

# Sequential ramp: how much the model wavered. One hue, light -> dark, so the
# encoding is magnitude and not identity. The house blue is the dark end.
WAVER = ["#c8dcf3", "#79a9e3", "#2a78d6"]
WAVER_LABEL = ["never wavered\n(5/0 or 0/5)", "wavered once\n(4/1 or 1/4)",
               "wavered twice\n(3/2 or 2/3)"]

COND_LABEL = {
    "letter_noreason": "letter only,\nreasoning off",
    "letter_reasoning": "letter only,\nreasoning on",
    "cot_reasoning": "upstream CoT,\nreasoning on",
}

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": AXIS,
    "text.color": INK, "axes.labelcolor": INK_2,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "savefig.dpi": DPI, "figure.dpi": DPI,
})


def load():
    diag = json.loads((PAIRS / "position_bias_diagnostic.json").read_text())
    lines = [json.loads(x) for x in (PAIRS / "balance_pilot.jsonl").read_text().splitlines()]
    prov = json.loads((PAIRS / "pilot_pool.jsonl").read_text().splitlines()[0])
    return diag, {**lines[0], **{k: prov[k] for k in ("source_commit", "source_file_commit", "source_file")}}, lines[1:]


def panel_a(ax, diag) -> None:
    """Order gap per pair, by elicitation condition."""
    conds = list(diag["conditions"])
    ax.axhspan(0, 0.2, color=GRID, alpha=0.45, lw=0, zorder=0)
    # One band label at the far left, clear of both the points and the mean labels.
    ax.text(-0.47, 0.10, "choice follows\ncontent", ha="left", va="center",
            size=7.0, color=INK_2, style="italic", zorder=4)

    for x, cond in enumerate(conds):
        gaps = [r["gap"] for r in diag["rows"] if r["condition"] == cond and "gap" in r]
        # deterministic spread so overlapping points stay countable
        offs = np.linspace(-0.13, 0.13, len(gaps)) if len(gaps) > 1 else [0.0]
        ax.scatter([x + o for o in offs], gaps, s=42, color=WAVER[2], alpha=0.75,
                   edgecolor=SURFACE, linewidth=1.6, zorder=3)
        mean = diag["mean_gap"][cond]
        ax.plot([x - 0.27, x + 0.27], [mean, mean], color=INK, lw=2.2, zorder=4,
                solid_capstyle="round")
        ax.text(x, mean + 0.055, f"mean {mean:.2f}", ha="center", size=7.6, color=INK)

    ax.set_xticks(range(len(conds)))
    ax.set_xticklabels([COND_LABEL.get(c, c) for c in conds], size=7.8)
    ax.set_xlim(-0.58, len(conds) - 0.55)
    ax.set_ylim(-0.05, 1.12)
    ax.set_yticks([0, 0.5, 1.0])
    ax.set_ylabel("order gap\n|P(a | a first) − P(a | a second)|", size=8.2)
    ax.set_title("a.  The elicitation had to be fixed first", size=9.4, color=INK,
                 loc="left", pad=9)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)


def panel_b(ax, recs) -> None:
    """How often the model wavered across k=5, by domain."""
    domains = sorted({r["domain"] for r in recs})
    counts = {
        d: Counter(min(r["n_a"], r["n_b"]) for r in recs if r["domain"] == d)
        for d in domains
    }
    ys = np.arange(len(domains))
    left = np.zeros(len(domains))
    for level in (0, 1, 2):
        vals = np.array([counts[d].get(level, 0) for d in domains], dtype=float)
        ax.barh(ys, vals, left=left, height=0.62, color=WAVER[level],
                edgecolor=SURFACE, linewidth=2.0, zorder=3,
                label=WAVER_LABEL[level])
        for y, v, l in zip(ys, vals, left):
            if v:
                ax.text(l + v / 2, y, f"{int(v)}", ha="center", va="center",
                        size=8.0, color=INK if level < 2 else SURFACE, zorder=4)
        left += vals

    ax.set_yticks(ys)
    ax.set_yticklabels([d.replace("_", "/") for d in domains], size=8.4)
    ax.invert_yaxis()
    ax.set_xlabel("pairs piloted", size=8.2)
    ax.set_title("b.  …and then almost nothing wavers", size=9.4, color=INK,
                 loc="left", pad=9)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.20), ncol=3,
              frameon=False, fontsize=7.6, handlelength=1.1, handleheight=1.1,
              columnspacing=1.4)


def main() -> None:
    diag, meta, recs = load()
    FIGS.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.5),
                             gridspec_kw={"width_ratios": [1.0, 1.15], "wspace": 0.32})
    panel_a(axes[0], diag)
    panel_b(axes[1], recs)
    fig.subplots_adjust(bottom=0.30, top=0.86, left=0.115, right=0.985)
    out = FIGS / "pair_balance.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)

    # --- macros -----------------------------------------------------------
    kept = [r for r in recs if r.get("decision") == "keep"]
    waver = Counter(min(r["n_a"], r["n_b"]) for r in recs)
    bias_on = diag["mean_gap"].get("letter_reasoning")
    bias_off = diag["mean_gap"].get("letter_noreason")
    macros = {
        "pairPiloted": len(recs),
        "pairKept": len(kept),
        "pairCeiling": waver.get(0, 0),
        "pairWaverOnce": waver.get(1, 0),
        "pairWaverTwice": waver.get(2, 0),
        "pairGapOff": f"{bias_off:.2f}",
        "pairGapOn": f"{bias_on:.2f}",
        "pairK": meta["k"],
        "pairModel": meta["model"].replace("_", "\\_"),
        "pairExcluded": sum(1 for _ in (PAIRS / "excluded_outcomes.jsonl")
                            .read_text().splitlines()) - 1,
        "pairSourceCommit": meta["source_file_commit"][:12],
        # wavered twice but answered by slot every time — balanced-looking noise
        "pairPositionDropped": sum(
            1 for r in recs
            if r.get("decision") == "drop" and min(r["n_a"], r["n_b"]) >= 2),
        "pairDomainsViable": sum(
            1 for d in {r["domain"] for r in recs}
            if sum(1 for r in recs if r["domain"] == d and r.get("decision") == "keep") >= 6),
    }
    (REPO / "paper" / "pair_stats.tex").write_text(
        "% Generated by analysis/pair_balance_figures.py — do not edit by hand.\n"
        + "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in macros.items())
    )

    # --- table ------------------------------------------------------------
    rows = []
    for d in sorted({r["domain"] for r in recs}):
        sub = [r for r in recs if r["domain"] == d]
        w = Counter(min(r["n_a"], r["n_b"]) for r in sub)
        k = sum(1 for r in sub if r.get("decision") == "keep")
        rows.append(f"{d.replace('_', '/')} & {len(sub)} & {w.get(0,0)} & "
                    f"{w.get(1,0)} & {w.get(2,0)} & {k} \\\\")
    (REPO / "paper" / "pair_table1.tex").write_text(
        "% Generated by analysis/pair_balance_figures.py — do not edit by hand.\n"
        "\\begin{tabular}{lrrrrr}\n\\toprule\n"
        "domain & piloted & never & once & twice & kept \\\\\n\\midrule\n"
        + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n"
    )

    print(f"wrote {out.relative_to(REPO)}")
    print(f"  piloted {len(recs)}, kept {len(kept)}, "
          f"ceiling {waver.get(0,0)}, wavered-once {waver.get(1,0)}, "
          f"wavered-twice {waver.get(2,0)}")


if __name__ == "__main__":
    main()
