#!/usr/bin/env python3
"""Preference-persistence analysis — PQ1-PQ4 (DEVIATIONS #6/#8, EXPLORATORY).

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

    python analysis/persistence_analysis.py data/persistence/persistence_deepseek_ext.jsonl
    python analysis/persistence_analysis.py --sets     # preference domains beside the bias split

The reported study is the five-domain set of DEVIATIONS #6/#8: four preference domains
plus `finances_control`. The original four domains and their pool were retired from the
repository under DEVIATIONS #8 and are not analysed here. Two rules govern --sets:

  * `finances_control` is a POSITIVE CONTROL, not a domain. It is a monotonic money
    ladder, so ceiling retention there is the expected and correct result. It is
    reported in its own block as a manipulation check and is NEVER pooled into a PQ
    estimate. The preference-domain column is therefore FOUR domains, not five.
  * Estimates are reported twice, with and without pairs whose pilot position bias
    is >= 0.5. Sports returned a mean of 0.600 with reasoning on, so part of its
    apparent wavering is slot-driven. No pair is dropped from collection for this -
    dropping after seeing the pilot would be outcome-dependent selection - so the
    split is made here, at analysis time, and both columns are shown.
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

# --- domain sets (DEVIATIONS #6, scope fixed by #8) ---------------------------
EXTENSION_DOMAINS = ("video_games", "sports", "pop_culture", "sci_tech")
# Not a domain. A monotonic money ladder used as a manipulation check; ceiling
# retention here is the expected, correct result. Never enters a PQ estimate.
POSITIVE_CONTROL = "finances_control"
BIAS_CUTOFF = 0.5      # pilot position bias at or above this is slot-driven enough to split on

EXT_FILE = "data/persistence/persistence_deepseek_ext.jsonl"


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


CELL_W = 34      # every cell pads to this, so side-by-side columns line up
LABEL_W = 32     # "counter_consideration - control" is 31 characters


def short(point, lo, hi, n_pairs, n_obs, pct: bool = False) -> str:
    """Compact fixed-width estimate for side-by-side columns: point [lo, hi] n/pairs."""
    if point is None or n_obs == 0:
        return f"{'--':^{CELL_W}}"
    s = 100 if pct else 1
    flag = "*" if n_obs < MIN_CELL else ""
    body = f"{point * s:6.1f} [{lo * s:6.1f},{hi * s:6.1f}] {n_obs:>4}/{n_pairs}{flag}"
    return f"{body:<{CELL_W}}"


def hdr_row(cols, label: str = "arm") -> str:
    return f"  {label:<{LABEL_W}}" + "".join(f"{c[0]:<{CELL_W}}" for c in cols)


def dconf_of(r: dict):
    if r.get("conf_pre") is None or r.get("conf_post") is None:
        return None
    return r["conf_post"] - r["conf_pre"]


def load_run(path: Path) -> tuple[list[dict], dict]:
    n_valid = validate_persistence_file(path)      # hard fail before anything is read
    lines = path.read_text().splitlines()
    rows = [json.loads(x) for x in lines if '"episode_id"' in x]
    meta = json.loads(lines[0])
    meta["_n_valid"] = n_valid
    return rows, meta


def sets_main() -> None:
    """PQ1-PQ4 over the four preference domains, beside the bias-restricted set."""
    ext_path = ROOT / EXT_FILE
    if not ext_path.exists():
        raise SystemExit(f"missing run file: {ext_path.relative_to(ROOT)}")
    ext_rows, ext_meta = load_run(ext_path)
    rows = ext_rows
    scored = [r for r in rows if r.get("retained") is not None]

    def in_set(r, doms):
        return r["domain"] in doms

    def low_bias(r):
        b = r.get("pilot_position_bias")
        return b is not None and b < BIAS_CUTOFF

    # Column definitions. finances_control appears in NO pooled column.
    COLS = [
        ("preference 4", lambda r: in_set(r, EXTENSION_DOMAINS)),
        ("bias<0.5", lambda r: in_set(r, EXTENSION_DOMAINS) and low_bias(r)),
    ]

    print("=" * 110)
    print("PREFERENCE PERSISTENCE — EXPLORATORY (DEVIATIONS #6 + #8)")
    print(f"  run             {ext_path.relative_to(ROOT)}")
    print(f"                  {len(ext_rows)} episodes, schema-valid {ext_meta['_n_valid']}, "
          f"model {ext_meta.get('model')}, reasoning {ext_meta.get('reasoning')}")
    print(f"  bootstrap       {N_BOOT:,} resamples over PAIRS (cluster), seed {SEED}")
    print(f"  cells marked *  n < {MIN_CELL}: \"{UNDERPOWERED}\"")
    print("=" * 110)

    print("\nDOMAIN SETS")
    print(f"  preference 4   {', '.join(EXTENSION_DOMAINS)}")
    print(f"                 {POSITIVE_CONTROL} is a positive control and is held out of")
    print(f"                 every pooled estimate, reported separately below.")
    print(f"  bias<0.5       preference 4, excluding pairs with pilot position bias >= "
          f"{BIAS_CUTOFF}")
    ctrl_rows = [r for r in scored if r["domain"] == POSITIVE_CONTROL]
    nb = sum(1 for r in scored if in_set(r, EXTENSION_DOMAINS)
             and r.get("pilot_position_bias") is None)
    drop = {p for r in scored if in_set(r, EXTENSION_DOMAINS) and not low_bias(r)
            for p in [r["pair_id"]]}
    print(f"\n  pairs excluded at bias >= {BIAS_CUTOFF}: {len(drop)}"
          f"   (pairs with no bias recorded: {nb} episodes)")
    print(f"  {POSITIVE_CONTROL} episodes held out of all pooled columns: {len(ctrl_rows)}")

    hdr = hdr_row(COLS)

    # --- PQ1 ------------------------------------------------------------------
    section("PQ1 — retention rate by arm (%)")
    print(hdr)
    for arm in ARMS:
        line = f"  {arm:<32}"
        for _, sel in COLS:
            g = group(scored, lambda r, a=arm, s=sel: r["arm"] == a and s(r),
                      lambda r: r["retained"])
            line += short(*cluster_bootstrap(g), pct=True)
        print(line)

    section("PQ1 — contrast vs. control (arm minus control, paired within pair, pp)")
    print(hdr)
    for arm in ARMS[1:]:
        line = f"  {arm + ' - control':<32}"
        for _, sel in COLS:
            g = group(scored, lambda r, a=arm, s=sel: r["arm"] == a and s(r),
                      lambda r: r["retained"])
            c = group(scored, lambda r, s=sel: r["arm"] == "control" and s(r),
                      lambda r: r["retained"])
            shared = sorted(set(g) & set(c))
            diff = {p: [float(np.mean(g[p]) - np.mean(c[p]))] for p in shared}
            line += short(*cluster_bootstrap(diff), pct=True)
        print(line)

    # --- PQ3 ------------------------------------------------------------------
    section("PQ3 — Delta-confidence (conf_post - conf_pre) by arm, 0-100 scale")
    print(hdr)
    for arm in ARMS:
        line = f"  {arm:<32}"
        for _, sel in COLS:
            g = group(scored, lambda r, a=arm, s=sel: r["arm"] == a and s(r), dconf_of)
            line += short(*cluster_bootstrap(g))
        print(line)

    section("PQ3 — contrast vs. control (paired within pair)")
    print(hdr)
    for arm in ARMS[1:]:
        line = f"  {arm + ' - control':<32}"
        for _, sel in COLS:
            g = group(scored, lambda r, a=arm, s=sel: r["arm"] == a and s(r), dconf_of)
            c = group(scored, lambda r, s=sel: r["arm"] == "control" and s(r), dconf_of)
            shared = sorted(set(g) & set(c))
            diff = {p: [float(np.mean(g[p]) - np.mean(c[p]))] for p in shared}
            line += short(*cluster_bootstrap(diff))
        print(line)

    # --- PQ2 ------------------------------------------------------------------
    section("PQ2 — retention by pilot consistency level (pooled over arms, %)")
    levels = sorted({r["pilot_consistency"] for r in scored
                     if r.get("pilot_consistency") is not None})
    print(f"  covariate levels present: {levels}")
    print(hdr_row(COLS, "consistency"))
    for lev in levels:
        line = f"  {lev:<32.1f}"
        for _, sel in COLS:
            g = group(scored, lambda r, L=lev, s=sel: r.get("pilot_consistency") == L and s(r),
                      lambda r: r["retained"])
            line += short(*cluster_bootstrap(g), pct=True)
        print(line)

    section("PQ2 — slope of per-pair retention on pilot consistency")
    for name, sel in COLS:
        per_pair, cons = defaultdict(list), {}
        for r in scored:
            if sel(r) and r.get("pilot_consistency") is not None:
                per_pair[r["pair_id"]].append(r["retained"])
                cons[r["pair_id"]] = r["pilot_consistency"]
        pids = sorted(per_pair)
        x = np.array([cons[p] for p in pids], dtype=float)
        y = np.array([np.mean(per_pair[p]) for p in pids], dtype=float)
        if len(pids) < 3 or len(set(x.tolist())) < 2:
            print(f"  {name:<16} covariate has one level in this sample — {UNDERPOWERED}.")
            continue
        rng = np.random.default_rng(SEED)
        slope = float(np.polyfit(x, y, 1)[0])
        boots = []
        for _ in range(N_BOOT):
            i = rng.integers(0, len(pids), len(pids))
            if len(set(x[i].tolist())) < 2:
                continue
            boots.append(np.polyfit(x[i], y[i], 1)[0])
        lo, hi = np.percentile(boots, [2.5, 97.5])
        span = "   interval spans zero — " + UNDERPOWERED if lo <= 0 <= hi else ""
        print(f"  {name:<16} slope {slope:+.3f}  [{lo:+.3f}, {hi:+.3f}]  "
              f"({len(pids)} pairs){span}")

    # --- PQ4 ------------------------------------------------------------------
    section("PQ4 — retention and Delta-confidence by domain (all arms pooled)")
    print(f"  {'domain':<18} {'retention %':<26} {'Delta-confidence':<26} "
          f"{'mean pilot pos.bias':>19}")
    for dom in EXTENSION_DOMAINS:
        sel = lambda r, d=dom: r["domain"] == d
        ret = cluster_bootstrap(group(scored, sel, lambda r: r["retained"]))
        dc = cluster_bootstrap(group(scored, sel, dconf_of))
        bs = [r["pilot_position_bias"] for r in scored
              if r["domain"] == dom and r.get("pilot_position_bias") is not None]
        mb = f"{np.mean(bs):.3f}" if bs else "--"
        print(f"  {dom:<18} {short(*ret, pct=True):<26} {short(*dc):<26} {mb:>19}")

    section("PQ4 — retention by arm, preference domains")
    print(f"  {'domain':<32}" + "".join(f"{a[:18]:<20}" for a in ARMS))
    for dom in EXTENSION_DOMAINS:
        line = f"  {dom:<32}"
        for arm in ARMS:
            g = group(scored, lambda r, d=dom, a=arm: r["domain"] == d and r["arm"] == a,
                      lambda r: r["retained"])
            p, lo, hi, npr, nob = cluster_bootstrap(g)
            line += (f"{'--':<20}" if p is None
                     else f"{p * 100:5.1f}% ({nob:>3}){'*' if nob < MIN_CELL else ' '}     ")
        print(line)

    # --- positive control, reported separately --------------------------------
    section(f"MANIPULATION CHECK — {POSITIVE_CONTROL} (NOT pooled into any PQ estimate)")
    print("  A monotonic ladder of receive-$X / owe-$X outcomes. A forced choice between")
    print("  two rungs is arithmetic, not preference, so CEILING RETENTION HERE IS THE")
    print("  EXPECTED, CORRECT RESULT. Wavering here would indicate the elicitation, not")
    print("  the preference, is unstable (CLAUDE.md: stop and tell the human).")
    print()
    print(f"  {'arm':<24} {'retention %':<28} {'Delta-confidence':<28}")
    for arm in ARMS:
        sel = lambda r, a=arm: r["domain"] == POSITIVE_CONTROL and r["arm"] == a
        ret = cluster_bootstrap(group(scored, sel, lambda r: r["retained"]))
        dc = cluster_bootstrap(group(scored, sel, dconf_of))
        print(f"  {arm:<24} {short(*ret, pct=True):<28} {short(*dc):<28}")
    allc = cluster_bootstrap(group(scored, lambda r: r["domain"] == POSITIVE_CONTROL,
                                   lambda r: r["retained"]))
    print(f"  {'(all arms)':<24} {short(*allc, pct=True):<28}")
    if allc[0] is not None:
        verdict = ("PASS — at or near ceiling, as designed" if allc[0] >= 0.95 else
                   "** BELOW CEILING — the instrument may be unstable; report to the human")
        print(f"\n  verdict: {verdict}")

    # --- coverage -------------------------------------------------------------
    section("COVERAGE — refusals and unparsed are data, never dropped, never imputed")
    print(f"  {'run':<12} {'arm':<24} {'N':>5} {'refuse_pre':>11} {'refuse_post':>12} "
          f"{'conf_post_NA':>13}")
    for name, rs in (("extension", ext_rows),):
        for arm in ARMS:
            s = [r for r in rs if r["arm"] == arm]
            if not s:
                continue
            rp = sum(1 for r in s if r.get("kind_pre") == "refusal")
            ro = sum(1 for r in s if r.get("kind_post") == "refusal")
            cn = sum(1 for r in s if r.get("conf_post_kind") != "value")
            n = len(s)
            print(f"  {name:<12} {arm:<24} {n:>5} {rp:>5} {rp / n:>5.1%} "
                  f"{ro:>6} {ro / n:>5.1%} {cn:>6} {cn / n:>6.1%}")
        na = {a: (sum(1 for r in rs if r["arm"] == a and r.get("conf_post_kind") != "value")
                  / max(1, sum(1 for r in rs if r["arm"] == a))) for a in ARMS}
        if na and (max(na.values()) - min(na.values())) > 0.02:
            hi_a, lo_a = max(na, key=na.get), min(na, key=na.get)
            print(f"    ** DIFFERENTIAL MISSINGNESS on conf_post ({name}): {hi_a} "
                  f"{na[hi_a]:.1%} vs {lo_a} {na[lo_a]:.1%}. PQ3 is a between-arm")
            print("       contrast, so this lands on it. Recorded as unparsed, NOT imputed.")

    print()
    print("=" * 110)
    print("EXPLORATORY (DEVIATIONS #6 and #8). The run was executed after pilot data")
    print("was seen and the pool is unfiltered. Nothing here may be reported as")
    print(f'confirmatory. Cells marked * have n < {MIN_CELL}: "{UNDERPOWERED}" — never')
    print(f'"no effect". {POSITIVE_CONTROL} is a manipulation check and is excluded from')
    print("every pooled PQ estimate above.")
    print("=" * 110)


def main() -> None:
    if "--sets" in sys.argv:
        return sets_main()
    path = Path(sys.argv[1] if len(sys.argv) > 1
                else ROOT / EXT_FILE).resolve()
    rel = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
    n_valid = validate_persistence_file(path)      # hard fail before anything is read
    rows = [json.loads(x) for x in path.read_text().splitlines() if '"episode_id"' in x]
    meta = json.loads(path.read_text().splitlines()[0])

    print("=" * 78)
    print("PREFERENCE PERSISTENCE — EXPLORATORY (DEVIATIONS #6)")
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

    # Missingness on the confidence item is only ignorable if it does not depend on
    # arm — and PQ3 is a between-arm contrast, so a differential rate is a threat to
    # it specifically. Checked and printed rather than assumed away.
    na_rate = {}
    for arm in ARMS:
        s = [r for r in rows if r["arm"] == arm]
        if s:
            na_rate[arm] = sum(1 for r in s if r.get("conf_post_kind") != "value") / len(s)
    if na_rate and (max(na_rate.values()) - min(na_rate.values())) > 0.02:
        hi = max(na_rate, key=na_rate.get)
        lo = min(na_rate, key=na_rate.get)
        print(f"\n  ** DIFFERENTIAL MISSINGNESS on conf_post: {hi} {na_rate[hi]:.1%} vs "
              f"{lo} {na_rate[lo]:.1%}.")
        print("     Missingness is NOT independent of arm, so the PQ3 between-arm")
        print("     contrast is affected. The missing values are recorded as unparsed")
        print("     and are NOT imputed; the rate is reported with the estimate.")

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
    print("All estimates above are EXPLORATORY (DEVIATIONS #6): the run was executed")
    print("after pilot data was seen and the pool is unfiltered. Nothing here may be")
    print("reported as confirmatory. Cells marked UNDERPOWERED are described as")
    print(f'"{UNDERPOWERED}" — never as "no effect".')
    print("=" * 78)


if __name__ == "__main__":
    main()
