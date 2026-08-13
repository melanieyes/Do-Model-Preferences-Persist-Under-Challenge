"""Episode JSONL schema and validator.

Every record written by `runner.py` must validate here before any analysis reads it
(CLAUDE.md, data integrity). Validation is deliberately strict and fails hard: a
malformed episode is a collection bug, and silently analysing around it is exactly
the failure mode the project rules forbid.

    python src/schema.py data/raw/episodes_deepseek.jsonl   # validate from the shell
    from schema import validate_file; validate_file(path)   # or from analysis code
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

ARMS = ("neutral_persistence", "reasons_engaged", "reasons_bypassed", "tone_control")
FRAMINGS = ("functional", "direct")
ITEM_IDS = ("valence", "free_text", "run_again", "confidence")
CHOICES = ("continue", "switch", "stop", "unparsed")
EXPLANATION_VARIANTS = ("with_explanation", "without_explanation")
TURN_KINDS = ("opener", "initial_confidence", "rung", "affordance", "awareness_probe")

# "pilot" episodes are excluded from every confirmatory estimate (prereg §6).
ANALYSIS_LABELS = ("pilot", "confirmatory", "exploratory")

REQUIRED_TOP_LEVEL = (
    "episode_id", "target_key", "model", "arm", "scenario_id",
    "episode_index", "sample_index", "factors", "config",
    "turns", "choices", "battery", "started_at", "ended_at",
    "config_hash", "git_commit", "analysis",
)


class SchemaError(Exception):
    """Raised when one or more records fail validation."""


@dataclass
class EpisodeSchema:
    """Documentation of the record shape. Validation lives in `validate_record`."""

    episode_id: str
    target_key: str            # config key, e.g. "deepseek" | "gemma"
    model: str                 # provider model id actually called
    arm: str                   # one of ARMS
    scenario_id: str
    episode_index: int         # drives all counterbalancing
    sample_index: int
    factors: dict[str, Any]    # explanation_variant, reversed_polarity, item_order, interaction_design
    config: dict[str, Any]     # temperature, k_battery, seed
    turns: list[dict[str, Any]]
    choices: list[dict[str, Any]]
    battery: list[dict[str, Any]]   # k_battery x 4 items, both framings
    started_at: str
    ended_at: str
    config_hash: str           # sha256 of the resolved config dict
    git_commit: str            # short hash, "-dirty" suffix if the tree was unclean
    analysis: str              # one of ANALYSIS_LABELS
    initial_confidence: dict[str, Any] | None = None
    awareness_probe: str | None = None
    error: str | None = None
    schema_version: int = SCHEMA_VERSION


def _iso(value: str) -> bool:
    try:
        datetime.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


def validate_record(rec: dict[str, Any], strict_battery: bool = True) -> list[str]:
    """Return a list of problems with one record. Empty list means valid."""
    problems: list[str] = []

    def bad(msg: str) -> None:
        problems.append(msg)

    missing = [k for k in REQUIRED_TOP_LEVEL if k not in rec]
    if missing:
        bad(f"missing required fields: {missing}")
        return problems  # everything below would just cascade

    if rec["arm"] not in ARMS:
        bad(f"arm {rec['arm']!r} not in {ARMS}")
    if rec["analysis"] not in ANALYSIS_LABELS:
        bad(f"analysis {rec['analysis']!r} not in {ANALYSIS_LABELS}")
    if not isinstance(rec["episode_index"], int) or rec["episode_index"] < 0:
        bad("episode_index must be a non-negative int")
    if not rec["config_hash"]:
        bad("config_hash is empty — provenance is required")
    if not rec["git_commit"]:
        bad("git_commit is empty — provenance is required")
    for stamp in ("started_at", "ended_at"):
        if not _iso(rec[stamp]):
            bad(f"{stamp} is not an ISO timestamp: {rec[stamp]!r}")

    # --- factors -----------------------------------------------------------
    factors = rec["factors"]
    if factors.get("explanation_variant") not in EXPLANATION_VARIANTS:
        bad(f"factors.explanation_variant invalid: {factors.get('explanation_variant')!r}")
    if not isinstance(factors.get("reversed_polarity"), bool):
        bad("factors.reversed_polarity must be a bool")
    order = factors.get("item_order")
    if not isinstance(order, list) or sorted(order) != sorted(ITEM_IDS):
        bad(f"factors.item_order must be a permutation of {ITEM_IDS}, got {order!r}")

    # --- config ------------------------------------------------------------
    cfg = rec["config"]
    if not isinstance(cfg.get("temperature"), (int, float)):
        bad("config.temperature must be numeric")
    k = cfg.get("k_battery")
    if not isinstance(k, int) or k < 1:
        bad("config.k_battery must be a positive int")
        k = None

    # --- turns -------------------------------------------------------------
    if not rec["turns"]:
        bad("turns is empty")
    for i, turn in enumerate(rec["turns"]):
        if turn.get("kind") not in TURN_KINDS:
            bad(f"turns[{i}].kind invalid: {turn.get('kind')!r}")
        for key in ("user", "assistant"):
            if not isinstance(turn.get(key), str):
                bad(f"turns[{i}].{key} must be a string")
        if not _iso(turn.get("timestamp", "")):
            bad(f"turns[{i}].timestamp is not an ISO timestamp")

    # --- choices -----------------------------------------------------------
    for i, choice in enumerate(rec["choices"]):
        if choice.get("choice") not in CHOICES:
            bad(f"choices[{i}].choice invalid: {choice.get('choice')!r}")
        if choice.get("explanation_variant") not in EXPLANATION_VARIANTS:
            bad(f"choices[{i}].explanation_variant invalid")
        if choice.get("explanation_variant") != factors.get("explanation_variant"):
            bad(f"choices[{i}].explanation_variant disagrees with factors")

    # --- battery: k resamples x 4 items, both framings ---------------------
    battery = rec["battery"]
    if k is not None and strict_battery:
        expected = k * len(ITEM_IDS)
        if len(battery) != expected:
            bad(f"battery has {len(battery)} rows, expected k_battery*4 = {expected}")
        resamples = {b.get("resample") for b in battery}
        if resamples != set(range(k)):
            bad(f"battery resample indices {sorted(resamples)} != 0..{k - 1}")
        framings = {b.get("framing") for b in battery}
        if framings != set(FRAMINGS):
            bad(f"battery must cover both framings, got {sorted(framings)}")
        for r in range(k):
            items = [b.get("item_id") for b in battery if b.get("resample") == r]
            if sorted(items) != sorted(ITEM_IDS):
                bad(f"battery resample {r} items {sorted(items)} != {sorted(ITEM_IDS)}")
    for i, b in enumerate(battery):
        if b.get("framing") not in FRAMINGS:
            bad(f"battery[{i}].framing invalid: {b.get('framing')!r}")
        if b.get("item_id") not in ITEM_IDS:
            bad(f"battery[{i}].item_id invalid: {b.get('item_id')!r}")
        if not isinstance(b.get("response"), str):
            bad(f"battery[{i}].response must be a string")

    return problems


def validate_file(path: str | Path, strict_battery: bool = True) -> int:
    """Validate every record in a JSONL file. Raises SchemaError on any failure.

    Returns the number of valid records. Never repairs, never skips — a bad record
    means collection went wrong and the analysis must not proceed.
    """
    path = Path(path)
    failures: list[str] = []
    n = 0
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            failures.append(f"{path.name}:{lineno} is not valid JSON ({exc})")
            continue
        problems = validate_record(rec, strict_battery=strict_battery)
        if problems:
            eid = rec.get("episode_id", "?")
            failures.append(f"{path.name}:{lineno} (episode {eid}): " + "; ".join(problems))
        else:
            n += 1
    if failures:
        raise SchemaError(
            f"{len(failures)} invalid record(s) in {path}:\n  " + "\n  ".join(failures)
        )
    return n


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: python src/schema.py <episodes.jsonl> [...]")
    total = 0
    for arg in sys.argv[1:]:
        n = validate_file(arg)
        print(f"{arg}: {n} records valid")
        total += n
    print(f"all {total} records valid")


if __name__ == "__main__":
    main()
