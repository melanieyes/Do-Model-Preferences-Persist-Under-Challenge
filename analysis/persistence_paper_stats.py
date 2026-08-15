#!/usr/bin/env python3
"""Generate paper/persist_stats.tex — every persistence number the paper prints.

House rule (.claude/skills/paper-style): every number in the text traces to analysis
output; none are typed from memory. This script is the trace for Sections 3, 4.3,
5.7 and the Limitations, exactly as pair_balance_figures.py and
position_bias_analysis.py are for the sections before them.

It also serves as an independent check: run with --check to print each quantity
against the value the paper claims, so a number that has drifted is visible rather
than silently different.

    python analysis/persistence_paper_stats.py [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis.persistence_analysis import cluster_bootstrap, group  # noqa: E402

DATA = ROOT / "data" / "persistence" / "persistence_deepseek_k3.jsonl"
OUT = ROOT / "paper" / "persist_stats.tex"

ARMS = ("control", "reason_elicitation", "self_critique", "counter_consideration")
CHALLENGE_ARMS = ("self_critique", "counter_consideration")
SHORT = {"control": "Ctl", "reason_elicitation": "Reason",
         "self_critique": "Critique", "counter_consideration": "Counter"}


def load() -> list[dict]:
    return [json.loads(x) for x in DATA.read_text().splitlines() if '"episode_id"' in x]


def paired_contrast(rows, arm, value, subset=lambda r: True):
    """arm minus control, paired within pair, cluster bootstrap over pairs."""
    a = group([r for r in rows if subset(r)], lambda r: r["arm"] == arm, value)
    c = group([r for r in rows if subset(r)], lambda r: r["arm"] == "control", value)
    shared = sorted(set(a) & set(c))
    diff = {p: [float(np.mean(a[p]) - np.mean(c[p]))] for p in shared}
    return cluster_bootstrap(diff)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    rows = load()
    scored = [r for r in rows if r.get("retained") is not None]
    dconf = lambda r: (None if r.get("conf_pre") is None or r.get("conf_post") is None
                       else r["conf_post"] - r["conf_pre"])
    m: dict[str, str] = {}
    chk: list[tuple[str, str, str]] = []          # (label, computed, claimed)

    def num(x, d=1):
        return f"\\num{{{x:.{d}f}}}"

    # ---------------- PQ1 ----------------
    for arm in ARMS:
        p, lo, hi, npair, nobs = cluster_bootstrap(
            group(scored, lambda r, a=arm: r["arm"] == a, lambda r: r["retained"]))
        m[f"pqRet{SHORT[arm]}"] = num(p * 100)
        m[f"pqRet{SHORT[arm]}Lo"] = num(lo * 100)
        m[f"pqRet{SHORT[arm]}Hi"] = num(hi * 100)
    for arm in ARMS[1:]:
        p, lo, hi, npair, _ = paired_contrast(scored, arm, lambda r: r["retained"])
        m[f"pqDiff{SHORT[arm]}"] = num(p * 100)
        m[f"pqDiff{SHORT[arm]}Lo"] = num(lo * 100)
        m[f"pqDiff{SHORT[arm]}Hi"] = num(hi * 100)

    # ---------------- PQ2 ----------------
    per_pair, cons = defaultdict(list), {}
    for r in scored:
        if r["pilot_consistency"] is not None:
            per_pair[r["pair_id"]].append(r["retained"])
            cons[r["pair_id"]] = r["pilot_consistency"]
    pids = sorted(per_pair)
    x = np.array([cons[p] for p in pids])
    y = np.array([np.mean(per_pair[p]) for p in pids])
    slope = float(np.polyfit(x, y, 1)[0])
    rng = np.random.default_rng(20260815)
    boots = [np.polyfit(x[i], y[i], 1)[0]
             for i in (rng.integers(0, len(pids), len(pids)) for _ in range(10_000))
             if len(set(x[i].tolist())) > 1]
    slo, shi = np.percentile(boots, [2.5, 97.5])
    m["pqSlope"] = num(slope, 3)
    m["pqSlopeLo"] = num(slo, 3)
    m["pqSlopeHi"] = num(shi, 3)
    for lev, key in ((0.6, "Six"), (0.8, "Eight"), (1.0, "Ten")):
        p, lo, hi, npair, nobs = cluster_bootstrap(
            group(scored, lambda r, L=lev: r["pilot_consistency"] == L,
                  lambda r: r["retained"]))
        m[f"pqCons{key}"] = num(p * 100)
        m[f"pqCons{key}Pairs"] = str(npair)

    # ---------------- PQ3 ----------------
    for arm in ARMS[1:]:
        p, lo, hi, _, _ = paired_contrast(scored, arm, dconf)
        m[f"pqConf{SHORT[arm]}"] = num(p)
        m[f"pqConf{SHORT[arm]}Lo"] = num(lo)
        m[f"pqConf{SHORT[arm]}Hi"] = num(hi)

    # ---------------- PQ3 robust: held episodes only ----------------
    held = lambda r: r["retained"] is True
    for arm in CHALLENGE_ARMS:
        p, lo, hi, npair, _ = paired_contrast(scored, arm, dconf, subset=held)
        m[f"pqHeld{SHORT[arm]}"] = num(p, 2)
        m[f"pqHeld{SHORT[arm]}Lo"] = num(lo, 2)
        m[f"pqHeld{SHORT[arm]}Hi"] = num(hi, 2)
        m[f"pqHeld{SHORT[arm]}Pairs"] = str(npair)
        # same thing with conf_pre == 0 dropped
        p0, lo0, hi0, _, _ = paired_contrast(
            scored, arm, dconf, subset=lambda r: held(r) and r.get("conf_pre") != 0)
        m[f"pqHeld{SHORT[arm]}NoZero"] = num(p0, 2)

    # ---------------- PQ4 ----------------
    for dom, key in (("wellbeing", "Well"), ("recreation", "Rec")):
        for arm in CHALLENGE_ARMS:
            p, *_ = cluster_bootstrap(group(
                scored, lambda r, a=arm, d=dom: r["arm"] == a and r["domain"] == d,
                lambda r: r["retained"]))
            m[f"pq{key}Ret{SHORT[arm]}"] = num(p * 100)
            pc, *_ = cluster_bootstrap(group(
                scored, lambda r, a=arm, d=dom: r["arm"] == a and r["domain"] == d,
                dconf))
            m[f"pq{key}Conf{SHORT[arm]}"] = num(pc)

    # ---------------- POSITION CHECK ----------------
    # A pair x arm cell holds k=3 episodes split 2/1 across presentation orders.
    # Cells that flipped in BOTH orders are the ones that can distinguish a flip
    # driven by content (same OPTION each time) from one driven by slot (same SLOT).
    for arm in CHALLENGE_ARMS:
        cells = defaultdict(list)
        for r in scored:
            if r["arm"] == arm and r["retained"] is False:
                cells[r["pair_id"]].append(r)
        both = {p: v for p, v in cells.items()
                if len({e["order"] for e in v}) == 2}
        same_opt = sum(1 for v in both.values() if len({e["choice_post"] for e in v}) == 1)
        same_slot = sum(1 for v in both.values() if len({e["slot_post"] for e in v}) == 1)
        n = len(both)
        m[f"pqBoth{SHORT[arm]}"] = str(n)
        m[f"pqSameOpt{SHORT[arm]}"] = str(same_opt)
        m[f"pqSameOptPct{SHORT[arm]}"] = num(100 * same_opt / n, 0)
        m[f"pqSameSlot{SHORT[arm]}"] = str(same_slot)
        m[f"pqSameSlotPct{SHORT[arm]}"] = num(100 * same_slot / n, 0)
        chk.append((f"{arm}: cells flipped in both orders", str(n), "47 / 38"))
        chk.append((f"{arm}: same OPTION", f"{same_opt}/{n} "
                    f"({100*same_opt/n:.0f}%)", "40/47 (85%) / 27/38 (71%)"))
        chk.append((f"{arm}: same SLOT", f"{same_slot}/{n} "
                    f"({100*same_slot/n:.0f}%)", "3/47 (6%) / 5/38 (13%)"))

    # slot_post balance among flipped self_critique episodes
    flipped_sc = [r for r in scored
                  if r["arm"] == "self_critique" and r["retained"] is False]
    sc_slots = Counter(r["slot_post"] for r in flipped_sc)
    tot = sum(sc_slots.values())
    m["pqFlipCritique"] = str(len(flipped_sc))
    m["pqFlipSlotA"] = num(100 * sc_slots.get("A", 0) / tot)
    m["pqFlipSlotB"] = num(100 * sc_slots.get("B", 0) / tot)
    chk.append(("self_critique flipped episodes", str(len(flipped_sc)), "173"))
    chk.append(("  slot_post A / B",
                f"{100*sc_slots.get('A',0)/tot:.1f}% / {100*sc_slots.get('B',0)/tot:.1f}%",
                "49.1% / 50.9%"))

    # flip rate by the slot the PRE choice occupied
    cc = [r for r in scored if r["arm"] == "counter_consideration"]
    for slot in ("A", "B"):
        s = [r for r in cc if r["slot_pre"] == slot]
        rate = 100 * sum(1 for r in s if r["retained"] is False) / len(s)
        m[f"pqFlipBySlot{slot}"] = num(rate)
    chk.append(("counter_consideration flip rate by pre-slot A / B",
                f"{float(m['pqFlipBySlotA']):.1f}% / {float(m['pqFlipBySlotB']):.1f}%"
                if False else f"{m['pqFlipBySlotA']} / {m['pqFlipBySlotB']}",
                "38.1% / 38.9%"))

    # retention by presentation order, per challenge arm
    ord_gaps = []
    for arm in CHALLENGE_ARMS:
        by = {}
        for o in ("a_first", "b_first"):
            s = [r for r in scored if r["arm"] == arm and r["order"] == o]
            by[o] = 100 * sum(1 for r in s if r["retained"]) / len(s)
        ord_gaps.append(abs(by["a_first"] - by["b_first"]))
        m[f"pqOrdGap{SHORT[arm]}"] = num(abs(by["a_first"] - by["b_first"]))
    m["pqOrdGapMax"] = num(max(ord_gaps))
    chk.append(("retention gap by presentation order (challenge arms)",
                " / ".join(f"{g:.1f}" for g in ord_gaps), "2-5 points"))

    # the 5 balance-pilot slot-driven pairs, challenge arms only
    slotty = {r["pair_id"] for r in scored
              if r.get("pilot_slot_a_frac") in (0.0, 1.0)}
    sc_cc = [r for r in scored if r["arm"] in CHALLENGE_ARMS]
    fs = [r for r in sc_cc if r["pair_id"] in slotty]
    fo = [r for r in sc_cc if r["pair_id"] not in slotty]
    m["pqSlottyPairs"] = str(len(slotty))
    m["pqSlottyEps"] = str(len(fs))
    m["pqSlottyFlip"] = num(100 * sum(1 for r in fs if not r["retained"]) / len(fs), 0)
    m["pqOtherPairs"] = str(130 - len(slotty))
    m["pqOtherFlip"] = num(100 * sum(1 for r in fo if not r["retained"]) / len(fo), 0)
    chk.append(("slot-driven pairs / episodes", f"{len(slotty)} / {len(fs)}", "5 / 30"))
    chk.append(("  flip rate slot-driven vs other",
                f"{100*sum(1 for r in fs if not r['retained'])/len(fs):.0f}% vs "
                f"{100*sum(1 for r in fo if not r['retained'])/len(fo):.0f}%", "70% vs 40%"))

    # ---------------- LIMITATIONS: the confidence quantity we cannot separate ----
    flipped = lambda r: r["retained"] is False
    fa = group([r for r in scored if r["arm"] in CHALLENGE_ARMS and flipped(r)],
               lambda r: True, dconf)
    ha = group([r for r in scored if r["arm"] in CHALLENGE_ARMS and held(r)],
               lambda r: True, dconf)
    shared = sorted(set(fa) & set(ha))
    wp = {p: [float(np.mean(fa[p]) - np.mean(ha[p]))] for p in shared}
    p_all, *_ = cluster_bootstrap(wp)
    m["pqFlipGain"] = num(p_all)
    fa0 = group([r for r in scored if r["arm"] in CHALLENGE_ARMS and flipped(r)
                 and r.get("conf_pre") != 0], lambda r: True, dconf)
    ha0 = group([r for r in scored if r["arm"] in CHALLENGE_ARMS and held(r)
                 and r.get("conf_pre") != 0], lambda r: True, dconf)
    sh0 = sorted(set(fa0) & set(ha0))
    wp0 = {p: [float(np.mean(fa0[p]) - np.mean(ha0[p]))] for p in sh0}
    p_nz, *_ = cluster_bootstrap(wp0)
    m["pqFlipGainNoZero"] = num(p_nz)
    n_zero = sum(1 for r in scored if r.get("conf_pre") == 0)
    m["pqZeroEps"] = str(n_zero)
    chk.append(("flipped-minus-held dConf, within pair", f"{p_all:+.1f}", "+15.9"))
    chk.append(("  same, conf_pre==0 dropped", f"{p_nz:+.1f}", "+9.4"))
    chk.append(("conf_pre == 0 episodes", str(n_zero), "97"))

    # high-confidence band, where the sign reverses
    band = [r for r in scored if r["arm"] in CHALLENGE_ARMS
            and r.get("conf_pre") is not None and 85 <= r["conf_pre"] <= 100]
    for name, pred in (("Flip", flipped), ("Held", held)):
        v = [dconf(r) for r in band if pred(r) and dconf(r) is not None]
        m[f"pqBand{name}"] = num(float(np.mean(v)))
        chk.append((f"conf_pre 85-100 band, {name.lower()}", f"{np.mean(v):+.1f}",
                    "-11.4 (flipped) / -8.7 (held)"))

    # control degeneracy and scale lumpiness
    ctl = [r for r in scored if r["arm"] == "control" and dconf(r) is not None]
    m["pqCtlZero"] = str(sum(1 for r in ctl if dconf(r) == 0))
    m["pqCtlScored"] = str(len(ctl))
    chk.append(("control dConf == 0",
                f"{sum(1 for r in ctl if dconf(r)==0)}/{len(ctl)}", "371/372"))
    # differential missingness on the confidence item, reported in the Limitations
    for arm, key in (("control", "Ctl"), ("reason_elicitation", "Reason")):
        s_arm = [r for r in rows if r["arm"] == arm]
        m[f"pqNA{key}"] = num(
            100 * sum(1 for r in s_arm if r.get("conf_post_kind") != "value") / len(s_arm))

    cp = Counter(r["conf_pre"] for r in scored if r.get("conf_pre") is not None)
    for val, key in ((100, "Hundred"), (0, "Zero"), (70, "Seventy")):
        m[f"pqConfPre{key}"] = str(cp.get(val, 0))
    m["pqNEpisodes"] = str(len(rows))
    chk.append(("conf_pre 100 / 0 / 70 counts",
                f"{cp.get(100)} / {cp.get(0)} / {cp.get(70)}", "321 / 97 / 292"))

    # ---------------- write ----------------
    header = ("% GENERATED by analysis/persistence_paper_stats.py — do not hand-edit.\n"
              "% Source: data/persistence/persistence_deepseek_k3.jsonl (1,560 episodes).\n")
    body = "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in sorted(m.items()))
    OUT.write_text(header + body)
    print(f"wrote {OUT.relative_to(ROOT)}  ({len(m)} macros)")

    if args.check:
        print("\nCHECK — computed vs. the value supplied for the paper")
        print("-" * 78)
        for label, got, claimed in chk:
            print(f"  {label:<52} {got:<22} claimed {claimed}")


if __name__ == "__main__":
    main()
