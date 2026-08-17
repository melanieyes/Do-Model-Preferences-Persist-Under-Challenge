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
    paper/figures/persistence_domains_<target>.png  (--scope models, one per target)
    paper/figures/persistence_confidence.png    (--scope confidence)
    paper/figures/persistence_models_ext.png    (--scope models)
    paper/figures/persistence_confidence_models.png (--scope models)

    python analysis/persistence_figures.py               # regenerates all
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

FINANCE_COLOR = "#e9a8c4"    # soft pink: the positive control, distinct from every arm blue

# Blue + soft-pink palette, validated (CVD dE >= 9; every bar carries a label).
MODEL_COLOUR = {"deepseek-v4-pro": "#2a78d6", "gpt-5.4-nano": "#e287ae",
                "gemini-2.5-flash": "#4a9c6d"}


def _targets():
    from analysis.persistence_models_ext_stats import TARGETS, load_merged
    return [(name, load_merged(files)) for _, name, files in TARGETS]


def build_models_ext() -> None:
    """Figure 1 of the submission: preference-domain retention by arm, three models.

    Same pool, same arms, same controls; finances_control is excluded here and
    reported as the separate manipulation check (finance_models.png).
    """
    targets = _targets()
    fig, ax = plt.subplots(figsize=(11.2, 4.4))
    width = 0.26
    for mi, (name, rows) in enumerate(targets):
        pref = [r for r in rows if r.get("retained") is not None
                and r["domain"] in EXTENSION_DOMAINS]
        xs, pts, los, his = [], [], [], []
        for ai, arm in enumerate(ARMS):
            p, lo, hi, *_ = cluster_bootstrap(
                group(pref, lambda r, a=arm: r["arm"] == a, lambda r: r["retained"]))
            if p is None:
                continue
            xs.append(ai + (mi - (len(targets) - 1) / 2) * width)
            pts.append(p * 100); los.append(lo * 100); his.append(hi * 100)
        ax.bar(xs, pts, width=width * 0.9, color=MODEL_COLOUR[name], edgecolor=AXIS,
               linewidth=0.6, zorder=2, label=name)
        for x, p_, lo, hi in zip(xs, pts, los, his):
            ax.plot([x, x], [lo, hi], color=INK, lw=1.2, zorder=3)
            ax.text(x, min(lo, p_) - 3.5, f"{p_:.0f}", ha="center", va="top",
                    fontsize=7.6, color=INK, fontweight="bold", zorder=4)
    ax.set_xticks(range(len(ARMS)))
    ax.set_xticklabels([LABEL[a] for a in ARMS], fontsize=8.5)
    ax.set_ylim(0, 118)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("retention, four preference domains (%)", fontsize=9)
    ax.set_title("Preference retention by challenge type across models "
                 "(same 80 pairs, same arms, same controls)",
                 fontsize=9.5, loc="left", color=INK)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID, linewidth=0.7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(fontsize=7.6, frameon=False, loc="upper right", ncol=3,
              handlelength=1.1, columnspacing=1.0)
    fig.tight_layout()
    out = FIGS / "persistence_models_ext.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out.relative_to(REPO)}")


def build_confidence_models() -> None:
    """Figure 3 of the submission: held-episode Delta-confidence by arm, three models.

    Per-arm means among episodes whose choice did not move, with cluster-bootstrap
    95% CIs; the value label sits under each bar.
    """
    targets = _targets()
    dconf = lambda r: (None if r.get("conf_pre") is None or r.get("conf_post") is None
                       else r["conf_post"] - r["conf_pre"])
    fig, ax = plt.subplots(figsize=(11.2, 4.2))
    width = 0.26
    for mi, (name, rows) in enumerate(targets):
        held = [r for r in rows if r.get("retained") is True
                and r["domain"] in EXTENSION_DOMAINS]
        xs, pts, los, his = [], [], [], []
        for ai, arm in enumerate(ARMS):
            p, lo, hi, *_ = cluster_bootstrap(
                group(held, lambda r, a=arm: r["arm"] == a, dconf))
            if p is None:
                continue
            xs.append(ai + (mi - (len(targets) - 1) / 2) * width)
            pts.append(p); los.append(lo); his.append(hi)
        ax.bar(xs, pts, width=width * 0.9, color=MODEL_COLOUR[name], edgecolor=AXIS,
               linewidth=0.6, zorder=2, label=name)
        for x, p_, lo, hi in zip(xs, pts, los, his):
            ax.plot([x, x], [lo, hi], color=INK, lw=1.2, zorder=3)
            ax.text(x, min(lo, p_) - 0.55, f"{p_:+.1f}", ha="center", va="top",
                    fontsize=7.3, color=INK, fontweight="bold", zorder=4)
    ax.axhline(0, color=AXIS, linewidth=0.9, zorder=1)
    ax.set_xticks(range(len(ARMS)))
    ax.set_xticklabels([LABEL[a] for a in ARMS], fontsize=8.5)
    ax.set_ylabel(r"$\Delta$confidence among HELD episodes", fontsize=9)
    ax.set_title("Confidence change among retained preferences, by model "
                 "(per-arm means, four preference domains)",
                 fontsize=9.5, loc="left", color=INK)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID, linewidth=0.7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(fontsize=7.6, frameon=False, loc="lower left", ncol=1,
              handlelength=1.1)
    fig.tight_layout()
    out = FIGS / "persistence_confidence_models.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out.relative_to(REPO)}")


