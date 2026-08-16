"""Figures for the preference-persistence result (PQ1-PQ3).

Two scopes, one per figure, because the paper uses them for different jobs:

  --scope original   the original four domains only (the k3 run). Sections 4.1-4.2
                     quote these estimates, so the figure beside them must be drawn
                     from exactly the same episodes -- no reconciliation, no caveat.
  --scope combined   the original run and the five-domain extension pooled across
                     the eight preference domains. This is the COMBINED view and it
                     belongs with Section 4.3, which is where the paper first
                     presents the extension as an independent replication. Putting
                     it in the headline figure would show the reader the replication
                     before the text has framed it as one.

`finances_control` is a POSITIVE CONTROL, not a domain -- a monotonic money ladder
where ceiling retention is the expected, correct answer -- so it is held out of the
combined figure entirely and reported on its own in the text. Pooling it would
flatter panel (a) with episodes that cannot move.

Three panels in both, one per channel of the finding:

  (a) retention by arm --- what the challenge ASKS FOR decides whether the
      preference survives; justifying it is indistinguishable from doing nothing;
  (b) Delta-confidence among episodes that HELD --- the preferences that survive
      are held less confidently, which panel (a) alone records as nothing happening;
  (c) retention against the balance-pilot consistency covariate (PQ2).

Every bar carries its bootstrap 95% CI over pairs, per the house rule that no
figure ships without one.

Emits:
    paper/figures/persistence.png            (--scope original)
    paper/figures/persistence_combined.png   (--scope combined)

    python analysis/persistence_figures.py               # regenerates both
    python analysis/persistence_figures.py --scope original
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
    EXTENSION_DOMAINS, ORIGINAL_DOMAINS, POSITIVE_CONTROL, cluster_bootstrap, group,
)
from analysis.persistence_ext_stats import EXT, K3, load  # noqa: E402

FIGS = REPO / "paper" / "figures"
OUT_DIR_DATA = REPO / "data" / "persistence"

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


POOLED_DOMAINS = tuple(ORIGINAL_DOMAINS) + tuple(EXTENSION_DOMAINS)

# All three targets ran the IDENTICAL 130-pair pool and answered essentially every
# episode, so this is a same-pool comparison rather than three item sets side by side.
#
# gemini-3.5-flash ran the same pool and is NOT here. It declines the forced choice in
# most episodes, leaving 273 of 1,560 scorable, so bars for it would rest on the pairs
# it agreed to answer -- the outcome-conditioned estimate §5.4 refuses to report for the
# order gap, and the same objection applies under challenge. Hatching and labelling it
# was tried and rejected: drawn beside two full-coverage models it still invites the
# comparison the paper says cannot be borne. Its episodes are reported as a coverage
# failure in the appendix, conditioning stated first, and never plotted here.
# See DEVIATIONS #7.
MODELS = [
    ("deepseek-v4-pro",  "persistence_deepseek_k3.jsonl", "#2a78d6"),
    ("gpt-5.4-nano",     "persistence_nano_k3.jsonl",     "#d1662b"),
    ("gemini-2.5-flash", "persistence_gemini25_k3.jsonl", "#4a9c6d"),
]

SCOPES = {
    # name: (episode files, domains kept, output filename)
    "original": ((K3,), tuple(ORIGINAL_DOMAINS), "persistence.png"),
    "combined": ((K3, EXT), POOLED_DOMAINS, "persistence_combined.png"),
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


def build_models() -> None:
    """Retention by arm across targets, on the same 130 pairs.

    Every bar here rests on full coverage: each target returned a scoreable choice at
    both elicitations in essentially all 1,560 episodes, so the three sets of bars are
    over the same pairs AND the same episodes. That is the condition for putting them
    beside each other, and it is why gemini-3.5-flash is not in MODELS.
    """
    dconf = lambda r: (None if r.get("conf_pre") is None or r.get("conf_post") is None
                       else r["conf_post"] - r["conf_pre"])
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 3.9))
    width = 0.26
    for ax, metric, ylab, pct in ((axes[0], "ret", "retention (%)", True),
                                  (axes[1], "dconf", r"$\Delta$confidence, held", False)):
        for mi, (name, fname, colour) in enumerate(MODELS):
            rows = [r for r in load(OUT_DIR_DATA / fname) if r.get("retained") is not None]
            xs, pts, los, his = [], [], [], []
            for ai, arm in enumerate(ARMS):
                sel = [r for r in rows if r["arm"] == arm]
                if metric == "dconf":
                    sel = [r for r in sel if r["retained"] is True]
                    g = group(sel, lambda r: True, dconf)
                else:
                    g = group(sel, lambda r: True, lambda r: r["retained"])
                pt, lo, hi, _, _ = cluster_bootstrap(g)
                if pt is None:
                    continue
                k = 100 if pct else 1
                xs.append(ai + (mi - (len(MODELS) - 1) / 2) * width)
                pts.append(pt * k); los.append(lo * k); his.append(hi * k)
            ax.bar(xs, pts, width=width * 0.90, color=colour, edgecolor=AXIS,
                   linewidth=0.6, zorder=2, label=name)
            for x, lo, hi in zip(xs, los, his):
                ax.plot([x, x], [lo, hi], color=INK, lw=1.2, zorder=3)
        ax.set_xticks(range(len(ARMS)))
        ax.set_xticklabels([LABEL[a] for a in ARMS], fontsize=7.5)
        ax.set_ylabel(ylab, fontsize=9)
        ax.set_axisbelow(True); ax.yaxis.grid(True, color=GRID, linewidth=0.7)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        if not pct:
            ax.axhline(0, color=AXIS, lw=0.9, zorder=1)
    axes[0].set_ylim(0, 132)
    # Above the bars, not on them: the tallest bar in this panel is at ceiling, so a
    # legend anywhere inside the plotting area lands on data.
    axes[0].legend(fontsize=7.4, frameon=False, loc="upper right", ncol=3,
                   handlelength=1.1, columnspacing=1.0)
    axes[0].set_title("(a) Retention by arm", fontsize=9.5, loc="left", color=INK)
    axes[1].set_title("(b) \u0394confidence among preferences that held",
                      fontsize=9.5, loc="left", color=INK)
    fig.suptitle("Same 130 pairs, three model families, full coverage on all three. "
                 "Control and reason-elicitation sit at ceiling and both challenge arms "
                 "move the choice.\nThe rank of the two challenge arms does not carry: "
                 "self-critique moves deepseek-v4-pro and gemini-2.5-flash most, "
                 "counter-consideration moves gpt-5.4-nano most.",
                 fontsize=8.4, color=INK_2, y=1.045, x=0.008, ha="left")
    fig.tight_layout()
    out = FIGS / "persistence_models.png"
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)
    print(f"  wrote {out.relative_to(REPO)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="persistence figures, by domain scope")
    ap.add_argument("--scope", choices=("original", "combined", "models", "both"), default="both",
                    help="which domain set to draw; default regenerates both")
    a = ap.parse_args()
    scopes = ("original", "combined", "models") if a.scope == "both" else (a.scope,)
    for sc in scopes:
        build_models() if sc == "models" else build(sc)
