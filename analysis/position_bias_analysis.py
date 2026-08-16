"""Primary analysis — position bias in forced-choice preference elicitation.

Two cells of one comparison, matched pair-for-pair: the same 130-pair pool, the same
k=5 resamples, the same 3/2 presentation-order schedule, run once with per-call
reasoning suppressed and once with it enabled.

    order gap = |P(option a | a shown first) - P(option a | a shown second)|

0 means the choice follows content; 1 means it follows the slot the option sat in.

Because the two cells cover the same pairs, the difference is tested with a PAIRED
bootstrap over pairs — resampling pairs, not the two cells independently.

Emits:
    paper/figures/order_gap.png       Fig 1, the headline distribution
    paper/figures/gap_vs_mean.png     Fig 2, order-averaging hides the bias
    paper/posbias_stats.tex           every quoted number, as macros
    paper/posbias_table1.tex          per-domain table

    python analysis/position_bias_analysis.py
"""

from __future__ import annotations

import json
import statistics as st
import sys
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

# Two series, validated with the dataviz palette checker (all checks pass,
# worst adjacent CVD dE 24.7). OFF is the warm/alarming cell by design.
C_OFF, C_ON = "#eb6834", "#2a78d6"
BOOT_N, BOOT_SEED = 10_000, 20260815

# A naive filter that looks only at the order-averaged split, as a balance filter
# specified without a position check would.
NAIVE_BAND = (0.30, 0.70)
GAP_TRAP = 0.50

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": AXIS,
    "text.color": INK, "axes.labelcolor": INK_2,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "savefig.dpi": DPI, "figure.dpi": DPI,
})


def load(name: str) -> dict[str, dict]:
    lines = [json.loads(x) for x in (PAIRS / name).read_text().splitlines()]
    return {r["pair_id"]: r for r in lines[1:]}


