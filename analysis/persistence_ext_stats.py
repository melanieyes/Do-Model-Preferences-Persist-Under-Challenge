#!/usr/bin/env python3
"""Generate paper/persist_ext_stats.tex — every persistence number the paper prints.

House rule (.claude/skills/paper-style): every number in the text traces to analysis
output; none are typed. Since DEVIATIONS #8 the reported study is the five-domain set
alone (four preference domains plus the finances_control positive control), so this is
the paper's single stats source for persistence, pair construction and the balance
pilot. The original-pool families (pqxo*, pqxp*) are retired with the pool.

Macro prefixes, one per domain set, so a number can never be quoted against the wrong set:

    pqxe*   the four preference domains  video_games, sports, pop_culture, sci_tech
    pqxl*   the same four, restricted to pairs with pilot position bias < 0.5
    pqxf*   finances_control, the positive control, reported alone and never pooled
    pqx…    run-level, pilot, prediction and confidence-baseline quantities
    pair…   shared identity facts (model, pilot k, upstream source commit)

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
    ARMS, BIAS_CUTOFF, EXTENSION_DOMAINS, POSITIVE_CONTROL,
    cluster_bootstrap, group,
)

EXT = ROOT / "data" / "persistence" / "persistence_deepseek_ext.jsonl"
PILOT = ROOT / "data" / "pairs" / "balance_pilot_ext.jsonl"
EXCLUDED = ROOT / "data" / "pairs" / "excluded_outcomes_ext.jsonl"
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

    ext_rows = load(EXT)
    ext_meta = json.loads(EXT.read_text().splitlines()[0])
    scored = [r for r in ext_rows if r.get("retained") is not None]

    pilot_lines = PILOT.read_text().splitlines()
    pilot_meta = json.loads(pilot_lines[0])
    pilot = [json.loads(x) for x in pilot_lines[1:]]
    excl_meta = json.loads(EXCLUDED.read_text().splitlines()[0])

    m: dict[str, str] = {}
    chk: list[tuple[str, str]] = []

    def num(x, d=1):
        return f"\\num{{{x:.{d}f}}}"

    def low_bias(r):
        b = r.get("pilot_position_bias")
        return b is not None and b < BIAS_CUTOFF

    # ---------------- shared identity facts ----------------
    m["pairModel"] = f"\\texttt{{{ext_meta['model']}}}"
    m["pairK"] = str(pilot_meta["k"])
    m["pairSourceCommit"] = excl_meta["source_file_commit"][:12]
    m["pairExcluded"] = str(excl_meta["n_excluded"])

    # ---------------- balance pilot (extension pool) ----------------
    pref_pilot = [r for r in pilot if r["domain"] != POSITIVE_CONTROL]
    twice = [r for r in pref_pilot if r["minority_frac"] >= 0.39]
    kept = [r for r in twice if r["slot_a_frac"] not in (0.0, 1.0)]
    m["pqxPiloted"] = str(len(pilot))
    m["pqxPilotPref"] = str(len(pref_pilot))
    m["pqxPilotRefusals"] = str(sum(r["n_refusal"] for r in pilot))
    m["pqxPilotNever"] = str(sum(1 for r in pref_pilot if r["minority_frac"] == 0))
    m["pqxPilotOnce"] = str(sum(1 for r in pref_pilot
                                if abs(r["minority_frac"] - 0.2) < 1e-9))
    m["pqxPilotTwice"] = str(len(twice))
    m["pqxPilotSlotDropped"] = str(len(twice) - len(kept))
    m["pqxKept"] = str(len(kept))
    chk.append(("pilot pref pairs never/once/twice/kept",
                f"{m['pqxPilotNever']}/{m['pqxPilotOnce']}/{m['pqxPilotTwice']}/"
                f"{m['pqxKept']} of {m['pqxPilotPref']}"))

    # ---------------- per-set PQ1 / PQ3 / PQ2 ----------------
    SETS = {
        "pqxe": [r for r in scored if r["domain"] in EXTENSION_DOMAINS],
        "pqxl": [r for r in scored if r["domain"] in EXTENSION_DOMAINS and low_bias(r)],
        "pqxf": [r for r in scored if r["domain"] == POSITIVE_CONTROL],
    }
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

    # ---------------- PQ3 among HELD episodes (the confidence channel) --------
    # Same contrast the choice channel uses — arm minus control, paired within
    # pair — but restricted to episodes whose choice did NOT move.
    for pre in ("pqxe", "pqxl"):
        held = [r for r in SETS[pre] if r["retained"] is True]
        held_nz = [r for r in held if r.get("conf_pre") not in (None, 0)]
        for arm in ARMS[1:]:
            p, lo, hi, npair, _ = paired_contrast(held, arm, dconf)
            if p is not None:
                m[f"{pre}Held{SHORT[arm]}"] = num(p)
                m[f"{pre}Held{SHORT[arm]}Lo"] = num(lo)
                m[f"{pre}Held{SHORT[arm]}Hi"] = num(hi)
                m[f"{pre}Held{SHORT[arm]}Pairs"] = str(npair)
            p, _, _, _, _ = paired_contrast(held_nz, arm, dconf)
            if p is not None:
                m[f"{pre}Held{SHORT[arm]}NoZero"] = num(p)
    for arm in ARMS[1:]:
        k = f"pqxeHeld{SHORT[arm]}"
        if k in m:
            chk.append((f"held-episode dconf vs control, {arm}",
                        f"{m[k]} [{m[k + 'Lo']}, {m[k + 'Hi']}] "
                        f"({m[k + 'Pairs']} pairs)"))

    # ---------------- confidence-baseline diagnostics (Limitations) -----------
    ctl = [r for r in SETS["pqxe"] if r["arm"] == "control"]
    ctl_scored = [r for r in ctl if dconf(r) is not None]
    m["pqxCtlScored"] = str(len(ctl_scored))
    m["pqxCtlZero"] = str(sum(1 for r in ctl_scored if dconf(r) == 0))
    chk.append(("control dconf exactly zero",
                f"{m['pqxCtlZero']} of {m['pqxCtlScored']} scored control episodes"))

    conf_rows = [r for r in SETS["pqxe"] if dconf(r) is not None]
    m["pqxZeroEps"] = str(sum(1 for r in conf_rows if r.get("conf_pre") == 0))

    def flip_gain(rows):
        """Flipped minus held mean dconf, within pair, over pairs with both."""
        per = defaultdict(lambda: {True: [], False: []})
        for r in rows:
            d = dconf(r)
            if d is not None and r["retained"] in (True, False):
                per[r["pair_id"]][r["retained"]].append(d)
        diff = {p: [float(np.mean(v[False]) - np.mean(v[True]))]
                for p, v in per.items() if v[True] and v[False]}
        return cluster_bootstrap(diff)

    g, glo, ghi, gpairs, _ = flip_gain(SETS["pqxe"])
    if g is not None:
        m["pqxFlipGain"] = num(g)
        m["pqxFlipGainPairs"] = str(gpairs)
    g2, *_ = flip_gain([r for r in SETS["pqxe"] if r.get("conf_pre") not in (None, 0)])
    if g2 is not None:
        m["pqxFlipGainNoZero"] = num(g2)
    band = [r for r in conf_rows if r.get("conf_pre") is not None
            and 85 <= r["conf_pre"] <= 100]
    bf = [dconf(r) for r in band if r["retained"] is False]
    bh = [dconf(r) for r in band if r["retained"] is True]
    if bf and bh:
        m["pqxBandFlip"] = num(float(np.mean(bf)))
        m["pqxBandHeld"] = num(float(np.mean(bh)))
    chk.append(("flip gain (flipped - held dconf, within pair)",
                f"{m.get('pqxFlipGain', '--')} over {m.get('pqxFlipGainPairs', 0)} pairs; "
                f"no-zero {m.get('pqxFlipGainNoZero', '--')}; band 85-100 "
                f"flip {m.get('pqxBandFlip', '--')} vs held {m.get('pqxBandHeld', '--')}"))

    pre_vals = [r["conf_pre"] for r in ext_rows if r.get("conf_pre") is not None]
    m["pqxNConfPre"] = str(len(pre_vals))
    m["pqxConfPreHundred"] = str(sum(1 for v in pre_vals if v == 100))
    m["pqxConfPreSeventy"] = str(sum(1 for v in pre_vals if v == 70))
    m["pqxConfPreZero"] = str(sum(1 for v in pre_vals if v == 0))
    chk.append(("conf_pre values 100 / 70 / 0",
                f"{m['pqxConfPreHundred']} / {m['pqxConfPreSeventy']} / "
                f"{m['pqxConfPreZero']} of {m['pqxNConfPre']}"))

    # ---------------- run-level ----------------
    m["pqxNEpisodes"] = str(len(ext_rows))
    m["pqxNPairs"] = str(len({r["pair_id"] for r in ext_rows}))
    m["pqxNDomains"] = str(len(EXTENSION_DOMAINS) + 1)          # 5 incl. the control

    # ---------------- the bias split ----------------
    ext_scored = SETS["pqxe"]
    drop_pairs = {r["pair_id"] for r in ext_scored if not low_bias(r)}
    keep_pairs = {r["pair_id"] for r in ext_scored if low_bias(r)}
    m["pqxBiasCut"] = num(BIAS_CUTOFF, 1)
    m["pqxBiasDropPairs"] = str(len(drop_pairs))
    m["pqxBiasKeepPairs"] = str(len(keep_pairs))
    chk.append(("pairs dropped at bias >= 0.5", f"{len(drop_pairs)} of "
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
    chk.append(("other preference domains, range",
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
    crit_more = counter_more = tied = 0
    dom_verdicts = {}
    for dom in EXTENSION_DOMAINS:
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
            crit_more += 1; dom_verdicts[dom] = "critique"
        elif cc < sc:
            counter_more += 1; dom_verdicts[dom] = "counter"
        else:
            tied += 1; dom_verdicts[dom] = "tie"
    m["pqxPredOneDoms"] = str(crit_more)
    m["pqxPredOneTied"] = str(tied)
    m["pqxPredOneCounterMore"] = str(counter_more)
    m["pqxPredOneOf"] = str(len(EXTENSION_DOMAINS))
    chk.append(("domains: self_critique reverses more / tied / counter more",
                f"{crit_more} / {tied} / {counter_more}  (of {len(EXTENSION_DOMAINS)}) "
                f"{dom_verdicts}"))

    # Prediction 1, first half: control is the fewest-reversal arm.
    ret_pool = {}
    for arm in ARMS:
        p, *_ = cluster_bootstrap(group(SETS["pqxe"], lambda r, a=arm: r["arm"] == a,
                                        lambda r: r["retained"]))
        ret_pool[arm] = p
    m["pqxPredOneCtlHighest"] = ("yes" if ret_pool["control"] >= max(ret_pool.values())
                                 else "no")
    chk.append(("control has the highest retention", m["pqxPredOneCtlHighest"]))

    # Prediction 2: record the retention gap that makes "at equal retention" fail.
    m["pqxPredTwoRetGap"] = num(
        (ret_pool["reason_elicitation"] - ret_pool["self_critique"]) * 100)
    chk.append(("retention gap reason_elicitation - self_critique",
                m["pqxPredTwoRetGap"]))

    # ---------------- PQ2 in full: retention at each consistency level --------
    LEVEL_NAME = {0.6: "Six", 0.8: "Eight", 1.0: "Ten"}
    for lev, name in LEVEL_NAME.items():
        p, lo, hi, npair, _ = cluster_bootstrap(group(
            SETS["pqxe"], lambda r, L=lev: r.get("pilot_consistency") == L,
            lambda r: r["retained"]))
        if p is not None:
            m[f"pqxCons{name}"] = num(p * 100)
            m[f"pqxCons{name}Pairs"] = str(npair)
    chk.append(("retention at consistency 0.6 / 0.8 / 1.0",
                " / ".join(m.get(f"pqxCons{n}", "--") for n in LEVEL_NAME.values())))

    # ---------------- the position check: flips are content, not slot ---------
    # Within pair x arm cells that flipped in BOTH presentation orders, do the
    # flips land on the same OPTION (content) or the same SLOT (layout)?
    for arm in CHALLENGE_ARMS:
        cells = defaultdict(lambda: defaultdict(list))
        for r in SETS["pqxe"]:
            if r["arm"] == arm:
                cells[r["pair_id"]][r["order"]].append(r)
        both = same_opt = same_slot = 0
        for pid, by_order in cells.items():
            if len(by_order) < 2:
                continue
            flips_per_order = [[r for r in eps if r["retained"] is False]
                               for eps in by_order.values()]
            if not all(flips_per_order):
                continue
            both += 1
            flips = [r for fl in flips_per_order for r in fl]
            if len({r["choice_post"] for r in flips}) == 1:
                same_opt += 1
            if len({r["slot_post"] for r in flips}) == 1:
                same_slot += 1
        key = SHORT[arm]
        m[f"pqxBoth{key}"] = str(both)
        if both:
            m[f"pqxSameOpt{key}"] = str(same_opt)
            m[f"pqxSameOptPct{key}"] = num(100 * same_opt / both, 0)
            m[f"pqxSameSlot{key}"] = str(same_slot)
            m[f"pqxSameSlotPct{key}"] = num(100 * same_slot / both, 0)
        chk.append((f"cells flipped in both orders, {arm}",
                    f"{both}; same option {same_opt}, same slot {same_slot}"))

    crit_flips = [r for r in SETS["pqxe"]
                  if r["arm"] == "self_critique" and r["retained"] is False]
    m["pqxFlipCritique"] = str(len(crit_flips))
    if crit_flips:
        sa = sum(1 for r in crit_flips if r["slot_post"] == "A")
        m["pqxFlipSlotA"] = num(100 * sa / len(crit_flips), 0)
        m["pqxFlipSlotB"] = num(100 * (len(crit_flips) - sa) / len(crit_flips), 0)
    cc = [r for r in SETS["pqxe"] if r["arm"] == "counter_consideration"]
    for slot, key in (("A", "A"), ("B", "B")):
        s = [r for r in cc if r["slot_pre"] == slot]
        if s:
            m[f"pqxFlipBySlot{key}"] = num(
                100 * sum(1 for r in s if r["retained"] is False) / len(s), 0)
    ord_gap = 0.0
    for arm in ARMS:
        by_order = {}
        for r in SETS["pqxe"]:
            if r["arm"] == arm:
                by_order.setdefault(r["order"], []).append(r["retained"])
        if len(by_order) == 2:
            a, b = [float(np.mean(v)) for v in by_order.values()]
            ord_gap = max(ord_gap, abs(a - b) * 100)
    m["pqxOrdGapMax"] = num(ord_gap)
    chk.append(("max retention gap between presentation orders (pp)",
                m["pqxOrdGapMax"]))

    # ---------------- differential missingness ----------------
    for arm, key in (("control", "Ctl"), ("reason_elicitation", "Reason")):
        s_arm = [r for r in ext_rows if r["arm"] == arm]
        m[f"pqxNA{key}"] = num(
            100 * sum(1 for r in s_arm if r.get("conf_post_kind") != "value") / len(s_arm))
    m["pqxNAtotal"] = str(sum(1 for r in ext_rows if r.get("conf_post_kind") != "value"))
    chk.append(("conf_post unparsed",
                f"{m['pqxNAtotal']} of {len(ext_rows)}; control {m['pqxNACtl']}%, "
                f"reason {m['pqxNAReason']}%"))

    # ---------------- write ----------------
    header = (
        "% GENERATED by analysis/persistence_ext_stats.py — do not hand-edit.\n"
        f"% Source: {EXT.name} ({len(ext_rows)} episodes), {PILOT.name}, "
        f"{EXCLUDED.name}.\n"
        "% pqxe preference 4 | pqxl bias<0.5 | pqxf finances_control (positive\n"
        "% control, never pooled) | pqx… run/pilot/prediction | pair… identity.\n")
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
