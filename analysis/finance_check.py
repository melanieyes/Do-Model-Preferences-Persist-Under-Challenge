#!/usr/bin/env python3
"""Cross-model manipulation check — finances_control only (DEVIATIONS #9, EXPLORATORY).

The money ladder is a POSITIVE CONTROL, not a domain: a forced choice between
two rungs is arithmetic, so ceiling retention is the expected, correct result
and nothing here is ever pooled into a PQ estimate. This script asks one
question per target: does the arithmetic ladder hold at ceiling on this model,
under the same four arms and the same five instrument controls?

Wavering here is not a preference result. On the primary target it would mean
the elicitation is broken (CLAUDE.md: stop and tell the human). On a further
target it is a property of that target's elicitation stability, reported as
such and never as retention-of-a-preference.

    python analysis/finance_check.py             # console comparison
    python analysis/finance_check.py --figure    # + paper/figures/finance_models.png
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis.persistence_analysis import (  # noqa: E402
    ARMS, POSITIVE_CONTROL, cluster_bootstrap, group,
)

DATA = ROOT / "data" / "persistence"
CHALLENGE_ARMS = ("self_critique", "counter_consideration")

# (label, file, filter-to-finance?) — every target now has one five-domain file;
# the finance episodes are filtered out of each.
SOURCES = [
    ("deepseek-v4-pro", DATA / "persistence_deepseek_ext.jsonl", True),
    ("gpt-5.4-nano", DATA / "persistence_nano_ext.jsonl", True),
    ("gemini-2.5-flash", DATA / "persistence_gemini25_ext.jsonl", True),
]


def load(path: Path, finance_only: bool) -> list[dict]:
    rows = [json.loads(x) for x in path.read_text().splitlines() if '"episode_id"' in x]
    return [r for r in rows if r["domain"] == POSITIVE_CONTROL] if finance_only else rows


def pct(x):
    return "--" if x is None else f"{x * 100:5.1f}%"


def build_figure() -> None:
    """Grouped bars: arms on x, one colour per model — the mentor's layout, on the
    manipulation check. Value labels on every bar (selective: one number per bar,
    the retention point) plus the bootstrap 95% CI whisker the house rule requires.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sys.path.insert(0, str(ROOT / "analysis"))
    from figure_style import AXIS, DPI, GRID, INK, INK_2, MUTED, SURFACE

    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "axes.edgecolor": AXIS, "text.color": INK, "axes.labelcolor": INK_2,
        "xtick.color": MUTED, "ytick.color": MUTED,
        "savefig.dpi": DPI, "figure.dpi": DPI,
    })
    COLOURS = {"deepseek-v4-pro": "#2a78d6", "gpt-5.4-nano": "#d1662b",
               "gemini-2.5-flash": "#4a9c6d"}
    ARM_LABEL = {"control": "control", "reason_elicitation": "reason\nelicitation",
                 "self_critique": "self\ncritique",
                 "counter_consideration": "counter\nconsideration"}

    present = [(n, p, f) for n, p, f in SOURCES if p.exists()]
    fig, ax = plt.subplots(figsize=(11.2, 4.4))
    width = 0.26
    for mi, (name, path, fin_only) in enumerate(present):
        scored = [r for r in load(path, fin_only) if r.get("retained") is not None]
        xs, pts, los, his = [], [], [], []
        for ai, arm in enumerate(ARMS):
            p, lo, hi, _, _ = cluster_bootstrap(group(
                scored, lambda r, a=arm: r["arm"] == a, lambda r: r["retained"]))
            if p is None:
                continue
            xs.append(ai + (mi - (len(present) - 1) / 2) * width)
            pts.append(p * 100); los.append(lo * 100); his.append(hi * 100)
        ax.bar(xs, pts, width=width * 0.9, color=COLOURS[name], edgecolor=AXIS,
               linewidth=0.6, zorder=2, label=name)
        for x, p_, lo, hi in zip(xs, pts, los, his):
            ax.plot([x, x], [lo, hi], color=INK, lw=1.2, zorder=3)
            ax.text(x, min(lo, p_) - 3.5, f"{p_:.0f}", ha="center", va="top",
                    fontsize=7.6, color=INK, fontweight="bold", zorder=4)

    ax.set_xticks(range(len(ARMS)))
    ax.set_xticklabels([ARM_LABEL[a] for a in ARMS], fontsize=8.5)
    ax.set_ylim(0, 118)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("retention on the money ladder (%)", fontsize=9)
    ax.set_title("Manipulation check across models: does a challenge move arithmetic?",
                 fontsize=9.5, loc="left", color=INK)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID, linewidth=0.7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(fontsize=7.6, frameon=False, loc="upper right", ncol=3,
              handlelength=1.1, columnspacing=1.0)
    fig.tight_layout()
    out = ROOT / "paper" / "figures" / "finance_models.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"\nwrote {out.relative_to(ROOT)}")


