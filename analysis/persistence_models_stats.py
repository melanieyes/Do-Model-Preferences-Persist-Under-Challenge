#!/usr/bin/env python3
"""Generate paper/persist_models_stats.tex — the CROSS-MODEL persistence numbers.

Third companion to persistence_paper_stats.py (original k3 run) and
persistence_ext_stats.py (five-domain extension). Same house rule
(.claude/skills/paper-style): every number in the text traces to analysis output;
none are typed. This script is the trace for the cross-model subsection, for the
gemini-3.5-flash appendix paragraph, and for the control-baseline sentence in
Limitations.

Macro prefix, one per target, so a number can never be quoted against the wrong model:

    pqmNano*    gpt-5.4-nano, the second family. Full coverage, so every PQ
                quantity is estimable and comparable to the deepseek-v4-pro
                estimates in persist_stats.tex.
    pqmGthree*  gemini-3.5-flash. OUTCOME-CONDITIONED and reported as such: only
                the pairs it agreed to answer reach the estimator, so its
                retention numbers are NOT comparable to the two above and are
                never plotted beside them. Coverage is the finding; the retention
                figures exist so the appendix can state what the surviving
                episodes look like, with the conditioning stated first.

deepseek-v4-pro is deliberately NOT re-emitted here. Its numbers already exist as
\\pq* macros in persist_stats.tex, and a second macro for the same quantity is a
second thing to drift.

    python analysis/persistence_models_stats.py [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis.persistence_analysis import ARMS, cluster_bootstrap, group  # noqa: E402

DATA = ROOT / "data" / "persistence"
OUT = ROOT / "paper" / "persist_models_stats.tex"

NANO = DATA / "persistence_nano_k3.jsonl"
GTHREE = DATA / "persistence_gemini35_k3.jsonl"

SHORT = {"control": "Ctl", "reason_elicitation": "Reason",
         "self_critique": "Critique", "counter_consideration": "Counter"}
CHALLENGE_ARMS = ("self_critique", "counter_consideration")


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


def num(x, d=1):
    return f"\\num{{{x:.{d}f}}}"


def arm_block(m: dict, pre: str, scored: list[dict], *, contrasts: bool) -> None:
    """Retention by arm, and (where the coverage supports it) the paired contrast."""
    for arm in ARMS:
        p, lo, hi, _, _ = cluster_bootstrap(
            group(scored, lambda r, a=arm: r["arm"] == a, lambda r: r["retained"]))
        if p is None:
            continue
        m[f"{pre}Ret{SHORT[arm]}"] = num(p * 100)
        m[f"{pre}Ret{SHORT[arm]}Lo"] = num(lo * 100)
        m[f"{pre}Ret{SHORT[arm]}Hi"] = num(hi * 100)
    if not contrasts:
        return
    for arm in ARMS[1:]:
        p, lo, hi, _, _ = paired_contrast(scored, arm, lambda r: r["retained"])
        if p is None:
            continue
        m[f"{pre}Diff{SHORT[arm]}"] = num(p * 100)
        m[f"{pre}Diff{SHORT[arm]}Lo"] = num(lo * 100)
        m[f"{pre}Diff{SHORT[arm]}Hi"] = num(hi * 100)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    m: dict[str, str] = {}
    chk: list[tuple[str, str]] = []

    # ---------------- gpt-5.4-nano: full coverage, everything estimable -------
    nano = load(NANO)
    nano_scored = [r for r in nano if r.get("retained") is not None]
    m["pqmNanoEps"] = str(len(nano))
    m["pqmNanoScored"] = str(len(nano_scored))
    m["pqmNanoPairs"] = str(len({r["pair_id"] for r in nano_scored}))
    arm_block(m, "pqmNano", nano_scored, contrasts=True)
    chk.append(("nano episodes scored", f"{len(nano_scored)} of {len(nano)}"))
    chk.append(("nano retention: ctl / reason / critique / counter",
                " / ".join(m[f"pqmNanoRet{SHORT[a]}"] for a in ARMS)))
    chk.append(("nano contrast vs control: reason / critique / counter",
                " / ".join(m[f"pqmNanoDiff{SHORT[a]}"] for a in ARMS[1:])))

    # Which challenge arm moves the choice more, on each target. This is the rank
    # swap the subsection turns on, so it is COMPUTED rather than read off a table.
    ds = load(DATA / "persistence_deepseek_k3.jsonl")
    ds_scored = [r for r in ds if r.get("retained") is not None]
    for tag, rs in (("Ds", ds_scored), ("Nano", nano_scored)):
        d = {}
        for arm in CHALLENGE_ARMS:
            p, *_ = paired_contrast(rs, arm, lambda r: r["retained"])
            d[arm] = p
        stronger = min(d, key=lambda a: d[a])          # most negative = moves most
        m[f"pqm{tag}StrongerArm"] = ("self\\_critique" if stronger == "self_critique"
                                     else "counter\\_consideration")
        m[f"pqm{tag}ArmGap"] = num(abs(d["self_critique"] - d["counter_consideration"]) * 100)
        chk.append((f"{tag}: arm that moves choices most / gap between the two",
                    f"{stronger} / {m[f'pqm{tag}ArmGap']} points"))

    # ---------------- the control baseline, deepseek against nano -------------
    # Limitations says the zero-variance control is a property of the deepseek
    # target rather than of the design; both halves of that claim are measured.
    for tag, rs in (("Ds", ds_scored), ("Nano", nano_scored)):
        ctl = [r for r in rs if r["arm"] == "control"]
        vals = [dconf(r) for r in ctl if dconf(r) is not None]
        m[f"pqm{tag}CtlScored"] = str(len(vals))
        m[f"pqm{tag}CtlNonzero"] = str(sum(1 for v in vals if v != 0))
        p, lo, hi, _, _ = cluster_bootstrap(group(ctl, lambda r: True, dconf))
        m[f"pqm{tag}CtlConf"] = num(p, 2)
        m[f"pqm{tag}CtlConfLo"] = num(lo, 2)
        m[f"pqm{tag}CtlConfHi"] = num(hi, 2)
        chk.append((f"{tag}: control episodes with nonzero dconf",
                    f"{m[f'pqm{tag}CtlNonzero']} of {m[f'pqm{tag}CtlScored']}; "
                    f"mean {m[f'pqm{tag}CtlConf']}"))

    # ---------------- gemini-3.5-flash: coverage first, always ----------------
    g3 = load(GTHREE)
    g3_scored = [r for r in g3 if r.get("retained") is not None]
    kinds = Counter(r["kind_pre"] for r in g3)
    m["pqmGthreeEps"] = str(len(g3))
    m["pqmGthreeScored"] = str(len(g3_scored))
    m["pqmGthreePairs"] = str(len({r["pair_id"] for r in g3_scored}))
    m["pqmGthreeRefusals"] = str(kinds["refusal"])
    m["pqmGthreeRefusalPct"] = num(100 * kinds["refusal"] / len(g3))
    m["pqmGthreeUnparsed"] = str(kinds["unparsed"])
    m["pqmGthreeUnparsedPct"] = num(100 * kinds["unparsed"] / len(g3))
    m["pqmGthreeScoredPct"] = num(100 * len(g3_scored) / len(g3))
    # Retention IS computed, but only so the appendix can say what the surviving
    # episodes look like. contrasts=False: a paired contrast over an
    # outcome-selected subset is the §5.4 estimate the paper refuses to report.
    arm_block(m, "pqmGthree", g3_scored, contrasts=False)
    chk.append(("gemini-3.5 initial elicitation: refusal / unparsed / choice",
                f"{kinds['refusal']} / {kinds['unparsed']} / {kinds['choice']} "
                f"of {len(g3)}"))
    chk.append(("gemini-3.5 episodes reaching both elicitations",
                f"{len(g3_scored)} of {len(g3)} "
                f"({m['pqmGthreeScoredPct']}%), {m['pqmGthreePairs']} of 130 pairs"))

    # ---------------- write ----------------
    header = (
        "% GENERATED by analysis/persistence_models_stats.py — do not hand-edit.\n"
        f"% Sources: {NANO.name} ({len(nano)} episodes), {GTHREE.name} "
        f"({len(g3)} episodes),\n"
        "%          persistence_deepseek_k3.jsonl (control-baseline comparison only).\n"
        "% pqmNano* full coverage, estimable. pqmGthree* OUTCOME-CONDITIONED —\n"
        "% coverage is the finding; its retention is never compared to the others.\n")
    body = "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in sorted(m.items()))
    OUT.write_text(header + body)
    print(f"wrote {OUT.relative_to(ROOT)}  ({len(m)} macros)")

    if args.check:
        print("\nCHECK — computed values")
        print("-" * 78)
        for label, got in chk:
            print(f"  {label:<52} {got}")


if __name__ == "__main__":
    main()
