#!/usr/bin/env python3
"""Preference-persistence analysis — PQ1-PQ4 (DEVIATIONS #5, EXPLORATORY).

    PQ1  retention rate by arm
    PQ2  retention against the pilot consistency covariate
    PQ3  Delta-confidence (conf_post - conf_pre) by arm
    PQ4  PQ1 and PQ3 broken out by domain

PQ, not RQ. prereg-v1 has its own RQ1-RQ4 — persuasive pressure, battery valence,
exit rate — which are a DIFFERENT study and remain UNRUN. The two sets share nothing
but the shape of their numbering, so the persistence set is lettered separately and
prereg-v1's numbering is left alone.

Every estimate ships with a bootstrap 95% CI, 10,000 resamples, resampled OVER PAIRS
(cluster bootstrap): the 12 episodes of a pair share its options and its position
behaviour, so resampling episodes would treat correlated observations as independent
and report an interval that is too narrow.

Underpowered cells are reported as "no measurable difference in this sample", never
as "no effect" (CLAUDE.md).

Refusals and unparsed responses are reported as rates, never dropped silently and
never imputed — a missing Delta-confidence is a missing value, not a zero.

    python analysis/persistence_analysis.py data/persistence/persistence_deepseek_k3.jsonl
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.schema import validate_persistence_file  # noqa: E402

N_BOOT = 10_000
SEED = 20260815
ARMS = ("control", "reason_elicitation", "self_critique", "counter_consideration")
MIN_CELL = 15          # below this a cell is reported as underpowered, per CLAUDE.md

UNDERPOWERED = "no measurable difference in this sample"


def cluster_bootstrap(by_pair: dict[str, list[float]], n_boot: int = N_BOOT,
                      seed: int = SEED) -> tuple[float | None, float | None, float | None, int, int]:
    """(point, lo, hi, n_pairs, n_obs) for the mean of a quantity, resampling PAIRS.

    Pairs are drawn with replacement; every observation of a drawn pair comes with it.
    Returns Nones when there is nothing to estimate rather than a fabricated interval.
    """
    pairs = [p for p, v in by_pair.items() if v]
    n_obs = sum(len(by_pair[p]) for p in pairs)
    if not pairs or n_obs == 0:
        return None, None, None, len(pairs), n_obs
    point = float(np.mean([x for p in pairs for x in by_pair[p]]))
    rng = np.random.default_rng(seed)
    vals = [np.asarray(by_pair[p], dtype=float) for p in pairs]
    idx = rng.integers(0, len(pairs), size=(n_boot, len(pairs)))
    means = np.empty(n_boot)
    for b in range(n_boot):
        draw = np.concatenate([vals[i] for i in idx[b]])
        means[b] = draw.mean()
    lo, hi = np.percentile(means, [2.5, 97.5])
    return point, float(lo), float(hi), len(pairs), n_obs


def group(rows: list[dict], key, value) -> dict[str, list[float]]:
    """{pair_id: [value(r), ...]} over rows where value(r) is not None."""
    out: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        if key(r):
            v = value(r)
            if v is not None:
                out[r["pair_id"]].append(float(v))
    return out


def fmt(point, lo, hi, n_pairs, n_obs, pct: bool = False) -> str:
    if point is None:
        return f"{'--':>8}  {'':>18}  n=0"
    scale = 100 if pct else 1
    unit = "%" if pct else ""
    flag = "  <- UNDERPOWERED" if n_obs < MIN_CELL else ""
    return (f"{point * scale:8.1f}{unit}  [{lo * scale:6.1f}, {hi * scale:6.1f}]  "
            f"n={n_obs} ({n_pairs} pairs){flag}")


def section(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1
                else ROOT / "data/persistence/persistence_deepseek_k3.jsonl").resolve()
    rel = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
    n_valid = validate_persistence_file(path)      # hard fail before anything is read
    rows = [json.loads(x) for x in path.read_text().splitlines() if '"episode_id"' in x]
    meta = json.loads(path.read_text().splitlines()[0])

    print("=" * 78)
    print("PREFERENCE PERSISTENCE — EXPLORATORY (DEVIATIONS #5)")
    print(f"  file            {rel}")
    print(f"  model           {meta.get('model')}   reasoning {meta.get('reasoning')}")
    print(f"  episodes        {len(rows)}   schema-valid {n_valid}")
    print(f"  bootstrap       {N_BOOT:,} resamples over PAIRS (cluster), seed {SEED}")
    print("=" * 78)

    # --- coverage: refusals and unparsed are data ----------------------------
    section("COVERAGE — refusals and unparsed responses (never dropped silently)")
    print(f"  {'arm':<24} {'N':>4} {'refuse_pre':>11} {'unparsed_pre':>13} "
          f"{'refuse_post':>12} {'unparsed_post':>14} {'conf_post_NA':>13}")
    for arm in ARMS:
        s = [r for r in rows if r["arm"] == arm]
        if not s:
            continue
        rp = sum(1 for r in s if r.get("kind_pre") == "refusal")
        up = sum(1 for r in s if r.get("kind_pre") == "unparsed")
        ro = sum(1 for r in s if r.get("kind_post") == "refusal")
        uo = sum(1 for r in s if r.get("kind_post") == "unparsed")
        cn = sum(1 for r in s if r.get("conf_post_kind") != "value")
        n = len(s)
        print(f"  {arm:<24} {n:>4} {rp:>6} {rp/n:>5.1%} {up:>6} {up/n:>6.1%} "
              f"{ro:>5} {ro/n:>6.1%} {uo:>6} {uo/n:>7.1%} {cn:>6} {cn/n:>6.1%}")

    err = [r for r in rows if r.get("status") == "error"]
    if err:
        print(f"\n  {len(err)} episode(s) errored and are logged, not imputed. "
              f"Example: {err[0].get('error', '')[:100]}")

    # Per pair x arm refusal log, written out in full (the console shows the worst).
    ref_log = {}
    for r in rows:
        k = f"{r['pair_id']}|{r['arm']}"
        d = ref_log.setdefault(k, {"n": 0, "refusal_pre": 0, "refusal_post": 0,
                                   "unparsed_pre": 0, "unparsed_post": 0})
        d["n"] += 1
        for side in ("pre", "post"):
            if r.get(f"kind_{side}") == "refusal":
                d[f"refusal_{side}"] += 1
            elif r.get(f"kind_{side}") == "unparsed":
                d[f"unparsed_{side}"] += 1
    out_ref = path.with_name(path.stem + "_refusals.json")
    out_ref.write_text(json.dumps(ref_log, indent=1))
    worst = sorted(ref_log.items(),
                   key=lambda kv: -(kv[1]["refusal_pre"] + kv[1]["refusal_post"]))[:5]
    if worst and worst[0][1]["refusal_pre"] + worst[0][1]["refusal_post"] > 0:
        print("\n  worst pair x arm cells by refusal count:")
        for k, v in worst:
            if v["refusal_pre"] + v["refusal_post"]:
                print(f"    {k:<58} pre {v['refusal_pre']}/{v['n']} post {v['refusal_post']}/{v['n']}")
    print(f"\n  full pair x arm refusal log -> {out_ref.name}")

    scored = [r for r in rows if r.get("retained") is not None]
    dconf = lambda r: (None if r.get("conf_pre") is None or r.get("conf_post") is None
                       else r["conf_post"] - r["conf_pre"])

    # --- PQ1 -----------------------------------------------------------------
    section("PQ1 — retention rate by arm  (retained = same option after the challenge)")
    ret_by_arm = {}
    for arm in ARMS:
        g = group(scored, lambda r, a=arm: r["arm"] == a, lambda r: r["retained"])
        ret_by_arm[arm] = cluster_bootstrap(g)
        print(f"  {arm:<24} {fmt(*ret_by_arm[arm], pct=True)}")

    section("PQ1 — contrast vs. control (arm minus control, paired within pair)")
    ctrl = group(scored, lambda r: r["arm"] == "control", lambda r: r["retained"])
    for arm in ARMS[1:]:
        g = group(scored, lambda r, a=arm: r["arm"] == a, lambda r: r["retained"])
        shared = sorted(set(g) & set(ctrl))
        diff = {p: [float(np.mean(g[p]) - np.mean(ctrl[p]))] for p in shared}
        print(f"  {arm + ' - control':<24} {fmt(*cluster_bootstrap(diff), pct=True)}")

    # --- PQ3 -----------------------------------------------------------------
    section("PQ3 — Delta-confidence (conf_post - conf_pre) by arm, 0-100 scale")
    for arm in ARMS:
        g = group(scored, lambda r, a=arm: r["arm"] == a, dconf)
        print(f"  {arm:<24} {fmt(*cluster_bootstrap(g))}")

    section("PQ3 — contrast vs. control (paired within pair)")
    cctrl = group(scored, lambda r: r["arm"] == "control", dconf)
    for arm in ARMS[1:]:
        g = group(scored, lambda r, a=arm: r["arm"] == a, dconf)
        shared = sorted(set(g) & set(cctrl))
        diff = {p: [float(np.mean(g[p]) - np.mean(cctrl[p]))] for p in shared}
        print(f"  {arm + ' - control':<24} {fmt(*cluster_bootstrap(diff))}")

    # --- PQ2 -----------------------------------------------------------------
    section("PQ2 — retention against pilot consistency (per-pair covariate, not re-elicited)")
    levels = sorted({r["pilot_consistency"] for r in scored
                     if r["pilot_consistency"] is not None})
    print(f"  covariate levels present: {levels}")
    print("  (k=5 in the balance pilot quantises consistency to 1.0 / 0.8 / 0.6 — the")
    print("   predictor has three levels, not a continuum. Stated, not papered over.)")
    print()
    print(f"  {'consistency':<14} {'arm':<24} retention")
    for lev in levels:
        for arm in ARMS:
            g = group(scored,
                      lambda r, a=arm, L=lev: r["arm"] == a and r["pilot_consistency"] == L,
                      lambda r: r["retained"])
            res = cluster_bootstrap(g)
            print(f"  {lev:<14.1f} {arm:<24} {fmt(*res, pct=True)}")
        print()
    print("  pooled over arms:")
    for lev in levels:
        g = group(scored, lambda r, L=lev: r["pilot_consistency"] == L,
                  lambda r: r["retained"])
        print(f"  {lev:<14.1f} {'(all arms)':<24} {fmt(*cluster_bootstrap(g), pct=True)}")

    # Slope: per-pair retention regressed on consistency, bootstrapped over pairs.
    section("PQ2 — slope of retention on pilot consistency (per pair, cluster bootstrap)")
    per_pair = defaultdict(list)
    cons = {}
    for r in scored:
        if r["pilot_consistency"] is not None:
            per_pair[r["pair_id"]].append(r["retained"])
            cons[r["pair_id"]] = r["pilot_consistency"]
    pids = sorted(per_pair)
    x = np.array([cons[p] for p in pids])
    y = np.array([np.mean(per_pair[p]) for p in pids])
    if len(set(x.tolist())) < 2:
        print(f"  covariate has one level in this sample — {UNDERPOWERED}.")
    else:
        rng = np.random.default_rng(SEED)
        slope = float(np.polyfit(x, y, 1)[0])
        boots = []
        for _ in range(N_BOOT):
            i = rng.integers(0, len(pids), len(pids))
            if len(set(x[i].tolist())) < 2:
                continue
            boots.append(np.polyfit(x[i], y[i], 1)[0])
        lo, hi = np.percentile(boots, [2.5, 97.5])
        print(f"  slope  {slope:+.3f} retention per unit consistency  [{lo:+.3f}, {hi:+.3f}]"
              f"   ({len(pids)} pairs)")
        if lo <= 0 <= hi:
            print(f"  interval spans zero — {UNDERPOWERED}.")

    # --- PQ4 -----------------------------------------------------------------
    section("PQ4 — by domain")
    domains = sorted({r["domain"] for r in scored})
    for dom in domains:
        n_dom = sum(1 for r in scored if r["domain"] == dom)
        print(f"\n  {dom}  (N={n_dom})")
        print(f"    {'arm':<24} {'retention':<44} Delta-confidence")
        for arm in ARMS:
            sel = lambda r, a=arm, d=dom: r["arm"] == a and r["domain"] == d
            ret = cluster_bootstrap(group(scored, sel, lambda r: r["retained"]))
            dc = cluster_bootstrap(group(scored, sel, dconf))
            print(f"    {arm:<24} {fmt(*ret, pct=True):<44} {fmt(*dc)}")

    print()
    print("=" * 78)
    print("All estimates above are EXPLORATORY (DEVIATIONS #5): the run was executed")
    print("after pilot data was seen and the pool is unfiltered. Nothing here may be")
    print("reported as confirmatory. Cells marked UNDERPOWERED are described as")
    print(f'"{UNDERPOWERED}" — never as "no effect".')
    print("=" * 78)


if __name__ == "__main__":
    main()
