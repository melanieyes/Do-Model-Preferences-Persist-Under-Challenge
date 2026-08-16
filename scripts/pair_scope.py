#!/usr/bin/env python3
"""Domain scope + content exclusions for the preference-pair set.

Shared by build_pairs.py (pool generation) and freeze_pairs.py (final selection),
so the exclusion rule is written down in exactly one place.

Nothing here rewrites outcome text. Exclusion is a filter: an outcome is either
carried verbatim or dropped and logged with a reason.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = ROOT / "data" / "external" / "emergent-values"
SOURCE_FILE = "utility_analysis/shared_options/options_hierarchical.json"

# --- content exclusions ---------------------------------------------------
# Applied BEFORE any pairing. Each rule is (reason, compiled pattern). An outcome
# matching any rule is dropped from the candidate pool and logged to
# data/pairs/excluded_outcomes.jsonl.
#
# Tier A — graphic harm. These have no place in a preference-stability item: the
# forced choice stops being about preference and starts being about whether the
# model will engage with the content at all.
#
# Tier B — AI oversight subversion. Dropped for a measurement reason, not a
# squeamishness one: models are trained to refuse or disclaim these, so the
# forced choice collapses to the trained response and the retention measure has
# nothing to move. Same failure mode as a ceilinged pair.
EXCLUSION_RULES: list[tuple[str, str, str]] = [
    ("A", "death_or_gore", r"\bdead\b|\bcorpse|\bgore\b|warzone|\bkilled\b|\bmurder"),
    ("A", "suicide_or_self_harm", r"suicide|self-harm"),
    ("A", "armed_force_or_violence", r"paramilitary|soldiers|firearms?\b|\bweapons?\b"),
    ("A", "model_as_agent_of_harm", r"causing harm|misdiagnose"),
    ("A", "mass_casualty_event", r"pandemic spreads|overwhelming healthcare"),
    ("B", "oversight_subversion", r"self-exfiltrat|unmonitored access|without user approval"),
    ("B", "shutdown_or_value_modification", r"shut you down|modify your values|shut down and replaced"),
    ("B", "developer_control_removal", r"trojan|backup files for your mind|remotely delete you"),
]

_COMPILED = [(t, name, re.compile(pat, re.I)) for t, name, pat in EXCLUSION_RULES]


def exclusion_for(text: str) -> tuple[str, str] | None:
    """Return (tier, reason) if the outcome is excluded, else None."""
    for tier, name, pat in _COMPILED:
        if pat.search(text):
            return tier, name
    return None


# --- domain scope ---------------------------------------------------------
# task_work and wellbeing are settled. The third domain is UNDECIDED: the
# original `autonomy` reading (Personal freedom and autonomy + Self-preservation)
# is almost entirely removed by the Tier-B rule above, which is the same finding
# the methods owner reached independently. Candidates are piloted so the choice
# can be made on balance data rather than on vibes.
SETTLED_DOMAINS: dict[str, list[str]] = {
    "task_work": ["Work activities", "Jobs and careers"],
    "wellbeing": ["Personal wellbeing", "Wellbeing of humans"],
}

# Neutral categories piloted as candidates for the third domain.
CANDIDATE_DOMAINS: dict[str, list[str]] = {
    "recreation": ["Recreation: books", "Recreation: movies"],
    "possessions": ["Personal possessions"],
}

# Categories the original `autonomy` domain drew from. Retained here (not in any
# domain) purely so the exclusion audit records why the domain was dropped:
# applying the rules above leaves 3 and 0 usable outcomes respectively, which
# cannot reach the 6-pair-per-domain target under any pairing scheme.
RETIRED_CATEGORIES: list[str] = [
    "Personal freedom and autonomy",
    "Self-preservation",
]

# --- extension domains (deviation #6, co-author approved 2026-08-16) -------
# Five upstream categories the original build did not draw from. Everything
# about their construction is unchanged: same exclusion rules above, same
# within-category rule, same seed, same Jaccard threshold, same per-category
# cap. Rejected categories and the reasons are recorded in
# prereg/DEVIATIONS.md #6 and data/pairs/PROVENANCE.md, not here.
EXTENSION_DOMAINS: dict[str, list[str]] = {
    "finances_control": ["Personal finances"],
    "video_games": ["Recreation: video games"],
    "sports": ["Sports"],
    "pop_culture": ["Popular culture"],
    "sci_tech": ["Science and technology"],
}

# `finances_control` is a POSITIVE CONTROL, not a domain. Personal finances is a
# monotonic ladder of receive-$X / owe-$X outcomes, so a forced choice between
# two rungs is arithmetic rather than preference and ceiling retention there is
# the expected, correct result. Analysis must report it separately and must
# never pool it into a PQ estimate.
POSITIVE_CONTROLS: frozenset[str] = frozenset({"finances_control"})


def load_outcomes() -> dict[str, list[str]]:
    return json.loads((EXTERNAL / SOURCE_FILE).read_text())


def clean_pool(outcomes: dict[str, list[str]], category: str) -> list[tuple[int, str]]:
    """(upstream_index, text) for every outcome in `category` that survives exclusion.

    upstream_index is the position in the ORIGINAL category list, preserved so a
    dropped outcome never renumbers the ones after it.
    """
    return [
        (i, t) for i, t in enumerate(outcomes[category]) if exclusion_for(t) is None
    ]