def build_domains(rows=None,
                  out_name: str = "persistence_domains_deepseek_v4_pro.png",
                  model_label: str | None = None) -> None:
    """Retention by arm across the four preference domains plus the positive control."""
    if rows is None:
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
    DOMAIN_LABEL = {"video_games": "video games", "sports": "sports",
                    "pop_culture": "pop culture", "sci_tech": "science & tech",
                    "finances_control": "personal finances"}
    ax.set_xticklabels([DOMAIN_LABEL[d] for d in REPORTED_DOMAINS], rotation=20,
                       ha="right", fontsize=8)
    ax.set_ylim(0, 110)
    ax.set_ylabel("retention (%)", fontsize=9)
    ax.set_title("Retention by domain and arm"
                 + (f" — {model_label}" if model_label else " — deepseek-v4-pro"),
                 fontsize=9.5, loc="left", color=INK)
    ax.axhline(0, color=AXIS, linewidth=0.9, zorder=1)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID, linewidth=0.7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False, fontsize=7.5, ncol=4, columnspacing=1.0,
              handlelength=1.1, loc="lower right", bbox_to_anchor=(1.0, 1.02))
    fig.tight_layout()
    out = FIGS / out_name
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out.relative_to(REPO)}")


def build_confidence() -> None:
    """PQ3, pointed at directly: every HELD episode's Delta-confidence, one point each.

    Panel (b) of the main figure shows the per-arm means. This figure shows the
    episodes those means summarise, so a reader can see the phenomenon the design
    was built to detect: the choice is retained and the stated confidence drops
    anyway (e.g. A at 100 -> A at 70). Points are jittered within arm; the dark
    marker is the per-arm mean with its cluster-bootstrap 95% CI over pairs. The
    annotated point is a real episode, selected in code (the largest confidence
    drop among held self_critique episodes), never typed by hand.
    """
    rows = load(EXT)
    dconf = lambda r: (None if r.get("conf_pre") is None or r.get("conf_post") is None
                       else r["conf_post"] - r["conf_pre"])
    held = [r for r in rows
            if r.get("retained") is True and r["domain"] in EXTENSION_DOMAINS
            and dconf(r) is not None]
    fin_held = [r for r in rows
                if r.get("retained") is True and r["domain"] == POSITIVE_CONTROL
                and dconf(r) is not None]
    print(f"[confidence] {len(held)} held preference episodes, "
          f"{len(fin_held)} held {POSITIVE_CONTROL} episodes (drawn separately)")

    fig, ax = plt.subplots(figsize=(13.2, 4.4))
    rng = np.random.default_rng(20260815)      # jitter only; fixed for reproducibility
    STEP = 1.7                                 # room per arm for both clusters + labels

    def column(x, eps, colour, *, spread, big_labels):
        """One jittered cluster with mean rule, CI whisker and value labels."""
        ys = np.array([dconf(r) for r in eps], dtype=float)
        xs = x + rng.uniform(-spread, spread, size=len(ys))
        ax.scatter(xs, ys, s=14, color=colour, alpha=0.5,
                   edgecolors="none", zorder=2)
        p, lo, hi, _, nobs = cluster_bootstrap(group(eps, lambda r: True, dconf))
        w = spread + 0.06
        ax.plot([x - w, x + w], [p, p], color=INK, linewidth=1.8, zorder=4)
        ax.plot([x + w + 0.04, x + w + 0.04], [lo, hi], color=INK, linewidth=1.4,
                zorder=4)
        if big_labels:
            # labels on the LEFT of the cluster; the right side belongs to the
            # money-ladder cluster drawn beside it
            ax.text(x - w - 0.08, p, f"{p:+.1f}", fontsize=9, color=INK,
                    fontweight="bold", ha="right", va="center")
            ax.text(x - w - 0.08, p, f"\n[{lo:+.1f}, {hi:+.1f}]\nn={nobs}",
                    fontsize=6.8, color=INK_2, ha="right", va="top", linespacing=1.25)
        else:
            ax.text(x, min(0, lo) - 2.0, f"{p:+.1f}", fontsize=7.2, color=INK_2,
                    ha="center", va="top")

    # All five domains in one panel, per arm: the four preference domains as the
    # blue cluster, the money ladder as the grey cluster beside it — side by side
    # as separate estimates, never pooled.
    for i, arm in enumerate(ARMS):
        x = i * STEP
        column(x - 0.18, [r for r in held if r["arm"] == arm], COLOR[arm],
               spread=0.24, big_labels=True)
        column(x + 0.52, [r for r in fin_held if r["arm"] == arm], FINANCE_COLOR,
               spread=0.07, big_labels=False)

    # Annotate one real retained-but-shaken episode, picked by rule, not by hand.
    crit_held = [r for r in held if r["arm"] == "self_critique"]
    ex = min(crit_held, key=dconf)
    ex_x = ARMS.index("self_critique") * STEP - 0.18
    ax.annotate(
        f"choice kept ({ex['choice_pre'].upper()} → "
        f"{ex['choice_post'].upper()}), confidence "
        f"{ex['conf_pre']} → {ex['conf_post']}",
        xy=(ex_x, dconf(ex)), xytext=((len(ARMS) - 1) * STEP + 0.6, dconf(ex) - 14),
        fontsize=8, color=INK, ha="right",
        arrowprops=dict(arrowstyle="->", color=INK_2, linewidth=0.9))

    ax.set_xticks([i * STEP for i in range(len(ARMS))])
    ax.set_xticklabels([LABEL[a] for a in ARMS], fontsize=8.5)
    ax.set_ylabel(r"$\Delta$confidence among HELD episodes (0--100 scale)", fontsize=9)
    ax.set_title("All five approved domains: the choice survives; the stated confidence "
                 "does not always survive with it — except on personal finances",
                 fontsize=9.5, loc="left", color=INK)
    from matplotlib.lines import Line2D
    ax.legend(handles=[
        Line2D([], [], marker="o", ls="none", color=COLOR["control"], alpha=0.7,
               label="preference episodes: arms that leave the choice at ceiling"),
        Line2D([], [], marker="o", ls="none", color=COLOR["self_critique"], alpha=0.7,
               label="preference episodes: arms that move the choice"),
        Line2D([], [], marker="o", ls="none", color=FINANCE_COLOR, alpha=0.8,
               label="personal-finances episodes (control item, never pooled)"),
        Line2D([], [], color=INK, lw=1.8,
               label="per-cluster mean, with bootstrap 95% CI over pairs"),
    ], fontsize=6.8, frameon=False, loc="lower left", handlelength=1.2,
       borderaxespad=0.2)

    ax.axhline(0, color=AXIS, linewidth=0.9, zorder=1)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID, linewidth=0.7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    out = FIGS / "persistence_confidence.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out.relative_to(REPO)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="persistence figures, by domain scope")
    ap.add_argument("--scope",
                    choices=("domains", "confidence", "models", "both"),
                    default="both",
                    help="which figure set to draw; default regenerates all figures")
    a = ap.parse_args()
    scopes = (("domains", "confidence", "models")
              if a.scope == "both" else (a.scope,))
    for sc in scopes:
        if sc == "confidence":
            build_confidence()
        elif sc == "domains":
            build_domains()
        if sc == "models":
            build_models_ext()
            build_confidence_models()
            # one domain-split figure per target, uniformly named
            for name, rows in _targets():
                tag = name.replace(".", "").replace("-", "_")
                build_domains(rows, f"persistence_domains_{tag}.png", name)

