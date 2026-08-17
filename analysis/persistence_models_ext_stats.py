#!/usr/bin/env python3
"""Generate paper/persist_models_ext_stats.tex — the cross-model numbers (DEVIATIONS #10).

Three targets, one protocol, one pool: the five-domain extension set. deepseek-v4-pro's
episodes come from the entry-#6 run; gpt-5.4-nano and gemini-2.5-flash ran the same 100
pairs in two batches each (finances_control under entry #9, the four preference domains
under entry #10) with the same seed, arms and per-pair order schedule, so the batches
merge at analysis time and are never re-run.

Macro prefix `xm` (cross-model, extension pool) — deliberately NOT `pqm`, which named
the retired original-pool comparison (DEVIATIONS #7/#8) and must stay retired.

    xmDs*    deepseek-v4-pro     xmNano*  gpt-5.4-nano     xmGtwo*  gemini-2.5-flash

Per model: preference-domain retention by arm with CIs, contrasts vs control,
held-episode confidence contrasts, coverage, and the finances_control check
(reported separately, never pooled).

    python analysis/persistence_models_ext_stats.py [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis.persistence_analysis import (  # noqa: E402
    ARMS, EXTENSION_DOMAINS, POSITIVE_CONTROL, cluster_bootstrap, group,
)
from analysis.persistence_ext_stats import dconf, paired_contrast  # noqa: E402

DATA = ROOT / "data" / "persistence"
OUT = ROOT / "paper" / "persist_models_ext_stats.tex"

SHORT = {"control": "Ctl", "reason_elicitation": "Reason",
         "self_critique": "Critique", "counter_consideration": "Counter"}

# (macro key, display name, episode files to merge)
TARGETS = [
    ("Ds", "deepseek-v4-pro", ["persistence_deepseek_ext.jsonl"]),
    ("Nano", "gpt-5.4-nano",
     ["persistence_nano_ext_finances_control.jsonl",
      "persistence_nano_ext_pop_culture-sci_tech-sports-video_games.jsonl"]),
    ("Gtwo", "gemini-2.5-flash",
     ["persistence_gemini25_ext_finances_control.jsonl",
      "persistence_gemini25_ext_pop_culture-sci_tech-sports-video_games.jsonl"]),
]


def load_merged(files: list[str]) -> list[dict]:
    rows: list[dict] = []
    for f in files:
        p = DATA / f
        if not p.exists():
            raise SystemExit(f"missing run file: {p.relative_to(ROOT)} — "
                             "collect it before generating cross-model stats")
        rows += [json.loads(x) for x in p.read_text().splitlines()
                 if '"episode_id"' in x]
    seen = {r["episode_id"] for r in rows}
    if len(seen) != len(rows):
        raise SystemExit("duplicate episode_ids across merged batches — "
                         "the same batch was collected twice; refusing to double-count")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    m: dict[str, str] = {}
    chk: list[tuple[str, str]] = []

    def num(x, d=1):
        return f"\\num{{{x:.{d}f}}}"

    stronger: dict[str, str] = {}
    for key, name, files in TARGETS:
        rows = load_merged(files)
        pref = [r for r in rows if r.get("retained") is not None
                and r["domain"] in EXTENSION_DOMAINS]
        fin = [r for r in rows if r.get("retained") is not None
               and r["domain"] == POSITIVE_CONTROL]
        n_ref = sum(1 for r in rows
                    if "refusal" in (r.get("kind_pre"), r.get("kind_post")))
        n_unp = sum(1 for r in rows
                    if "unparsed" in (r.get("kind_pre"), r.get("kind_post")))
        m[f"xm{key}Name"] = f"\\texttt{{{name}}}"
        m[f"xm{key}Eps"] = str(len(rows))
        m[f"xm{key}PrefEps"] = str(len(pref))
        m[f"xm{key}Refusals"] = str(n_ref)
        m[f"xm{key}Unparsed"] = str(n_unp)
        m[f"xm{key}Errors"] = str(sum(1 for r in rows if r.get("status") == "error"))

        for arm in ARMS:
            p, lo, hi, _, _ = cluster_bootstrap(
                group(pref, lambda r, a=arm: r["arm"] == a, lambda r: r["retained"]))
            if p is None:
                continue
            m[f"xm{key}Ret{SHORT[arm]}"] = num(p * 100)
            m[f"xm{key}Ret{SHORT[arm]}Lo"] = num(lo * 100)
            m[f"xm{key}Ret{SHORT[arm]}Hi"] = num(hi * 100)
        diffs = {}
        for arm in ARMS[1:]:
            p, lo, hi, _, _ = paired_contrast(pref, arm, lambda r: r["retained"])
            if p is not None:
                diffs[arm] = p
                m[f"xm{key}Diff{SHORT[arm]}"] = num(p * 100)
                m[f"xm{key}Diff{SHORT[arm]}Lo"] = num(lo * 100)
                m[f"xm{key}Diff{SHORT[arm]}Hi"] = num(hi * 100)

        held = [r for r in pref if r["retained"] is True]
        for arm in ARMS[1:]:
            p, lo, hi, npair, _ = paired_contrast(held, arm, dconf)
            if p is not None:
                m[f"xm{key}Held{SHORT[arm]}"] = num(p)
                m[f"xm{key}Held{SHORT[arm]}Lo"] = num(lo)
                m[f"xm{key}Held{SHORT[arm]}Hi"] = num(hi)

        # finances_control, separately, never pooled
        p, lo, hi, _, _ = cluster_bootstrap(
            group(fin, lambda r: True, lambda r: r["retained"]))
        m[f"xm{key}FinRet"] = num(p * 100)
        m[f"xm{key}FinRetLo"] = num(lo * 100)
        m[f"xm{key}FinRetHi"] = num(hi * 100)
        m[f"xm{key}FinFlips"] = str(sum(1 for r in fin if r["retained"] is False))

        if "self_critique" in diffs and "counter_consideration" in diffs:
            stronger[key] = ("critique"
                             if diffs["self_critique"] < diffs["counter_consideration"]
                             else "counter")
        chk.append((f"{name}: ret by arm (pref domains)",
                    " / ".join(m.get(f"xm{key}Ret{SHORT[a]}", "--") for a in ARMS)))
        chk.append((f"{name}: finance ret / flips",
                    f"{m[f'xm{key}FinRet']} / {m[f'xm{key}FinFlips']}"))

    m["xmNTargets"] = str(len(TARGETS))
    m["xmCritiqueWins"] = str(sum(1 for v in stronger.values() if v == "critique"))
    m["xmCounterWins"] = str(sum(1 for v in stronger.values() if v == "counter"))
    chk.append(("stronger adversarial arm per target", str(stronger)))

    header = (
        "% GENERATED by analysis/persistence_models_ext_stats.py — do not hand-edit.\n"
        "% Cross-model persistence on the five-domain extension pool (DEVIATIONS #9/#10).\n"
        "% xmDs deepseek-v4-pro | xmNano gpt-5.4-nano | xmGtwo gemini-2.5-flash.\n"
        "% Preference-domain estimates; Fin* macros are the positive control, never pooled.\n")
    body = "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in sorted(m.items()))
    OUT.write_text(header + body)
    print(f"wrote {OUT.relative_to(ROOT)}  ({len(m)} macros)")

    if args.check:
        print("\nCHECK — computed values")
        print("-" * 88)
        for label, got in chk:
            print(f"  {label:<52} {got}")


if __name__ == "__main__":
    main()
