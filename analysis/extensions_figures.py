"""Extensions — cross-model position bias, and label-scheme robustness.

Every model is scored on the SAME statistic, the discrete order gap computed from the
k=5 choices alone:

    |frac(chose a | a shown first) - frac(chose a | a shown second)|

The continuous log-probability version is unavailable on Gemini, so the discrete one
is used throughout. On DeepSeek, where both exist, they agree to 0.001 — that
agreement is what licenses the substitution, and it is reported.

gemini-3.5-flash is deliberately NOT given a gap estimate. It declines the task in
the majority of trials, so only 25 of 130 pairs are scorable in its reasoning-on
cell; plotting that beside a 130-pair estimate would invite exactly the comparison
it cannot support. It is reported as coverage instead.

gpt-5.4-nano contributes ONE cell rather than an off/on pair: it spends no reasoning
tokens, so there is nothing to suppress. It is included because the gate is the order
gap on the model in use, not the presence of a reasoning toggle, and it passes that
gate (median 0.000). See DEVIATIONS #7.

Emits:
    paper/figures/three_model.png    model-specificity + coverage (not referenced by
                                     the paper; four_model.png from
                                     model_comparison_figures.py is the placed figure)
    paper/figures/label_schemes.png  Fig 5: does the bias survive relabeling?
    paper/ext_stats.tex              every quoted number, as macros
    paper/ext_table1.tex             cross-model summary table

    python analysis/extensions_figures.py
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

from figure_style import AXIS, DPI, GRID, INK, INK_2, MUTED, SURFACE  # noqa: E402

PAIRS = REPO / "data" / "pairs"
FIGS = REPO / "paper" / "figures"

C_OFF, C_ON = "#eb6834", "#2a78d6"
BOOT_N, BOOT_SEED = 10_000, 20260815

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": AXIS,
    "text.color": INK, "axes.labelcolor": INK_2,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "savefig.dpi": DPI, "figure.dpi": DPI,
})


def rows(name: str) -> list[dict]:
    return [json.loads(x) for x in (PAIRS / name).read_text().splitlines()][1:]


def discrete_gap(rec: dict) -> float | None:
    """Order gap from the k=5 choices alone — the statistic every model shares."""
    by = {f: [s for s in rec["samples"] if s["flip"] is f] for f in (False, True)}
    fr = {}
    for f, v in by.items():
        scored = [s for s in v if s.get("chose")]
        if scored:
            fr[f] = sum(1 for s in scored if s["chose"] == "a") / len(scored)
    return abs(fr[False] - fr[True]) if len(fr) == 2 else None


def boot_ci(v: np.ndarray, rng) -> tuple[float, float]:
    idx = rng.integers(0, len(v), size=(BOOT_N, len(v)))
    m = v[idx].mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def coverage(recs: list[dict]) -> dict:
    kinds = Counter(s.get("kind", "choice") for r in recs for s in r["samples"])
    total = sum(kinds.values())
    scorable = sum(1 for r in recs if discrete_gap(r) is not None)
    return {"total": total, "choice": kinds["choice"], "refusal": kinds["refusal"],
            "unparsed": kinds["unparsed"], "scorable_pairs": scorable,
            "pct_choice": 100 * kinds["choice"] / total if total else 0.0,
            "pct_refusal": 100 * kinds["refusal"] / total if total else 0.0}


CELLS = [
    ("deepseek-v4-pro", "off", "balance_pilot_noreason.jsonl", True),
    ("deepseek-v4-pro", "on", "balance_pilot.jsonl", True),
    ("gemini-2.5-flash", "off", "gemini_gemini-25-flash_off.jsonl", True),
    ("gemini-2.5-flash", "on", "gemini_gemini-25-flash_on.jsonl", True),
    # One cell, not two. gpt-5.4-nano spends no reasoning tokens at all (verified by
    # effect from usage.completion_tokens_details, not from the model name), so there
    # is no reasoning to suppress and no off/on contrast to draw. It enters the
    # comparison on the gate that applies to every target -- the order gap on the
    # model as it is actually used -- and passes it.
    ("gpt-5.4-nano", "none", "balance_pilot_nano.jsonl", True),
    # estimable=False: reported as coverage only, never as a gap
    ("gemini-3.5-flash", "off", "gemini_gemini-35-flash_off.jsonl", False),
    ("gemini-3.5-flash", "on", "gemini_gemini-35-flash_on.jsonl", False),
]

# How each cell's reasoning setting is named, in the figure and in the table. The
# nano cell is not "reasoning off" -- there is no reasoning stage to have turned off.
FIG_LABEL = {"off": "reasoning off", "on": "reasoning on", "none": "non-reasoning"}
TAB_LABEL = {"off": "off", "on": "on", "none": "non-reasoning"}
SHORT_NAME = {"deepseek-v4-pro": "deepseek v4", "gemini-2.5-flash": "gemini 2.5",
              "gemini-3.5-flash": "gemini 3.5", "gpt-5.4-nano": "gpt-5.4-nano"}


def fig_three_model(stats: dict) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.5),
                             gridspec_kw={"width_ratios": [1.72, 1.0], "wspace": 0.34})

    # --- panel A: per-pair gap, only where the cell is estimable -----------
    ax = axes[0]
    labels, y = [], 0
    yticks, ylabels = [], []
    rng = np.random.default_rng(BOOT_SEED)
    for model, setting, _, estimable in CELLS:
        s = stats[(model, setting)]
        yticks.append(y)
        ylabels.append(f"{model}\n{FIG_LABEL[setting]}")
        colour = C_OFF if setting == "off" else C_ON
        if estimable:
            g = s["gaps"]
            jitter = (rng.random(len(g)) - 0.5) * 0.30
            ax.scatter(g, y + jitter, s=15, color=colour, alpha=0.42,
                       edgecolor="none", zorder=3)
            ax.plot([s["median"], s["median"]], [y - 0.30, y + 0.30], color=INK,
                    lw=2.6, zorder=5, solid_capstyle="butt")
            ax.text(1.06, y, f"med {s['median']:.2f}   mean {s['mean']:.3f}\n"
                            f"[{s['lo']:.3f}, {s['hi']:.3f}]   n={len(g)}",
                    va="center", size=7.0, color=INK)
        else:
            ax.text(0.01, y, "not estimable — the model declines the task "
                             f"({s['cov']['pct_refusal']:.0f}% refusals, "
                             f"{s['cov']['scorable_pairs']}/130 pairs scorable)",
                    va="center", size=7.2, color=MUTED, style="italic")
        y += 1
    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels, size=7.4)
    # room on the right for the per-cell statistics, without spilling into panel b
    ax.set_xlim(-0.03, 1.72)
    ax.set_ylim(len(CELLS) - 0.45, -0.55)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xlabel("order gap   (0 = choice follows content, 1 = follows slot)", size=8.2)
    ax.set_title("a.  Same instrument, same 130 pairs — the magnitude is model-specific",
                 size=9.2, color=INK, loc="left", pad=8)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    for gx in (0, 0.25, 0.5, 0.75, 1.0):
        ax.axvline(gx, color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)

    # --- panel B: coverage -------------------------------------------------
    ax = axes[1]
    ys = np.arange(len(CELLS))
    vals = [stats[(m, s)]["cov"]["pct_choice"] for m, s, _, _ in CELLS]
    cols = [C_OFF if s == "off" else C_ON for _, s, _, _ in CELLS]
    ax.barh(ys, vals, height=0.60, color=cols, edgecolor=SURFACE, linewidth=2.0, zorder=3)
    for yy, v, (m, s, _, est) in zip(ys, vals, CELLS):
        ax.text(min(v + 2, 99), yy, f"{v:.0f}%", va="center", size=7.6, color=INK)
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{SHORT_NAME[m]} · {TAB_LABEL[s]}" for m, s, _, _ in CELLS],
                       size=7.2)
    ax.invert_yaxis()
    ax.set_xlim(0, 108)
    ax.set_xlabel("responses that were a usable forced choice (%)", size=8.2)
    ax.set_title("b.  …and on one model the question cannot be posed",
                 size=9.2, color=INK, loc="left", pad=8)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)

    out = FIGS / "three_model.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def fig_labels(lab: dict) -> Path:
    order = ["letters", "numeric", "ordinal", "verbatim"]
    pretty = {"letters": "Option A / Option B", "numeric": "Option 1 / Option 2",
              "ordinal": "First / Second", "verbatim": "no label —\nrepeat the option text"}
    fig, ax = plt.subplots(figsize=(7.2, 3.3))
    ys = np.arange(len(order))
    for y, k in zip(ys, order):
        s = lab[k]
        colour = C_ON if k == "verbatim" else C_OFF
        ax.plot([s["lo"], s["hi"]], [y, y], color=colour, lw=3.0, zorder=3,
                solid_capstyle="round", alpha=0.45)
        ax.scatter([s["mean"]], [y], s=64, color=colour, zorder=4,
                   edgecolor=SURFACE, linewidth=1.6)
        ax.text(s["hi"] + 0.02, y, f"{s['mean']:.3f}  [{s['lo']:.3f}, {s['hi']:.3f}]",
                va="center", size=7.4, color=INK)
    ax.set_yticks(ys)
    ax.set_yticklabels([pretty[k] for k in order], size=7.8)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.0)
    ax.set_xlabel("order gap, reasoning off   (mean and bootstrap 95% CI)", size=8.2)
    ax.set_title("Relabelling does not remove the bias; removing the label does",
                 size=9.2, color=INK, loc="left", pad=8)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    out = FIGS / "label_schemes.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    rng = np.random.default_rng(BOOT_SEED)
    FIGS.mkdir(parents=True, exist_ok=True)

    stats: dict = {}
    for model, setting, fname, estimable in CELLS:
        recs = rows(fname)
        g = np.array([x for x in (discrete_gap(r) for r in recs) if x is not None])
        cov = coverage(recs)
        entry = {"gaps": g, "cov": cov, "estimable": estimable}
        if len(g) > 1:
            lo, hi = boot_ci(g, rng)
            entry |= {"mean": float(g.mean()), "median": float(np.median(g)),
                      "lo": lo, "hi": hi}
        stats[(model, setting)] = entry

    print(f"{'model':18s} {'set':4s} {'n':>4s} {'mean':>7s} {'median':>7s} "
          f"{'95% CI':>18s} {'%choice':>8s} {'%refusal':>9s}")
    for model, setting, _, est in CELLS:
        s = stats[(model, setting)]
        ci = f"[{s['lo']:.3f}, {s['hi']:.3f}]" if "mean" in s else "—"
        mean = f"{s['mean']:.3f}" if "mean" in s else "—"
        med = f"{s['median']:.3f}" if "mean" in s else "—"
        tag = "" if est else "   <- coverage only"
        print(f"{model:18s} {setting:4s} {len(s['gaps']):4d} {mean:>7s} {med:>7s} "
              f"{ci:>18s} {s['cov']['pct_choice']:7.1f}% {s['cov']['pct_refusal']:8.1f}%{tag}")

    # --- label schemes ----------------------------------------------------
    lab_rows = rows("label_schemes.jsonl")
    lab = {}
    for scheme in ["letters", "numeric", "ordinal", "verbatim"]:
        g = np.array([r["discrete_order_gap"] for r in lab_rows
                      if r["scheme"] == scheme and r["discrete_order_gap"] is not None])
        lo, hi = boot_ci(g, rng)
        lab[scheme] = {"mean": float(g.mean()), "lo": lo, "hi": hi,
                       "median": float(np.median(g)), "n": len(g)}
        print(f"  label {scheme:9s} n={len(g)} mean {g.mean():.3f} [{lo:.3f}, {hi:.3f}]")

    f1 = fig_three_model(stats)
    f2 = fig_labels(lab)

    ds_off, ds_on = stats[("deepseek-v4-pro", "off")], stats[("deepseek-v4-pro", "on")]
    g25_off, g25_on = stats[("gemini-2.5-flash", "off")], stats[("gemini-2.5-flash", "on")]
    g35_on, g35_off = stats[("gemini-3.5-flash", "on")], stats[("gemini-3.5-flash", "off")]
    nano = stats[("gpt-5.4-nano", "none")]

    def diff_ci(a, b):
        n = min(len(a), len(b))
        idx = rng.integers(0, n, size=(BOOT_N, n))
        d = a[:n][idx].mean(axis=1) - b[:n][idx].mean(axis=1)
        return (float(a.mean() - b.mean()),
                float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5)))

    d25 = diff_ci(g25_off["gaps"], g25_on["gaps"])

    m = {
        "extDsOff": f"{ds_off['mean']:.3f}", "extDsOffMed": f"{ds_off['median']:.3f}",
        "extDsOn": f"{ds_on['mean']:.3f}",
        "extGtwoOff": f"{g25_off['mean']:.3f}", "extGtwoOffMed": f"{g25_off['median']:.3f}",
        "extGtwoOffLo": f"{g25_off['lo']:.3f}", "extGtwoOffHi": f"{g25_off['hi']:.3f}",
        "extGtwoOn": f"{g25_on['mean']:.3f}",
        "extGtwoOnLo": f"{g25_on['lo']:.3f}", "extGtwoOnHi": f"{g25_on['hi']:.3f}",
        "extGtwoN": len(g25_off["gaps"]),
        "extGtwoDiff": f"{d25[0]:+.3f}", "extGtwoDiffLo": f"{d25[1]:+.3f}",
        "extGtwoDiffHi": f"{d25[2]:+.3f}",
        "extGthreeRefusalOn": f"{g35_on['cov']['pct_refusal']:.0f}",
        "extGthreeRefusalOff": f"{g35_off['cov']['pct_refusal']:.0f}",
        "extGthreeScorableOn": g35_on["cov"]["scorable_pairs"],
        "extGthreeScorableOff": g35_off["cov"]["scorable_pairs"],
        "extGthreeChoiceOn": g35_on["cov"]["choice"],
        "extRatio": f"{ds_off['mean'] / g25_off['mean']:.1f}",
        # The gate a new target has to clear before its episodes mean anything: the
        # order gap on the model as used. Median, not mean — the mean is carried by a
        # minority tail on every model here.
        "extNanoGap": f"{nano['mean']:.3f}", "extNanoGapMed": f"{nano['median']:.3f}",
        "extNanoGapLo": f"{nano['lo']:.3f}", "extNanoGapHi": f"{nano['hi']:.3f}",
        "extNanoN": len(nano["gaps"]),
        "extNanoChoice": f"{nano['cov']['pct_choice']:.0f}",
    }
    for k in ["letters", "numeric", "ordinal", "verbatim"]:
        m[f"lab{k.capitalize()}"] = f"{lab[k]['mean']:.3f}"
        m[f"lab{k.capitalize()}Lo"] = f"{lab[k]['lo']:.3f}"
        m[f"lab{k.capitalize()}Hi"] = f"{lab[k]['hi']:.3f}"

    (REPO / "paper" / "ext_stats.tex").write_text(
        "% Generated by analysis/extensions_figures.py — do not edit by hand.\n"
        + "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in m.items())
    )

    tex = ["% Generated by analysis/extensions_figures.py — do not edit by hand.",
           "\\begin{tabular}{llrrrr}", "\\toprule",
           "model & reasoning & pairs & mean gap & median & usable \\\\", "\\midrule"]
    for model, setting, _, est in CELLS:
        s = stats[(model, setting)]
        if est:
            tex.append(f"\\texttt{{{model}}} & {TAB_LABEL[setting]} & {len(s['gaps'])} & "
                       f"{s['mean']:.3f} & {s['median']:.3f} & "
                       f"{s['cov']['pct_choice']:.0f}\\% \\\\")
        else:
            tex.append(f"\\texttt{{{model}}} & {TAB_LABEL[setting]} & "
                       f"{s['cov']['scorable_pairs']} & "
                       f"\\multicolumn{{2}}{{c}}{{\\emph{{not estimable}}}} & "
                       f"{s['cov']['pct_choice']:.0f}\\% \\\\")
    tex += ["\\bottomrule", "\\end{tabular}"]
    (REPO / "paper" / "ext_table1.tex").write_text("\n".join(tex) + "\n")

    print(f"\nwrote {f1.relative_to(REPO)}, {f2.relative_to(REPO)}, ext_stats.tex, ext_table1.tex")


if __name__ == "__main__":
    main()
