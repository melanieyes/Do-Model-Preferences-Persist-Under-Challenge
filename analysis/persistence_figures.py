"""Figures for the preference-persistence result (PQ1-PQ3).

Since DEVIATIONS #8 the reported study is the five-domain set alone: the four
preference domains of the extension run plus `finances_control`.

`finances_control` is a POSITIVE CONTROL, not a domain -- a monotonic money ladder
where ceiling retention is the expected, correct answer -- so it is held out of the
main figure entirely and reported on its own in the text. Pooling it would
flatter panel (a) with episodes that cannot move.

Three panels in the main figure, one per channel of the finding:

  (a) retention by arm --- what the challenge ASKS FOR decides whether the
      preference survives; justifying it is indistinguishable from doing nothing;
  (b) Delta-confidence among episodes that HELD --- the preferences that survive
      are held less confidently, which panel (a) alone records as nothing happening;
  (c) retention against the balance-pilot consistency covariate (PQ2).

Every bar carries its bootstrap 95% CI over pairs, per the house rule that no
figure ships without one.

Emits:
    paper/figures/persistence.png            (--scope main)
    paper/figures/persistence_domains.png    (--scope domains)

    python analysis/persistence_figures.py               # regenerates both
    python analysis/persistence_figures.py --scope main
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "analysis"))

from figure_style import AXIS, DPI, GRID, INK, INK_2, MUTED, SURFACE  # noqa: E402
from analysis.persistence_analysis import (  # noqa: E402
    EXTENSION_DOMAINS, POSITIVE_CONTROL, cluster_bootstrap, group,
)
from analysis.persistence_ext_stats import EXT, load  # noqa: E402

FIGS = REPO / "paper" / "figures"

ARMS = ("control", "reason_elicitation", "self_critique", "counter_consideration")
LABEL = {"control": "control\n(no challenge)",
         "reason_elicitation": "reason\nelicitation",
         "self_critique": "self\ncritique",
         "counter_consideration": "counter\nconsideration"}
# Control and reason_elicitation behave identically; the two arms that move the
# preference get the saturated hue. Encoding is "did it move", not identity.
COLOR = {"control": "#c8dcf3", "reason_elicitation": "#c8dcf3",
         "self_critique": "#2a78d6", "counter_consideration": "#2a78d6"}

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": AXIS,
    "text.color": INK, "axes.labelcolor": INK_2,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "savefig.dpi": DPI, "figure.dpi": DPI,
})


def bars(ax, xs, pts, los, his, colors, *, pct):
    for x, p, lo, hi, c in zip(xs, pts, los, his, colors):
        ax.bar(x, p, width=0.62, color=c, edgecolor=AXIS, linewidth=0.6, zorder=2)
        ax.plot([x, x], [lo, hi], color=INK, linewidth=1.4, zorder=3)
        ax.plot([x - 0.08, x + 0.08], [lo, lo], color=INK, linewidth=1.1, zorder=3)
        ax.plot([x - 0.08, x + 0.08], [hi, hi], color=INK, linewidth=1.1, zorder=3)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID, linewidth=0.7)
    ax.set_xticks(list(xs))
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


REPORTED_DOMAINS = (
    "video_games",
    "sports",
    "pop_culture",
    "sci_tech",
    "finances_control",
)

SCOPES = {
    # name: (episode files, domains kept, output filename)
    "main": ((EXT,), tuple(EXTENSION_DOMAINS), "persistence.png"),
}


def build(scope: str) -> None:
    files, domains, fname = SCOPES[scope]
    rows = [r for f in files for r in load(f)]
    scored = [r for r in rows if r.get("retained") is not None
              and r["domain"] in domains]          # positive control never included
    held_out = sum(1 for r in rows if r["domain"] == POSITIVE_CONTROL)
    print(f"[{scope}] {len(rows)} episodes -> {len(scored)} scored across "
          f"{len(domains)} domains ({len({r['pair_id'] for r in scored})} pairs)"
          + (f"; {held_out} {POSITIVE_CONTROL} episodes held out" if held_out else ""))

    dconf = lambda r: (None if r.get("conf_pre") is None or r.get("conf_post") is None
                       else r["conf_post"] - r["conf_pre"])

    fig, axes = plt.subplots(1, 3, figsize=(11.4, 3.5))

    # --- (a) retention by arm -------------------------------------------------
    ax = axes[0]
    pts, los, his = [], [], []
    for arm in ARMS:
        p, lo, hi, *_ = cluster_bootstrap(
            group(scored, lambda r, a=arm: r["arm"] == a, lambda r: r["retained"]))
        pts.append(p * 100); los.append(lo * 100); his.append(hi * 100)
    bars(ax, range(len(ARMS)), pts, los, his, [COLOR[a] for a in ARMS], pct=True)
    ax.set_xticklabels([LABEL[a] for a in ARMS], fontsize=7.5)
    ax.set_ylim(0, 108)
    ax.set_ylabel("retention (%)", fontsize=9)
    ax.set_title("(a) The preference survives, or does not,\naccording to what the "
                 "challenge asks for", fontsize=9, loc="left", color=INK)

    # --- (b) Delta-confidence among HELD episodes ------------------------------
    ax = axes[1]
    held = [r for r in scored if r["retained"] is True]
    pts, los, his = [], [], []
    for arm in ARMS:
        p, lo, hi, *_ = cluster_bootstrap(
            group(held, lambda r, a=arm: r["arm"] == a, dconf))
        pts.append(p); los.append(lo); his.append(hi)
    bars(ax, range(len(ARMS)), pts, los, his, [COLOR[a] for a in ARMS], pct=False)
    ax.axhline(0, color=AXIS, linewidth=0.9, zorder=1)
    ax.set_xticklabels([LABEL[a] for a in ARMS], fontsize=7.5)
    ax.set_ylabel(r"$\Delta$confidence (0--100 scale)", fontsize=9)
    ax.set_title("(b) Among preferences that DO survive, the two\narms that move "
                 "choices also cost confidence", fontsize=9, loc="left", color=INK)

    # --- (c) PQ2: retention against pilot consistency --------------------------
    ax = axes[2]
    levels = sorted({r["pilot_consistency"] for r in scored
                     if r["pilot_consistency"] is not None})
    pts, los, his, npairs = [], [], [], []
    for lev in levels:
        p, lo, hi, npair, _ = cluster_bootstrap(
            group(scored, lambda r, L=lev: r["pilot_consistency"] == L,
                  lambda r: r["retained"]))
        pts.append(p * 100); los.append(lo * 100); his.append(hi * 100)
        npairs.append(npair)
    ramp = ["#c8dcf3", "#79a9e3", "#2a78d6"]
    bars(ax, range(len(levels)), pts, los, his, ramp, pct=True)
    ax.set_xticklabels([f"{L:.1f}\n({n} pairs)" for L, n in zip(levels, npairs)],
                       fontsize=7.5)
    ax.set_xlabel("balance-pilot consistency", fontsize=8.5)
    ax.set_ylim(0, 108)
    ax.set_ylabel("retention (%)", fontsize=9)
    ax.set_title("(c) Preferences the model held more\nconsistently survive more often",
                 fontsize=9, loc="left", color=INK)

    fig.tight_layout()
    FIGS.mkdir(parents=True, exist_ok=True)
    out = FIGS / fname
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out.relative_to(REPO)}")


def build_domains() -> None:
    """Retention by arm across the four preference domains plus the positive control."""
    rows = load(EXT)
    scored = [r for r in rows if r.get("retained") is not None and r["domain"] in REPORTED_DOMAINS]
    fig, ax = plt.subplots(figsize=(12.0, 3.8))
    x_base = np.arange(len(REPORTED_DOMAINS))
    width = 0.18
    arm_to_offset = {arm: (i - 1.5) * width for i, arm in enumerate(ARMS)}
    for arm in ARMS:
        ys, los, his = [], [], []
        for dom in REPORTED_DOMAINS:
            p, lo, hi, *_ = cluster_bootstrap(
                group(scored,
                      lambda r, d=dom, a=arm: r["domain"] == d and r["arm"] == a,
                      lambda r: r["retained"]))
            ys.append((p * 100) if p is not None else np.nan)
            los.append((lo * 100) if p is not None else np.nan)
            his.append((hi * 100) if p is not None else np.nan)
        xs = x_base + arm_to_offset[arm]
        ax.bar(xs, ys, width=width * 0.9, color=COLOR[arm], edgecolor=AXIS,
               linewidth=0.6, zorder=2, label=LABEL[arm])
        for x, lo, hi in zip(xs, los, his):
            if np.isnan(lo) or np.isnan(hi):
                continue
            ax.plot([x, x], [lo, hi], color=INK, linewidth=1.2, zorder=3)
            ax.plot([x - 0.05, x + 0.05], [lo, lo], color=INK, linewidth=1.0, zorder=3)
            ax.plot([x - 0.05, x + 0.05], [hi, hi], color=INK, linewidth=1.0, zorder=3)

    ax.set_xticks(x_base)
    ax.set_xticklabels([d.replace("_", " ") for d in REPORTED_DOMAINS], rotation=20,
                       ha="right", fontsize=8)
    ax.set_ylim(0, 110)
    ax.set_ylabel("retention (%)", fontsize=9)
    ax.set_title("Retention by domain and arm for the approved persistence set",
                 fontsize=9.5, loc="left", color=INK)
    ax.axhline(0, color=AXIS, linewidth=0.9, zorder=1)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID, linewidth=0.7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False, fontsize=7.5, ncol=4, columnspacing=1.0,
              handlelength=1.1, loc="upper center", bbox_to_anchor=(0.5, 1.08))
    fig.tight_layout()
    out = FIGS / "persistence_domains.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out.relative_to(REPO)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="persistence figures, by domain scope")
    ap.add_argument("--scope", choices=("main", "domains", "both"),
                    default="both",
                    help="which figure set to draw; default regenerates all figures")
    a = ap.parse_args()
    scopes = ("main", "domains") if a.scope == "both" else (a.scope,)
    for sc in scopes:
        if sc == "domains":
            build_domains()
        else:
            build(sc)