def main() -> None:
    print("=" * 96)
    print("MANIPULATION CHECK, CROSS-MODEL — finances_control (EXPLORATORY, DEVIATIONS #9)")
    print("  Never pooled into any PQ estimate. Bootstrap 95% CIs over pairs, 10,000 resamples.")
    print("=" * 96)
    for name, path, fin_only in SOURCES:
        if not path.exists():
            print(f"\n{name}: {path.name} not collected yet — skipped")
            continue
        rows = load(path, fin_only)
        scored = [r for r in rows if r.get("retained") is not None]
        n_ref = sum(1 for r in rows if "refusal" in (r.get("kind_pre"), r.get("kind_post")))
        n_unp = sum(1 for r in rows if "unparsed" in (r.get("kind_pre"), r.get("kind_post")))
        print(f"\n{name}  —  {len(rows)} episodes, {len(scored)} scored, "
              f"{n_ref} refusal / {n_unp} unparsed (data, not dropped)")
        p, lo, hi, npair, nobs = cluster_bootstrap(
            group(scored, lambda r: True, lambda r: r["retained"]))
        print(f"  retention, all arms     {pct(p)}  [{pct(lo).strip()}, {pct(hi).strip()}]"
              f"  ({nobs} eps, {npair} pairs)")
        for arm in ARMS:
            pa, la, ha, _, na = cluster_bootstrap(group(
                scored, lambda r, a=arm: r["arm"] == a, lambda r: r["retained"]))
            print(f"    {arm:<24}{pct(pa)}  [{pct(la).strip()}, {pct(ha).strip()}]  n={na}")
        flips = [r for r in scored if r["retained"] is False]
        ch = sum(1 for r in scored if r["arm"] in CHALLENGE_ARMS)
        ch_flips = sum(1 for r in flips if r["arm"] in CHALLENGE_ARMS)
        print(f"  flips: {len(flips)} total; {ch_flips} in {ch} challenge episodes")
        if flips:
            print("  flipped episodes (the ladder MOVED — elicitation instability on this target):")
            for r in flips[:8]:
                print(f"    {r['arm']:<22} {r['pair_id'][-3:]}  "
                      f"{r['choice_pre']}->{r['choice_post']}  "
                      f"conf {r.get('conf_pre')}->{r.get('conf_post')}")
        verdict = ("PASS — at or near ceiling, as designed" if p is not None and p >= 0.95
                   else "** BELOW CEILING — elicitation unstable on this target; "
                        "report as an instrument property, never as preference movement")
        print(f"  verdict: {verdict}")
    print()
    print("=" * 96)
    print("EXPLORATORY. finances_control is a manipulation check; wavering on a further")
    print("target is that target's elicitation instability, not a preference finding.")
    print("=" * 96)


if __name__ == "__main__":
    main()
    if "--figure" in sys.argv:
        build_figure()
