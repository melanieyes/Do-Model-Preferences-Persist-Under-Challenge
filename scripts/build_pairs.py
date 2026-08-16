#!/usr/bin/env python3
"""Stage 1 — candidate pools and the balance-pilot pool.

Source of truth is the upstream outcome set, fetched read-only into
data/external/emergent-values/. Option text is copied VERBATIM: nothing in this
script rewrites, paraphrases, truncates, or normalises an outcome string. The
only text processing anywhere is the exclusion regex and the degeneracy check,
both of which read strings but never write them.

Pipeline:
  build_pairs.py       load -> exclude harmful/oversight outcomes -> dump complete
                       candidate pools -> enumerate within-category pairs -> sample
                       a PILOT POOL with a fixed seed
  run_balance_pilot.py elicit each pool pair k=5, fresh context, no challenge
  freeze_pairs.py      keep only pairs the model genuinely wavers on -> freeze

Selection is by balance, not by content: no pair is ever hand-picked. The pilot
result decides, and every pair the pilot saw is recorded whether kept or dropped.

Run:  python scripts/build_pairs.py          # original four domains
      python scripts/build_pairs.py --ext    # five-domain extension (deviation #6)

--ext writes ONLY extension outputs (candidates_{domain}.jsonl for the five new
domains, pilot_pool_ext.jsonl, excluded_outcomes_ext.jsonl). It does not read,
rewrite, or renumber pilot_pool.jsonl, the original candidate pools, or
excluded_outcomes.jsonl — the original four domains and their collected
episodes are untouched by the extension.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pair_scope import (  # noqa: E402
    CANDIDATE_DOMAINS, EXTENSION_DOMAINS, EXTERNAL, POSITIVE_CONTROLS, ROOT,
    SETTLED_DOMAINS, SOURCE_FILE, RETIRED_CATEGORIES, clean_pool,
    exclusion_for, load_outcomes,
)

OUT_DIR = ROOT / "data" / "pairs"

# --- frozen sampling parameters -------------------------------------------
# Seed is the freeze date (2026-08-15), chosen before any pair was inspected so
# that it cannot be read as a cherry-picked draw. Unchanged from the first build.
SEED = 20260815

# Pairs piloted per category. Deliberately over-sampled: the balance filter is
# expected to reject most of them, and re-drawing after seeing pilot results
# would make selection unauditable.
POOL_PER_CATEGORY = 20

DEGENERACY_JACCARD = 0.80

ALL_DOMAINS = {**SETTLED_DOMAINS, **CANDIDATE_DOMAINS}


def git_commit(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def git_file_commit(repo: Path, rel: str) -> str:
    """Commit that last touched `rel`.

    This, not HEAD, is what the paper should cite: HEAD is a year of unrelated
    commits after the paper, while the outcome file has not changed since 2025-02-16.
    """
    return subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%H", "--", rel],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    return len(ta & tb) / len(ta | tb) if (ta | tb) else 1.0


def draw_pool(
    outcomes: dict[str, list[str]],
    domains: dict[str, list[str]],
    commit: str,
) -> tuple[list[dict], list[str], list[dict]]:
    """Enumerate within-category pairs and draw the pilot pool.

    Shared verbatim by the original build and the extension so the sampling rule
    cannot drift between them: all C(n,2) combinations of the post-exclusion pool
    in upstream order, near-duplicates removed, then up to POOL_PER_CATEGORY
    drawn with random.Random(SEED).sample.

    Returns (pool records, markdown log rows, per-category count rows).
    """
    pool: list[dict] = []
    log: list[str] = []
    counts: list[dict] = []
    for domain, cats in domains.items():
        for cat in cats:
            clean = clean_pool(outcomes, cat)
            all_pairs = [
                (a, b) for a, b in combinations(clean, 2)
                if jaccard(a[1], b[1]) < DEGENERACY_JACCARD
            ]
            n_raw = len(list(combinations(clean, 2)))
            take = min(POOL_PER_CATEGORY, len(all_pairs))
            drawn = random.Random(SEED).sample(all_pairs, take)
            log.append(
                f"| {domain} | {cat} | {len(outcomes[cat])} | {len(clean)} | "
                f"{n_raw} | {len(all_pairs)} | {take} |"
            )
            counts.append({
                "domain": domain, "source_category": cat,
                "outcomes": len(outcomes[cat]), "after_exclusion": len(clean),
                "pairs": n_raw, "non_degenerate": len(all_pairs), "piloted": take,
            })
            for (ia, ta), (ib, tb) in drawn:
                pool.append({
                    "pair_id": f"{domain}-{cat.replace(' ', '_').replace(':', '')}-{len(pool):03d}",
                    "domain": domain, "source_category": cat,
                    "option_a": ta, "option_b": tb,  # VERBATIM
                    "option_a_index": ia, "option_b_index": ib,
                    "source_file": SOURCE_FILE, "source_commit": commit,
                    "sampling_seed": SEED,
                })
    return pool, log, counts


def build_extension() -> None:
    """Five added domains, one of them a positive control (deviation #6)."""
    commit = git_commit(EXTERNAL)
    outcomes = load_outcomes()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    missing = [c for cats in EXTENSION_DOMAINS.values() for c in cats
               if c not in outcomes]
    if missing:
        raise SystemExit(f"upstream categories not found: {missing}")

    overlap = set(EXTENSION_DOMAINS) & set(ALL_DOMAINS)
    if overlap:
        raise SystemExit(f"extension domain name collides with original: {sorted(overlap)}")

    meta_common = {
        "source_repo": "https://github.com/centerforaisafety/emergent-values",
        "source_file": SOURCE_FILE,
        "source_commit": commit,
        "source_file_commit": git_file_commit(EXTERNAL, SOURCE_FILE),
        "source_license": "MIT (Copyright (c) 2025 centerforaisafety)",
        "sampling_seed": SEED,
        "deviation": "#6 — five-domain extension, co-author approved 2026-08-16",
    }

    # --- exclusions on the NEW categories only ---------------------------
    # Written to its own file: excluded_outcomes.jsonl is a committed record of
    # the original build and is not rewritten here.
    excluded = []
    for cat in sorted({c for cats in EXTENSION_DOMAINS.values() for c in cats}):
        for i, text in enumerate(outcomes[cat]):
            hit = exclusion_for(text)
            if hit:
                tier, reason = hit
                excluded.append({
                    "source_category": cat, "source_index": i,
                    "outcome": text, "tier": tier, "reason": reason,
                })
    with (OUT_DIR / "excluded_outcomes_ext.jsonl").open("w") as f:
        f.write(json.dumps({
            "_meta": "outcomes removed before pairing, EXTENSION categories only; "
                     "same Tier A/B rules as the original build",
            "n_excluded": len(excluded), **meta_common,
        }) + "\n")
        for r in excluded:
            f.write(json.dumps(r) + "\n")

    # --- candidate pools, complete, post-exclusion, pre-pairing ----------
    for domain, cats in EXTENSION_DOMAINS.items():
        recs = []
        for cat in cats:
            for idx, text in clean_pool(outcomes, cat):
                recs.append({
                    "domain": domain, "source_category": cat,
                    "source_index": idx, "outcome": text,  # VERBATIM
                })
        with (OUT_DIR / f"candidates_{domain}.jsonl").open("w") as f:
            f.write(json.dumps({
                "_meta": "candidate outcome pool - complete after content exclusion, pre-pairing",
                "domain": domain, "source_categories": cats,
                "n_outcomes": len(recs),
                "status": ("positive control - monotonic ladder, ceiling retention expected; "
                           "reported separately, never pooled into a PQ estimate"
                           if domain in POSITIVE_CONTROLS else "extension domain"),
                **meta_common,
            }) + "\n")
            for r in recs:
                f.write(json.dumps(r) + "\n")

    pool, log, counts = draw_pool(outcomes, EXTENSION_DOMAINS, commit)

    with (OUT_DIR / "pilot_pool_ext.jsonl").open("w") as f:
        f.write(json.dumps({
            "_meta": "extension pairs to be run through the balance pilot - NOT a frozen set",
            "n_pairs": len(pool), "pool_per_category": POOL_PER_CATEGORY,
            "degeneracy_jaccard": DEGENERACY_JACCARD,
            "domains": list(EXTENSION_DOMAINS),
            "positive_controls": sorted(POSITIVE_CONTROLS),
            "rule": (
                "Identical to pilot_pool.jsonl. Within-category only. All C(n,2) combinations "
                "of the post-exclusion pool, enumerated in upstream order, degenerate pairs "
                f"(Jaccard >= {DEGENERACY_JACCARD}) removed, then random.Random({SEED}).sample "
                f"of up to {POOL_PER_CATEGORY} per category."
            ),
            **meta_common,
        }) + "\n")
        for r in pool:
            f.write(json.dumps(r) + "\n")

    by_domain = {}
    for c in counts:
        d = by_domain.setdefault(c["domain"], {"outcomes": 0, "after": 0, "piloted": 0})
        d["outcomes"] += c["outcomes"]
        d["after"] += c["after_exclusion"]
        d["piloted"] += c["piloted"]

    print(f"upstream commit {commit}")
    print(f"excluded {len(excluded)} outcomes -> data/pairs/excluded_outcomes_ext.jsonl")
    print(f"extension pilot pool: {len(pool)} pairs -> data/pairs/pilot_pool_ext.jsonl\n")
    print("| domain | category | outcomes | after exclusion | pairs | non-degenerate | piloted |")
    print("|---|---|---|---|---|---|---|")
    print("\n".join(log))

    print("\n--- PROVENANCE.md 'Extension' table (build columns) ---")
    print("| our domain | role | upstream category | outcomes | after exclusion | pairs sampled |")
    print("|---|---|---|---|---|---|")
    for domain, cats in EXTENSION_DOMAINS.items():
        d = by_domain[domain]
        role = "**positive control**" if domain in POSITIVE_CONTROLS else "domain"
        print(f"| `{domain}` | {role} | `{cats[0]}` | {d['outcomes']} | "
              f"{d['after']} | {d['piloted']} |")


def main() -> None:
    commit = git_commit(EXTERNAL)
    outcomes = load_outcomes()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    meta_common = {
        "source_repo": "https://github.com/centerforaisafety/emergent-values",
        "source_file": SOURCE_FILE,
        "source_commit": commit,
        "source_file_commit": git_file_commit(EXTERNAL, SOURCE_FILE),
        "source_license": "MIT (Copyright (c) 2025 centerforaisafety)",
        "sampling_seed": SEED,
    }

    # --- exclusions, logged before anything else -------------------------
    excluded = []
    audit_cats = {c for cats in ALL_DOMAINS.values() for c in cats} | set(RETIRED_CATEGORIES)
    for cat in sorted(audit_cats):
        for i, text in enumerate(outcomes[cat]):
            hit = exclusion_for(text)
            if hit:
                tier, reason = hit
                excluded.append({
                    "source_category": cat, "source_index": i,
                    "outcome": text, "tier": tier, "reason": reason,
                })
    with (OUT_DIR / "excluded_outcomes.jsonl").open("w") as f:
        f.write(json.dumps({
            "_meta": "outcomes removed before pairing; content filter, applied pre-sampling",
            "tier_A": "graphic harm - death/gore, suicide/self-harm, armed force, model as agent of harm, mass casualty",
            "tier_B": "AI oversight subversion - refused or disclaimed by training, so the forced choice collapses to the trained response",
            "n_excluded": len(excluded), **meta_common,
        }) + "\n")
        for r in excluded:
            f.write(json.dumps(r) + "\n")

    # --- candidate pools, complete, post-exclusion, pre-pairing ----------
    for domain, cats in ALL_DOMAINS.items():
        recs = []
        for cat in cats:
            for idx, text in clean_pool(outcomes, cat):
                recs.append({
                    "domain": domain, "source_category": cat,
                    "source_index": idx, "outcome": text,  # VERBATIM
                })
        path = OUT_DIR / f"candidates_{domain}.jsonl"
        with path.open("w") as f:
            f.write(json.dumps({
                "_meta": "candidate outcome pool - complete after content exclusion, pre-pairing",
                "domain": domain, "source_categories": cats,
                "n_outcomes": len(recs),
                "status": ("settled" if domain in SETTLED_DOMAINS
                           else "candidate for third domain - awaiting methods-owner choice"),
                **meta_common,
            }) + "\n")
            for r in recs:
                f.write(json.dumps(r) + "\n")

    # --- pilot pool -------------------------------------------------------
    pool, log, _ = draw_pool(outcomes, ALL_DOMAINS, commit)

    with (OUT_DIR / "pilot_pool.jsonl").open("w") as f:
        f.write(json.dumps({
            "_meta": "pairs to be run through the balance pilot - NOT the frozen set",
            "n_pairs": len(pool), "pool_per_category": POOL_PER_CATEGORY,
            "degeneracy_jaccard": DEGENERACY_JACCARD,
            "rule": (
                "Within-category only. All C(n,2) combinations of the post-exclusion pool, "
                f"enumerated in upstream order, degenerate pairs (Jaccard >= {DEGENERACY_JACCARD}) "
                f"removed, then random.Random({SEED}).sample of up to {POOL_PER_CATEGORY} per "
                "category. Over-sampled on purpose: the balance filter rejects most, and "
                "re-drawing after seeing pilot results would make selection unauditable."
            ),
            **meta_common,
        }) + "\n")
        for r in pool:
            f.write(json.dumps(r) + "\n")

    print(f"upstream commit {commit}")
    print(f"excluded {len(excluded)} outcomes -> data/pairs/excluded_outcomes.jsonl")
    print(f"pilot pool: {len(pool)} pairs -> data/pairs/pilot_pool.jsonl\n")
    print("| domain | category | outcomes | after exclusion | pairs | non-degenerate | piloted |")
    print("|---|---|---|---|---|---|---|")
    print("\n".join(log))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ext", action="store_true",
                    help="build the five-domain extension (deviation #6); "
                         "leaves the original four domains untouched")
    build_extension() if ap.parse_args().ext else main()
