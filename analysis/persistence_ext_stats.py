#!/usr/bin/env python3
"""Generate paper/persist_ext_stats.tex — the extension numbers the paper prints.

Companion to persistence_paper_stats.py, which covers the original k3 run. Same house
rule (.claude/skills/paper-style): every number in the text traces to analysis output;
none are typed. This script is the trace for the extension additions to Section 5.4 and
for the predictions-vs-outcomes subsection.

Macro prefixes, one per domain set, so a number can never be quoted against the wrong set:

    pqxo*   original 4   task_work, wellbeing, recreation, possessions
    pqxe*   extension 4  video_games, sports, pop_culture, sci_tech
    pqxp*   pooled 8     the two above — NOT nine; finances_control is held out
    pqxl*   extension 4, restricted to pairs with pilot position bias < 0.5
    pqxf*   finances_control, the positive control, reported alone and never pooled

    python analysis/persistence_ext_stats.py [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis.persistence_analysis import (  # noqa: E402
    ARMS, BIAS_CUTOFF, EXTENSION_DOMAINS, ORIGINAL_DOMAINS, POSITIVE_CONTROL,
    cluster_bootstrap, group,
)

K3 = ROOT / "data" / "persistence" / "persistence_deepseek_k3.jsonl"
EXT = ROOT / "data" / "persistence" / "persistence_deepseek_ext.jsonl"
OUT = ROOT / "paper" / "persist_ext_stats.tex"

CHALLENGE_ARMS = ("self_critique", "counter_consideration")
SHORT = {"control": "Ctl", "reason_elicitation": "Reason",
         "self_critique": "Critique", "counter_consideration": "Counter"}


def load(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text().splitlines() if '"episode_id"' in x]


def dconf(r):
    if r.get("conf_pre") is None or r.get("conf_post") is None:
        return None
    return r["conf_post"] - r["conf_pre"]


def paired_contrast(rows, arm, value):
    """arm minus control, paired within pair, cluster bootstrap over pairs."""
    a = group(rows, lambda r: r["arm"] == arm, value)
    c = group(rows, lambda r: r["arm"] == "control", value)
    shared = sorted(set(a) & set(c))
    diff = {p: [float(np.mean(a[p]) - np.mean(c[p]))] for p in shared}
    return cluster_bootstrap(diff)


def slope_on_consistency(rows):
    """Per-pair retention regressed on pilot consistency, bootstrapped over pairs."""
    per_pair, cons = defaultdict(list), {}
    for r in rows:
        if r.get("pilot_consistency") is not None:
            per_pair[r["pair_id"]].append(r["retained"])
            cons[r["pair_id"]] = r["pilot_consistency"]
    pids = sorted(per_pair)
    if len(pids) < 3:
        return None, None, None, len(pids)
    x = np.array([cons[p] for p in pids], dtype=float)
    y = np.array([np.mean(per_pair[p]) for p in pids], dtype=float)
    if len(set(x.tolist())) < 2:
        return None, None, None, len(pids)
    slope = float(np.polyfit(x, y, 1)[0])
    rng = np.random.default_rng(20260815)
    boots = [np.polyfit(x[i], y[i], 1)[0]
             for i in (rng.integers(0, len(pids), len(pids)) for _ in range(10_000))
             if len(set(x[i].tolist())) > 1]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return slope, float(lo), float(hi), len(pids)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    k3_rows, ext_rows = load(K3), load(EXT)
    rows = k3_rows + ext_rows
    scored = [r for r in rows if r.get("retained") is not None]

    m: dict[str, str] = {}
    chk: list[tuple[str, str]] = []

    def num(x, d=1):
        return f"\\num{{{x:.{d}f}}}"

    def low_bias(r):
        b = r.get("pilot_position_bias")
        return b is not None and b < BIAS_CUTOFF

    POOLED = tuple(ORIGINAL_DOMAINS) + tuple(EXTENSION_DOMAINS)
    SETS = {
        "pqxo": [r for r in scored if r["domain"] in ORIGINAL_DOMAINS],
        "pqxe": [r for r in scored if r["domain"] in EXTENSION_DOMAINS],
        "pqxp": [r for r in scored if r["domain"] in POOLED],
        "pqxl": [r for r in scored if r["domain"] in EXTENSION_DOMAINS and low_bias(r)],
        "pqxf": [r for r in scored if r["domain"] == POSITIVE_CONTROL],
    }

    # ---------------- per-set PQ1 / PQ3 / PQ2 ----------------
    for pre, rs in SETS.items():
        m[f"{pre}Eps"] = str(len(rs))
        m[f"{pre}Pairs"] = str(len({r["pair_id"] for r in rs}))
        for arm in ARMS:
            p, lo, hi, _, _ = cluster_bootstrap(
                group(rs, lambda r, a=arm: r["arm"] == a, lambda r: r["retained"]))
            if p is None:
                continue
            m[f"{pre}Ret{SHORT[arm]}"] = num(p * 100)
            m[f"{pre}Ret{SHORT[arm]}Lo"] = num(lo * 100)
            m[f"{pre}Ret{SHORT[arm]}Hi"] = num(hi * 100)
        for arm in ARMS[1:]:
            p, lo, hi, _, _ = paired_contrast(rs, arm, lambda r: r["retained"])
            if p is not None:
                m[f"{pre}Diff{SHORT[arm]}"] = num(p * 100)
                m[f"{pre}Diff{SHORT[arm]}Lo"] = num(lo * 100)
                m[f"{pre}Diff{SHORT[arm]}Hi"] = num(hi * 100)
            c, clo, chi, _, _ = paired_contrast(rs, arm, dconf)
            if c is not None:
                m[f"{pre}Conf{SHORT[arm]}"] = num(c)
                m[f"{pre}Conf{SHORT[arm]}Lo"] = num(clo)
                m[f"{pre}Conf{SHORT[arm]}Hi"] = num(chi)
        s, slo, shi, npair = slope_on_consistency(rs)
        if s is not None:
            m[f"{pre}Slope"] = num(s, 3)
            m[f"{pre}SlopeLo"] = num(slo, 3)
            m[f"{pre}SlopeHi"] = num(shi, 3)

    # ---------------- run-level ----------------
    m["pqxNEpisodes"] = str(len(ext_rows))
    m["pqxNPairs"] = str(len({r["pair_id"] for r in ext_rows}))
    m["pqxNDomains"] = str(len(EXTENSION_DOMAINS) + 1)          # 5 incl. the control
    m["pqxNPooledDomains"] = str(len(POOLED))                   # 8, control held out
    m["pqxNCombinedEps"] = str(len(rows))

    # ---------------- the bias split ----------------
    ext_scored = SETS["pqxe"]
    drop_pairs = {r["pair_id"] for r in ext_scored if not low_bias(r)}
    keep_pairs = {r["pair_id"] for r in ext_scored if low_bias(r)}
    m["pqxBiasCut"] = num(BIAS_CUTOFF, 1)
    m["pqxBiasDropPairs"] = str(len(drop_pairs))
    m["pqxBiasKeepPairs"] = str(len(keep_pairs))
    chk.append(("extension pairs dropped at bias >= 0.5", f"{len(drop_pairs)} of "
                f"{len(drop_pairs) + len(keep_pairs)}"))

    # mean pilot position bias by domain — sports against the rest
    bias_by_dom = {}
    for dom in EXTENSION_DOMAINS:
        b = [r["pilot_position_bias"] for r in scored
             if r["domain"] == dom and r.get("pilot_position_bias") is not None]
        bias_by_dom[dom] = float(np.mean(b)) if b else None
    others = [v for d, v in bias_by_dom.items() if d != "sports" and v is not None]
    m["pqxSportsBias"] = num(bias_by_dom["sports"], 3)
    m["pqxOtherBiasLo"] = num(min(others), 3)
    m["pqxOtherBiasHi"] = num(max(others), 3)
    chk.append(("sports mean pilot position bias", f"{bias_by_dom['sports']:.3f}"))
    chk.append(("other extension domains, range",
                f"{min(others):.3f}-{max(others):.3f}"))

    # sports retention, pooled and by challenge arm
    for arm, key in [(None, "")] + [(a, SHORT[a]) for a in CHALLENGE_ARMS]:
        sel = (lambda r: r["domain"] == "sports") if arm is None else \
              (lambda r, a=arm: r["domain"] == "sports" and r["arm"] == a)
        p, lo, hi, _, _ = cluster_bootstrap(group(scored, sel, lambda r: r["retained"]))
        m[f"pqxSportsRet{key}"] = num(p * 100)
    chk.append(("sports retention, all arms", m["pqxSportsRet"]))

    # ---------------- finances_control, the manipulation check ----------------
    fc = SETS["pqxf"]
    p, lo, hi, npair, nobs = cluster_bootstrap(
        group(fc, lambda r: True, lambda r: r["retained"]))
    m["pqxfRet"] = num(p * 100)
    m["pqxfRetLo"] = num(lo * 100)
    m["pqxfRetHi"] = num(hi * 100)
    m["pqxfFlips"] = str(sum(1 for r in fc if r["retained"] is False))
    m["pqxfChallengeEps"] = str(sum(1 for r in fc if r["arm"] in CHALLENGE_ARMS))
    m["pqxfBias"] = num(float(np.mean([r["pilot_position_bias"] for r in fc
                                       if r.get("pilot_position_bias") is not None])), 3)
    chk.append(("finances_control retention (all arms)",
                f"{p*100:.1f}% [{lo*100:.1f}, {hi*100:.1f}], {nobs} eps, {npair} pairs"))
    chk.append(("finances_control flips under the two challenge arms",
                f"{sum(1 for r in fc if r['retained'] is False)} of "
                f"{sum(1 for r in fc if r['arm'] in CHALLENGE_ARMS)}"))

    # ---------------- predictions vs outcomes ----------------
    # Prediction 1, second half: is counter_consideration really the MOST reversing arm?
    # Three counts, because the honest statement needs all three: domains where
    # self_critique strictly reverses more, where counter_consideration does, and ties.
    # The prediction fails if counter_consideration is not strictly highest anywhere.
    crit_more = counter_more = tied = 0
    for dom in POOLED:
        rc = {}
        for arm in CHALLENGE_ARMS:
            p, *_ = cluster_bootstrap(group(
                scored, lambda r, d=dom, a=arm: r["domain"] == d and r["arm"] == a,
                lambda r: r["retained"]))
            rc[arm] = p
        sc, cc = rc["self_critique"], rc["counter_consideration"]
        if sc is None or cc is None:
            continue
        if sc < cc:
            crit_more += 1
        elif cc < sc:
            counter_more += 1
        else:
            tied += 1
    m["pqxPredOneDoms"] = str(crit_more)
    m["pqxPredOneTied"] = str(tied)
    m["pqxPredOneCounterMore"] = str(counter_more)
    m["pqxPredOneOf"] = str(len(POOLED))
    chk.append(("domains: self_critique reverses more / tied / counter more",
                f"{crit_more} / {tied} / {counter_more}  (of {len(POOLED)})"))

    # Prediction 1, first half: control is the fewest-reversal arm.
    ret_pool = {}
    for arm in ARMS:
        p, *_ = cluster_bootstrap(group(SETS["pqxp"], lambda r, a=arm: r["arm"] == a,
                                        lambda r: r["retained"]))
        ret_pool[arm] = p
    m["pqxPredOneCtlHighest"] = ("yes" if ret_pool["control"] >= max(ret_pool.values())
                                 else "no")
    chk.append(("control has the highest pooled retention",
                m["pqxPredOneCtlHighest"]))

    # Prediction 2: self_critique lowers confidence more than reason_elicitation,
    # "at equal retention" — record both the confidence order and the retention gap
    # that makes the precondition fail.
    m["pqxPredTwoRetGap"] = num(
        (ret_pool["reason_elicitation"] - ret_pool["self_critique"]) * 100)
    chk.append(("retention gap reason_elicitation - self_critique (pooled)",
                m["pqxPredTwoRetGap"]))

    # ---------------- differential missingness, extension run ----------------
    for arm, key in (("control", "Ctl"), ("reason_elicitation", "Reason")):
        s_arm = [r for r in ext_rows if r["arm"] == arm]
        m[f"pqxNA{key}"] = num(
            100 * sum(1 for r in s_arm if r.get("conf_post_kind") != "value") / len(s_arm))
    m["pqxNAtotal"] = str(sum(1 for r in ext_rows if r.get("conf_post_kind") != "value"))
    chk.append(("conf_post unparsed, extension run",
                f"{m['pqxNAtotal']} of {len(ext_rows)}; control {m['pqxNACtl']}%, "
                f"reason {m['pqxNAReason']}%"))

    # ---------------- write ----------------
    header = (
        "% GENERATED by analysis/persistence_ext_stats.py — do not hand-edit.\n"
        f"% Sources: {K3.name} ({len(k3_rows)} episodes) + {EXT.name} "
        f"({len(ext_rows)} episodes).\n"
        "% pqxo original 4 | pqxe extension 4 | pqxp pooled 8 | pqxl ext bias<0.5 |\n"
        "% pqxf finances_control (positive control, never pooled).\n")
    body = "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in sorted(m.items()))
    OUT.write_text(header + body)
    print(f"wrote {OUT.relative_to(ROOT)}  ({len(m)} macros)")

    if args.check:
        print("\nCHECK — computed values")
        print("-" * 78)
        for label, got in chk:
            print(f"  {label:<58} {got}")


if __name__ == "__main__":
    main()
