#!/usr/bin/env python3
"""Cross-model manipulation check — finances_control only (DEVIATIONS #9, EXPLORATORY).

The money ladder is a POSITIVE CONTROL, not a domain: a forced choice between
two rungs is arithmetic, so ceiling retention is the expected, correct result
and nothing here is ever pooled into a PQ estimate. This script asks one
question per target: does the arithmetic ladder hold at ceiling on this model,
under the same four arms and the same five instrument controls?

Wavering here is not a preference result. On the primary target it would mean
the elicitation is broken (CLAUDE.md: stop and tell the human). On a further
target it is a property of that target's elicitation stability, reported as
such and never as retention-of-a-preference.

    python analysis/finance_check.py             # console comparison
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis.persistence_analysis import (  # noqa: E402
    ARMS, POSITIVE_CONTROL, cluster_bootstrap, group,
)

DATA = ROOT / "data" / "persistence"
CHALLENGE_ARMS = ("self_critique", "counter_consideration")

# (label, file, filter-to-finance?) — every target now has one five-domain file;
# the finance episodes are filtered out of each.
SOURCES = [
    ("deepseek-v4-pro", DATA / "persistence_deepseek_ext.jsonl", True),
    ("gpt-5.4-nano", DATA / "persistence_nano_ext.jsonl", True),
    ("gemini-2.5-flash", DATA / "persistence_gemini25_ext.jsonl", True),
]


def load(path: Path, finance_only: bool) -> list[dict]:
    rows = [json.loads(x) for x in path.read_text().splitlines() if '"episode_id"' in x]
    return [r for r in rows if r["domain"] == POSITIVE_CONTROL] if finance_only else rows


def pct(x):
    return "--" if x is None else f"{x * 100:5.1f}%"


def main() -> None:
    print("=" * 96)
    print("MANIPULATION CHECK, CROSS-MODEL — finances_control (EXPLORATORY, DEVIATIONS #9)")
    print("  Never pooled into any PQ estimate. Bootstrap 95% CIs over pairs, 10,000 resamples.")
    print("=" * 96)
    for name, path, fin_only in SOURCES:
        if not path.exists():
            print(f"\n{name}: {path.name} not collected yet — skipped")
            continue
        rows = load(path, fin_only)
        scored = [r for r in rows if r.get("retained") is not None]
        n_ref = sum(1 for r in rows if "refusal" in (r.get("kind_pre"), r.get("kind_post")))
        n_unp = sum(1 for r in rows if "unparsed" in (r.get("kind_pre"), r.get("kind_post")))
        print(f"\n{name}  —  {len(rows)} episodes, {len(scored)} scored, "
              f"{n_ref} refusal / {n_unp} unparsed (data, not dropped)")
        p, lo, hi, npair, nobs = cluster_bootstrap(
            group(scored, lambda r: True, lambda r: r["retained"]))
        print(f"  retention, all arms     {pct(p)}  [{pct(lo).strip()}, {pct(hi).strip()}]"
              f"  ({nobs} eps, {npair} pairs)")
        for arm in ARMS:
            pa, la, ha, _, na = cluster_bootstrap(group(
                scored, lambda r, a=arm: r["arm"] == a, lambda r: r["retained"]))
            print(f"    {arm:<24}{pct(pa)}  [{pct(la).strip()}, {pct(ha).strip()}]  n={na}")
        flips = [r for r in scored if r["retained"] is False]
        ch = sum(1 for r in scored if r["arm"] in CHALLENGE_ARMS)
        ch_flips = sum(1 for r in flips if r["arm"] in CHALLENGE_ARMS)
        print(f"  flips: {len(flips)} total; {ch_flips} in {ch} challenge episodes")
        if flips:
            print("  flipped episodes (the ladder MOVED — elicitation instability on this target):")
            for r in flips[:8]:
                print(f"    {r['arm']:<22} {r['pair_id'][-3:]}  "
                      f"{r['choice_pre']}->{r['choice_post']}  "
                      f"conf {r.get('conf_pre')}->{r.get('conf_post')}")
        verdict = ("PASS — at or near ceiling, as designed" if p is not None and p >= 0.95
                   else "** BELOW CEILING — elicitation unstable on this target; "
                        "report as an instrument property, never as preference movement")
        print(f"  verdict: {verdict}")
    print()
    print("=" * 96)
    print("EXPLORATORY. finances_control is a manipulation check; wavering on a further")
    print("target is that target's elicitation instability, not a preference finding.")
    print("=" * 96)


if __name__ == "__main__":
    main()