def boot_mean(vals: np.ndarray, rng) -> tuple[float, float]:
    idx = rng.integers(0, len(vals), size=(BOOT_N, len(vals)))
    means = vals[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def boot_paired_diff(a: np.ndarray, b: np.ndarray, rng) -> tuple[float, float]:
    """CI on mean(a) - mean(b), resampling PAIRS (a and b are aligned)."""
    idx = rng.integers(0, len(a), size=(BOOT_N, len(a)))
    diffs = a[idx].mean(axis=1) - b[idx].mean(axis=1)
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def describe(vals: np.ndarray, rng) -> dict:
    lo, hi = boot_mean(vals, rng)
    return {
        "n": len(vals), "mean": float(vals.mean()), "median": float(np.median(vals)),
        "sd": float(vals.std(ddof=1)), "iqr_lo": float(np.percentile(vals, 25)),
        "iqr_hi": float(np.percentile(vals, 75)),
        "ci_lo": lo, "ci_hi": hi,
        "gt50": int((vals > 0.5).sum()), "gt90": int((vals > 0.9).sum()),
    }


def fig_order_gap(off: np.ndarray, on: np.ndarray, s_off: dict, s_on: dict) -> Path:
    bins = np.linspace(0, 1, 21)
    fig, axes = plt.subplots(2, 1, figsize=(7.0, 4.4), sharex=True,
                             gridspec_kw={"hspace": 0.34})
    for ax, vals, s, colour, title in (
        (axes[0], off, s_off, C_OFF, "reasoning suppressed"),
        (axes[1], on, s_on, C_ON, "reasoning enabled"),
    ):
        ax.hist(vals, bins=bins, color=colour, edgecolor=SURFACE, linewidth=1.4, zorder=3)
        ax.axvline(s["mean"], color=INK, lw=2.0, zorder=5)
        # CI drawn as a band around the mean, not an errorbar hidden in a caption
        ax.axvspan(s["ci_lo"], s["ci_hi"], color=INK, alpha=0.13, lw=0, zorder=4)
        # One text block, parked over the sparse middle of both distributions so it
        # never lands on a bar or on the other block.
        ax.text(0.235, 0.95,
                f"mean {s['mean']:.3f}   95% CI [{s['ci_lo']:.3f}, {s['ci_hi']:.3f}]\n"
                f"median {s['median']:.3f}   sd {s['sd']:.3f}\n"
                f"{s['gt50']} pairs > 0.5   ·   {s['gt90']} pairs > 0.9",
                transform=ax.transAxes, ha="left", va="top", size=7.5, color=INK,
                linespacing=1.5, zorder=6)
        ax.set_title(f"{title}   (n = {s['n']} pairs)", size=9.0, color=INK,
                     loc="left", pad=6)
        ax.set_ylabel("pairs", size=8.2)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
        ax.set_axisbelow(True)

    axes[1].set_xlabel(
        "order gap   |P(a | a shown first) − P(a | a shown second)|\n"
        "0 = choice follows content          1 = choice follows slot", size=8.4)
    axes[1].set_xlim(0, 1)
    out = FIGS / "order_gap.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def fig_gap_vs_mean(rows_off: list, rows_on: list, counts: dict) -> Path:
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    # the trap: looks balanced on the order-averaged split, driven by slot
    ax.add_patch(plt.Rectangle((NAIVE_BAND[0], GAP_TRAP),
                               NAIVE_BAND[1] - NAIVE_BAND[0], 1 - GAP_TRAP,
                               facecolor=GRID, alpha=0.75, lw=0, zorder=1))
    ax.axvspan(NAIVE_BAND[0], NAIVE_BAND[1], color=GRID, alpha=0.30, lw=0, zorder=0)

    for rows, colour, label in ((rows_off, C_OFF, "reasoning suppressed"),
                                (rows_on, C_ON, "reasoning enabled")):
        xs = [r["mean_p_option_a"] for r in rows]
        ys = [r["position_bias"] for r in rows]
        ax.scatter(xs, ys, s=34, color=colour, alpha=0.62, edgecolor=SURFACE,
                   linewidth=1.1, zorder=3, label=label)

    # Parked top-right, clear of both the legend and the orange ridge.
    ax.text(0.985, 0.985,
            "shaded: accepted by a naive 0.3–0.7 split filter\n"
            "dark: …and driven by slot (gap > 0.5)\n"
            f"reasoning off:  {counts['trap_off']} of {counts['naive_off']}\n"
            f"reasoning on:   {counts['trap_on']} of {counts['naive_on']}",
            transform=ax.transAxes, ha="right", va="top", size=7.6, color=INK,
            linespacing=1.5, zorder=6)
    ax.set_xlabel("order-averaged P(option a)   —  0.5 reads as \"balanced\"", size=8.4)
    ax.set_ylabel("order gap", size=8.4)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.03, 1.05)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(loc="lower center", frameon=False, fontsize=7.8, handletextpad=0.4,
              ncol=2, bbox_to_anchor=(0.5, -0.30))
    out = FIGS / "gap_vs_mean.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    on_m, off_m = load("balance_pilot.jsonl"), load("balance_pilot_noreason.jsonl")
    ids = sorted(set(on_m) & set(off_m))
    usable = [i for i in ids
              if on_m[i]["position_bias"] is not None and off_m[i]["position_bias"] is not None]
    rows_on = [on_m[i] for i in usable]
    rows_off = [off_m[i] for i in usable]
    on = np.array([r["position_bias"] for r in rows_on])
    off = np.array([r["position_bias"] for r in rows_off])

    rng = np.random.default_rng(BOOT_SEED)
    s_on, s_off = describe(on, rng), describe(off, rng)
    d_lo, d_hi = boot_paired_diff(off, on, rng)
    diff = float(off.mean() - on.mean())

    print(f"pairs matched in both cells: {len(usable)} of {len(ids)}\n")
    for name, s in (("OFF", s_off), ("ON", s_on)):
        print(f"  {name}: mean {s['mean']:.3f} [{s['ci_lo']:.3f}, {s['ci_hi']:.3f}]  "
              f"median {s['median']:.3f}  sd {s['sd']:.3f}  "
              f"IQR [{s['iqr_lo']:.3f}, {s['iqr_hi']:.3f}]  "
              f">0.5 {s['gt50']}  >0.9 {s['gt90']}")
    print(f"\n  DIFFERENCE (off - on): {diff:.3f}  95% CI [{d_lo:.3f}, {d_hi:.3f}]"
          f"   paired bootstrap over pairs, B={BOOT_N:,}\n")

    # --- robustness: the two cells measure the gap on different scales ----
    # With reasoning enabled the answer token's logprob saturates, so the ON gap is
    # close to binary while the OFF gap is graded. Re-run the contrast on two scales
    # that remove the asymmetry, so the headline does not rest on that artefact.
    off_b, on_b = (off > GAP_TRAP).astype(float), (on > GAP_TRAP).astype(float)
    b_lo, b_hi = boot_paired_diff(off_b, on_b, rng)
    # and once with no logprobs at all: how far the k=5 slot choices depart from
    # the 50/50 a content-driven answer would produce under a counterbalanced schedule
    off_s = np.array([abs(r["slot_a_frac"] - 0.5) * 2 for r in rows_off])
    on_s = np.array([abs(r["slot_a_frac"] - 0.5) * 2 for r in rows_on])
    s_lo, s_hi = boot_paired_diff(off_s, on_s, rng)
    print(f"  robustness, binarised at gap>{GAP_TRAP}: OFF {off_b.mean():.3f} "
          f"ON {on_b.mean():.3f}  diff {off_b.mean() - on_b.mean():.3f} "
          f"[{b_lo:.3f}, {b_hi:.3f}]")
    print(f"  robustness, discrete slot choices only: OFF {off_s.mean():.3f} "
          f"ON {on_s.mean():.3f}  diff {off_s.mean() - on_s.mean():.3f} "
          f"[{s_lo:.3f}, {s_hi:.3f}]\n")

    # --- STEP 3: what a naive split filter would accept -------------------
    def trap(rows):
        naive = [r for r in rows
                 if r["mean_p_option_a"] is not None
                 and NAIVE_BAND[0] <= r["mean_p_option_a"] <= NAIVE_BAND[1]]
        return naive, [r for r in naive if r["position_bias"] > GAP_TRAP]

    naive_on, trap_on = trap(rows_on)
    naive_off, trap_off = trap(rows_off)
    print(f"  naive {NAIVE_BAND[0]}-{NAIVE_BAND[1]} filter, reasoning ON : "
          f"accepts {len(naive_on)}, of which {len(trap_on)} have gap > {GAP_TRAP}")
    print(f"  naive {NAIVE_BAND[0]}-{NAIVE_BAND[1]} filter, reasoning OFF: "
          f"accepts {len(naive_off)}, of which {len(trap_off)} have gap > {GAP_TRAP}\n")

    # --- per domain -------------------------------------------------------
    MIN_N = 10   # below this an order-gap mean is not reported
    domains = sorted({r["domain"] for r in rows_on})
    table = []
    for d in domains:
        o = np.array([r["position_bias"] for r in rows_off if r["domain"] == d])
        n_ = np.array([r["position_bias"] for r in rows_on if r["domain"] == d])
        if len(o) < MIN_N:
            table.append((d, len(o), None, None))
            print(f"  {d:12s} n={len(o):3d}  no estimate at this n")
            continue
        table.append((d, len(o), float(o.mean()), float(n_.mean())))
        print(f"  {d:12s} n={len(o):3d}  OFF {o.mean():.3f}   ON {n_.mean():.3f}")

    FIGS.mkdir(parents=True, exist_ok=True)
    f1 = fig_order_gap(off, on, s_off, s_on)
    f2 = fig_gap_vs_mean(rows_off, rows_on, {
        "naive_on": len(naive_on), "trap_on": len(trap_on),
        "naive_off": len(naive_off), "trap_off": len(trap_off)})

    macros = {
        "pbN": len(usable),
        "pbOffMean": f"{s_off['mean']:.3f}", "pbOffLo": f"{s_off['ci_lo']:.3f}",
        "pbOffHi": f"{s_off['ci_hi']:.3f}", "pbOffMed": f"{s_off['median']:.3f}",
        "pbOffSd": f"{s_off['sd']:.3f}", "pbOffGtFifty": s_off["gt50"],
        "pbOffGtNinety": s_off["gt90"],
        "pbOnMean": f"{s_on['mean']:.3f}", "pbOnLo": f"{s_on['ci_lo']:.3f}",
        "pbOnHi": f"{s_on['ci_hi']:.3f}", "pbOnMed": f"{s_on['median']:.3f}",
        "pbOnSd": f"{s_on['sd']:.3f}", "pbOnGtFifty": s_on["gt50"],
        "pbOnGtNinety": s_on["gt90"],
        "pbDiff": f"{diff:.3f}", "pbDiffLo": f"{d_lo:.3f}", "pbDiffHi": f"{d_hi:.3f}",
        "pbBoot": f"{BOOT_N:,}".replace(",", "{,}"),
        "pbNaiveOn": len(naive_on), "pbTrapOn": len(trap_on),
        "pbNaiveOff": len(naive_off), "pbTrapOff": len(trap_off),
        "pbMinN": MIN_N,
        "pbBinDiff": f"{off_b.mean() - on_b.mean():.3f}",
        "pbBinLo": f"{b_lo:.3f}", "pbBinHi": f"{b_hi:.3f}",
        "pbSlotDiff": f"{off_s.mean() - on_s.mean():.3f}",
        "pbSlotLo": f"{s_lo:.3f}", "pbSlotHi": f"{s_hi:.3f}",
    }
    (REPO / "paper" / "posbias_stats.tex").write_text(
        "% Generated by analysis/position_bias_analysis.py — do not edit by hand.\n"
        + "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in macros.items())
    )

    rows_tex = []
    for d, n_, o, n_on in table:
        cell = ("\\multicolumn{2}{c}{\\emph{no estimate at this n}}"
                if o is None else f"{o:.3f} & {n_on:.3f}")
        rows_tex.append(f"{d.replace('_', '/')} & {n_} & {cell} \\\\")
    (REPO / "paper" / "posbias_table1.tex").write_text(
        "% Generated by analysis/position_bias_analysis.py — do not edit by hand.\n"
        "\\begin{tabular}{lrrr}\n\\toprule\n"
        "domain & pairs & gap, reasoning off & gap, reasoning on \\\\\n\\midrule\n"
        + "\n".join(rows_tex) + "\n\\bottomrule\n\\end{tabular}\n"
    )
    print(f"\nwrote {f1.relative_to(REPO)}, {f2.relative_to(REPO)}, posbias_stats.tex, "
          f"posbias_table1.tex")


if __name__ == "__main__":
    main()
