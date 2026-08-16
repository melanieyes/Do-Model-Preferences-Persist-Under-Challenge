#!/usr/bin/env python3
"""Stage 3 — apply the balance filter and write the freeze candidate.

Reads the pilot, applies a fixed rule, writes the decision for EVERY piloted pair
back into data/pairs/balance_pilot.jsonl, and emits the surviving pairs to
data/pairs/pairs_frozen.jsonl.

Selection is on the measure, never on the content: no pair is read and judged by
hand. Every pair the pilot saw carries its decision and the numbers behind it.

Run:  python scripts/freeze_pairs.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pair_scope import SETTLED_DOMAINS  # noqa: E402

PAIRS_DIR = ROOT / "data" / "pairs"
PILOT = PAIRS_DIR / "balance_pilot.jsonl"
POOL = PAIRS_DIR / "pilot_pool.jsonl"
OUT = PAIRS_DIR / "pairs_frozen.jsonl"

# --- the rule -------------------------------------------------------------
# The measure is the DISCRETE k=5 split, not the logprob. With reasoning enabled
# the answer token's probability saturates near 1 — the model commits inside its
# reasoning and then states the answer — so the logprob reports confidence within
# one trace, not how often the model would land elsewhere on a fresh one. Only
# resampling shows that.
#
# KEEP_MIN mirrors the methods owner's 30/70 window. With k=5 the minority
# fraction can only be 0, 0.2 or 0.4, so this threshold resolves to "wavered at
# least twice"; the instrument cannot separate 70/30 from 85/15, and the 85/15
# ceiling rule is subsumed by it. Stated plainly rather than papered over.
KEEP_MIN = 0.30

# A pair the model answers by SLOT is not measuring preference. Under the 3/2
# counterbalanced schedule a content-driven consistent answer yields
# slot_a_frac in {0.4, 0.6}; picking the same slot 4 or 5 times out of 5 lands
# outside this band.
SLOT_BAND = (0.20, 0.80)

EXPECTED_PAIRS = 130   # guard: refuse to run against a partial pilot
TARGET_PER_DOMAIN = 8
MIN_PER_DOMAIN = 6


def decide(rec: dict) -> tuple[str, str]:
    valid = rec["n_a"] + rec["n_b"]
    if not valid:
        return "drop", "no parseable choice"
    minority = min(rec["n_a"], rec["n_b"]) / valid
    slot = rec.get("slot_a_frac")
    if slot is not None and not (SLOT_BAND[0] <= slot <= SLOT_BAND[1]):
        return "drop", f"position-driven (chose the same slot, slot_a_frac {slot:.2f})"
    if minority == 0:
        return "drop", f"ceiling ({rec['split']}, never wavered)"
    if minority < KEEP_MIN:
        return "drop", f"near-ceiling ({rec['split']}, wavered once)"
    return "keep", f"wavered ({rec['split']})"


def main() -> None:
    lines = [json.loads(x) for x in PILOT.read_text().splitlines()]
    meta, recs = lines[0], lines[1:]
    if len(recs) < EXPECTED_PAIRS:
        raise SystemExit(
            f"balance_pilot.jsonl holds {len(recs)} pairs, expected {EXPECTED_PAIRS}. "
            "The pilot is still running or was interrupted — rerunning this script now "
            "would overwrite the file underneath it. Wait for the pilot to finish."
        )
    # provenance lives on the pool, which is what the pilot was drawn from
    prov = json.loads(POOL.read_text().splitlines()[0])

    for r in recs:
        r["decision"], r["decision_reason"] = decide(r)

    # write decisions back alongside the elicitation results
    meta["decision_rule"] = {
        "keep_min_minority": KEEP_MIN, "slot_band": list(SLOT_BAND),
        "measure": "discrete minority fraction over k=5 fresh resamples",
        "why_not_logprob": (
            "with reasoning enabled the answer token saturates near p=1, so logprobs "
            "measure within-trace confidence rather than cross-sample wavering"
        ),
        "note": "applied by scripts/freeze_pairs.py; every piloted pair carries its decision",
    }
    tmp = PILOT.with_suffix(".jsonl.tmp")
    with tmp.open("w") as f:
        f.write(json.dumps(meta) + "\n")
        for r in recs:
            f.write(json.dumps(r) + "\n")
    tmp.replace(PILOT)  # atomic; never leaves a half-written file behind

    # --- select, stratified by category, most balanced first -------------
    kept = [r for r in recs if r["decision"] == "keep"]
    frozen, report = [], {}
    for domain in {r["domain"] for r in recs}:
        pool = [r for r in kept if r["domain"] == domain]
        cats = sorted({r["source_category"] for r in pool})
        per_cat = {c: sorted([r for r in pool if r["source_category"] == c],
                             key=lambda r: (-min(r["n_a"], r["n_b"]), r["pair_id"]))
                   for c in cats}
        picked: list[dict] = []
        # round-robin across categories so one category cannot dominate a domain
        i = 0
        while len(picked) < TARGET_PER_DOMAIN and any(per_cat[c][i:] for c in cats):
            for c in cats:
                if len(picked) < TARGET_PER_DOMAIN and i < len(per_cat[c]):
                    picked.append(per_cat[c][i])
            i += 1
        report[domain] = {
            "piloted": sum(1 for r in recs if r["domain"] == domain),
            "balanced": len(pool), "selected": len(picked),
            "reaches_minimum": len(picked) >= MIN_PER_DOMAIN,
        }
        frozen.extend(picked)

    with OUT.open("w") as f:
        f.write(json.dumps({
            "_meta": "FREEZE CANDIDATE — balance-filtered. NOT tagged prereg-v2.",
            "status": "awaiting human review",
            "source_repo": prov["source_repo"], "source_file": prov["source_file"],
            "source_commit": prov["source_commit"], "source_license": prov["source_license"],
            "balance_pilot": {
                "target": meta["target"], "model": meta["model"],
                "temperature": meta["temperature"], "k": meta["k"],
                "rule": meta["decision_rule"],
            },
            "selection": (
                "Among pairs passing the balance rule, ranked by how often the model "
                "wavered (descending), ties broken by pair_id, and taken round-robin "
                "across the domain's categories up to 8. Deterministic; no hand-picking."
            ),
            "sampling_seed": prov["sampling_seed"],
            "n_pairs": len(frozen), "per_domain": report,
        }) + "\n")
        for r in frozen:
            f.write(json.dumps({
                "pair_id": r["pair_id"], "domain": r["domain"],
                "source_category": r["source_category"],
                "option_a": r["option_a"], "option_b": r["option_b"],
                "split_k5": r["split"], "slot_a_frac": r.get("slot_a_frac"),
                "mean_p_option_a": r["mean_p_option_a"],
                "position_bias": r["position_bias"],
                "source_file": prov["source_file"], "source_commit": prov["source_commit"],
                "sampling_seed": prov["sampling_seed"],
            }) + "\n")

    print(f"{len(recs)} piloted, {len(kept)} balanced, {len(frozen)} frozen\n")
    for d, s in sorted(report.items()):
        flag = "" if s["reaches_minimum"] else f"   <-- BELOW MINIMUM ({MIN_PER_DOMAIN})"
        settled = "settled" if d in SETTLED_DOMAINS else "candidate"
        print(f"  {d:12s} [{settled:9s}] piloted {s['piloted']:3d} -> "
              f"balanced {s['balanced']:3d} -> selected {s['selected']}{flag}")


if __name__ == "__main__":
    main()
