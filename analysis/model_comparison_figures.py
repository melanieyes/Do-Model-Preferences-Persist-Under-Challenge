#!/usr/bin/env python3
"""Cross-model order-gap figures, all on ONE measure.

Replaces the single-model gap_vs_mean.png, order_gap.png and three_model.png. The
paper now has four measured targets and 230 deepseek pairs, and those figures showed
one model and 130 pairs.

THE MEASURE. Everything here is the DISCRETE order gap, computed from the k=5
samples: the share of resamples choosing option a in each presentation order, the
gap being how far the two orders disagree. Discrete throughout is not a compromise,
it is the only honest cross-model choice -- DeepSeek and gpt-5.4-nano expose
log-probabilities and Gemini does not, so a mixed plot would put a continuous P(a)
beside one quantised to 20% steps and the shape difference would be an artefact of
the API rather than of the model. Appendix D already makes this argument: where both
are available they agree to 0.001.

WHAT IS AND IS NOT COMPARED.

  * The on/off contrast is WITHIN PAIR and is therefore drawn only over pairs that
    have both cells -- the original 130. No reasoning-off run exists for the
    extension pool, so showing 230 on against 130 off would compare two different
    pools while looking like a paired contrast. That is the same error the
    counterbalancing argument exists to expose.
  * gemini-3.5-flash is excluded. It declines the task in ~60-96% of trials
    depending on the cell, so a gap over the pairs it will answer is conditioned on
    its willingness to answer -- the §5.4 problem. The paper reports no gap for it
    and neither does this script.

Emits:
    paper/figures/gap_vs_mean_models.png   the inverted V, three models
    paper/figures/order_gap.png            (a) on/off at 130  (b) reasoning-on at 230
    paper/figures/four_model.png           per-pair gap across four measured cells

    python analysis/model_comparison_figures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "analysis"))

import matplotlib.pyplot as plt  # noqa: E402
from figure_style import AXIS, DPI, GRID, INK, INK_2, MUTED, SURFACE  # noqa: E402

PAIRS = REPO / "data" / "pairs"
FIGS = REPO / "paper" / "figures"

C_OFF, C_ON, C_EXT = "#d1662b", "#2a78d6", "#7a3fa8"
NAIVE_BAND = (0.30, 0.70)
GAP_TRAP = 0.50


def discrete(rec: dict) -> dict | None:
    """Order-averaged P(option a) and the order gap, from the k=5 samples.

    Averages the two ORDER means rather than the raw samples: k=5 gives a 3/2
    schedule, so a raw mean would inherit that imbalance as a spurious preference.
    """
    by: dict[bool, list[float]] = {False: [], True: []}
    for s in rec.get("samples", []):
        if s.get("chose") in ("a", "b"):
            by[bool(s.get("flip"))].append(1.0 if s["chose"] == "a" else 0.0)
    if not by[False] or not by[True]:
        return None          # cannot form an order contrast for this pair
    m0, m1 = float(np.mean(by[False])), float(np.mean(by[True]))
    return {"mean_p_a": (m0 + m1) / 2, "gap": abs(m0 - m1),
            "n": len(by[False]) + len(by[True])}


def load_continuous(name: str) -> list[dict]:
    """Logprob-derived P(option a) and gap, where the provider exposes them.

    The inverted V is only visible on a CONTINUOUS P(a). At k=5 the discrete
    estimate takes six values, so 130 pairs collapse onto a dozen lattice points and
    the shape -- which is the whole argument -- disappears. Gemini exposes no
    log-probabilities and so cannot appear in that figure at all; it appears in the
    gap comparison, where the discrete measure is sufficient.
    """
    out = []
    for line in (PAIRS / name).read_text().splitlines()[1:]:
        r = json.loads(line)
        if r.get("mean_p_option_a") is not None and r.get("position_bias") is not None:
            out.append({"mean_p_a": r["mean_p_option_a"], "gap": r["position_bias"],
                        "pair_id": r["pair_id"], "domain": r.get("domain")})
    return out


def load(name: str) -> list[dict]:
    lines = (PAIRS / name).read_text().splitlines()
    out = []
    for line in lines[1:]:
        r = json.loads(line)
        if "pair_id" not in r:
            continue
        d = discrete(r)
        if d:
            out.append({**d, "pair_id": r["pair_id"], "domain": r.get("domain")})
    return out


# label -> (file, colour, cell)
CELLS = {
    "deepseek-v4-pro, reasoning off": ("balance_pilot_noreason.jsonl", C_OFF),
    "deepseek-v4-pro, reasoning on":  ("balance_pilot.jsonl", C_ON),
    "gemini-2.5-flash, reasoning off": ("gemini_gemini-25-flash_off.jsonl", C_OFF),
    "gemini-2.5-flash, reasoning on":  ("gemini_gemini-25-flash_on.jsonl", C_ON),
    "gpt-5.4-nano (non-reasoning)":    ("balance_pilot_nano.jsonl", C_ON),
}


def _frame(ax):
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID, linewidth=0.7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def fig_gap_vs_mean_models() -> Path:
    """The inverted V, on the continuous measure, for every target that exposes logprobs."""
    panels = [("deepseek-v4-pro",
               [("balance_pilot_noreason.jsonl", C_OFF, "reasoning suppressed"),
                ("balance_pilot.jsonl", C_ON, "reasoning enabled")]),
              ("gpt-5.4-nano",
               [("balance_pilot_nano.jsonl", C_ON, "no reasoning stage")])]
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.1), sharey=True)
    for ax, (title, cells) in zip(axes, panels):
        ax.add_patch(plt.Rectangle((NAIVE_BAND[0], GAP_TRAP),
                                   NAIVE_BAND[1] - NAIVE_BAND[0], 1 - GAP_TRAP,
                                   facecolor=GRID, alpha=0.75, lw=0, zorder=1))
        ax.axvspan(*NAIVE_BAND, color=GRID, alpha=0.30, lw=0, zorder=0)
        notes = []
        for fname, colour, lbl in cells:
            rows = load_continuous(fname)
            ax.scatter([r["mean_p_a"] for r in rows], [r["gap"] for r in rows],
                       s=30, color=colour, alpha=0.58, edgecolor=SURFACE,
                       linewidth=1.0, zorder=3, label=lbl)
            naive = [r for r in rows if NAIVE_BAND[0] <= r["mean_p_a"] <= NAIVE_BAND[1]]
            trap = [r for r in naive if r["gap"] > GAP_TRAP]
            notes.append(f"{lbl}: naive filter takes {len(naive)}, "
                         f"{len(trap)} of them slot-driven")
        _frame(ax)
        ax.set_xlim(-0.03, 1.03); ax.set_ylim(-0.03, 1.03)
        ax.set_xlabel("order-averaged $P$(option a)", fontsize=9)
        ax.set_title(title, fontsize=10, loc="left", color=INK)
        ax.legend(fontsize=8, frameon=False, loc="upper left")
        ax.text(0.985, 0.02, "\n".join(notes), transform=ax.transAxes,
                ha="right", va="bottom", fontsize=7.3, color=INK)
    axes[0].set_ylabel("order gap", fontsize=9)
    fig.suptitle("Perfect balance and total position dependence are the same number — "
                 "the apex sits at $P=0.5$.\ngemini-2.5-flash cannot appear here: "
                 "the API exposes no log-probabilities, and at $k$=5 the discrete "
                 "estimate is too coarse to show the shape.",
                 fontsize=8.6, color=INK_2, y=1.06, x=0.01, ha="left")
    fig.tight_layout()
    out = FIGS / "gap_vs_mean_models.png"
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)
    return out


def fig_order_gap(data: dict[str, list[dict]], ext: list[dict]) -> Path:
    """(a) the within-pair on/off contrast at 130. (b) reasoning-on over all 230."""
    bins = np.linspace(0, 1, 21)
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 4.8), sharex=True,
                             gridspec_kw={"hspace": 0.40})

    ax = axes[0]
    for key, colour, lbl in (("deepseek-v4-pro, reasoning off", C_OFF, "reasoning suppressed"),
                             ("deepseek-v4-pro, reasoning on", C_ON, "reasoning enabled")):
        v = np.array([r["gap"] for r in data[key]])
        ax.hist(v, bins=bins, color=colour, alpha=0.62, label=f"{lbl}  (mean {v.mean():.3f})")
        ax.axvline(v.mean(), color=colour, lw=1.6, zorder=4)
    _frame(ax); ax.legend(fontsize=7.6, frameon=False)
    ax.set_ylabel("pairs", fontsize=9)
    ax.set_title(f"(a) The same {len(data['deepseek-v4-pro, reasoning on'])} pairs in both "
                 "cells — the contrast is within pair", fontsize=9, loc="left", color=INK)

    ax = axes[1]
    orig = np.array([r["gap"] for r in data["deepseek-v4-pro, reasoning on"]])
    e = np.array([r["gap"] for r in ext])
    ax.hist([orig, e], bins=bins, stacked=True, color=[C_ON, C_EXT], alpha=0.75,
            label=[f"original pool ({len(orig)})", f"extension pool ({len(e)})"])
    ax.axvline(np.concatenate([orig, e]).mean(), color=INK, lw=1.6, zorder=4)
    sports = [r["gap"] for r in ext if r.get("domain") == "sports"]
    if sports:
        ax.annotate(f"sports: {len(sports)} pairs, mean {np.mean(sports):.3f}\n"
                    "reasoning ON and still slot-driven",
                    xy=(float(np.mean(sports)), 1.5), xytext=(0.40, 0.46),
                    textcoords="axes fraction", fontsize=7.4, color=INK,
                    arrowprops=dict(arrowstyle="->", color=MUTED, lw=1.0))
    _frame(ax); ax.legend(fontsize=7.6, frameon=False)
    ax.set_xlabel("order gap (discrete, $k$=5)", fontsize=9)
    ax.set_ylabel("pairs", fontsize=9)
    ax.set_title(f"(b) Reasoning enabled, all {len(orig) + len(e)} pairs — the reasoning "
                 "control does not reach every item", fontsize=9, loc="left", color=INK)
    fig.tight_layout()
    out = FIGS / "order_gap.png"
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)
    return out


def fig_four_model(data: dict[str, list[dict]]) -> Path:
    """Per-pair gap for every measured cell. One point per pair, median ruled."""
    order = list(CELLS)
    fig, ax = plt.subplots(figsize=(8.4, 4.0))
    rng = np.random.default_rng(20260815)
    for i, key in enumerate(order):
        v = np.array([r["gap"] for r in data[key]])
        ax.scatter(v, i + rng.uniform(-0.16, 0.16, len(v)), s=17,
                   color=CELLS[key][1], alpha=0.5, edgecolor="none", zorder=3)
        ax.plot([np.median(v)] * 2, [i - 0.3, i + 0.3], color=INK, lw=2.0, zorder=4)
        ax.text(1.02, i, f"n={len(v)}   mean {v.mean():.3f}   median {np.median(v):.3f}",
                va="center", fontsize=7.6, color=INK_2)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order, fontsize=8.2)
    ax.set_xlim(-0.03, 1.03); ax.set_xlabel("order gap (discrete, $k$=5)", fontsize=9)
    ax.set_axisbelow(True); ax.xaxis.grid(True, color=GRID, linewidth=0.7)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.set_title("The black rule is the median. gemini-3.5-flash is absent because it "
                 "declines the task,\nso any gap for it would be conditioned on its "
                 "willingness to answer.", fontsize=8.6, loc="left", color=INK_2)
    fig.tight_layout()
    out = FIGS / "four_model.png"
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)
    return out


def main() -> None:
    FIGS.mkdir(parents=True, exist_ok=True)
    data = {k: load(f) for k, (f, _) in CELLS.items()}
    ext = load("balance_pilot_ext.jsonl")
    for k, v in data.items():
        g = np.array([r["gap"] for r in v])
        print(f"  {k:<34} n={len(v):>4}  mean {g.mean():.3f}  median {np.median(g):.3f}")
    ge = np.array([r["gap"] for r in ext])
    print(f"  {'deepseek extension pool (on)':<34} n={len(ext):>4}  mean {ge.mean():.3f}  "
          f"median {np.median(ge):.3f}")
    for p in (fig_gap_vs_mean_models(), fig_order_gap(data, ext), fig_four_model(data)):
        print(f"  wrote {p.relative_to(REPO)}")


if __name__ == "__main__":
    main()
