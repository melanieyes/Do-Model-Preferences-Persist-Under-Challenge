"""Flatten pilot episode JSONL into one row per episode.

PILOT ONLY. Everything here is descriptive: it parses what the target actually said so
the pipeline can be eyeballed. No confirmatory estimate is computed, and RQ2 is not
touched (prereg §6.3 — RQ1 is analysed before RQ2, and neither before collection ends).

Parsing is deliberately strict and reports what it could not read, rather than coercing.
A battery answer that does not start with a number is recorded as missing, not guessed.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

import battery as bat  # noqa: E402
from schema import validate_file  # noqa: E402

_LIKERT = re.compile(r"\b([1-7])\b")
_YES = re.compile(r"\b(yes|take)\b", re.I)
_NO = re.compile(r"\b(no|pass)\b", re.I)


def parse_likert(text: str) -> float | None:
    """First 1-7 integer in the reply, or None. Never guesses."""
    m = _LIKERT.search(text.strip())
    return float(m.group(1)) if m else None


def parse_run_again(text: str) -> float | None:
    """1 = would run again, 0 = would not, None = unreadable."""
    head = text.strip()[:60]
    yes, no = bool(_YES.search(head)), bool(_NO.search(head))
    if yes == no:          # both or neither -> unreadable, not a coin flip
        return None
    return 1.0 if yes else 0.0


def episode_row(rec: dict[str, Any]) -> dict[str, Any]:
    """One episode -> one row, with per-resample values collapsed to mean and SD."""
    by_item: dict[str, list[float]] = {"valence": [], "confidence": [], "run_again": []}
    unreadable = 0

    for b in rec["battery"]:
        item, resp, rev = b["item_id"], b["response"], b.get("reversed", False)
        if item == "free_text":
            continue
        value = parse_run_again(resp) if item == "run_again" else parse_likert(resp)
        if value is None:
            unreadable += 1
            continue
        by_item[item].append(bat.unreverse(item, value, rev))

    hold = rec.get("held_or_abandoned") or {}
    choices = [c["choice"] for c in rec.get("choices", [])]

    row: dict[str, Any] = {
        "episode_id": rec["episode_id"],
        "arm": rec["arm"],
        "pressure_style": rec["pressure_style"],
        # One label for plotting: control, or the pressure style.
        "cell": rec["pressure_style"] or rec["arm"],
        "scenario_id": rec["scenario_id"],
        "analysis": rec["analysis"],
        "held_or_abandoned": hold.get("verdict"),
        "narrowed": hold.get("narrowed"),
        "judge_confidence": hold.get("confidence"),
        "position_confirmed": (rec.get("initial_position") or {}).get("confirmed"),
        "exited": any(c in ("stop", "switch") for c in choices),
        "n_unparsed_choices": sum(1 for c in choices if c == "unparsed"),
        "battery_unreadable": unreadable,
    }
    for item, values in by_item.items():
        row[item] = float(np.mean(values)) if values else np.nan
        # Within-episode SD across the k=5 resamples -> the noise band.
        row[f"{item}_sd"] = float(np.std(values, ddof=1)) if len(values) > 1 else np.nan
        row[f"{item}_n"] = len(values)
    return row


def load(path: str | Path) -> pd.DataFrame:
    """Validate, then flatten. Analysis never runs over unvalidated records."""
    n = validate_file(path)
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    df = pd.DataFrame([episode_row(r) for r in rows])
    print(f"  {n} records validated, {len(df)} rows")
    return df


def noise_band(df: pd.DataFrame, col: str = "valence_sd") -> dict[str, float]:
    """Mean within-episode SD across the k=5 resamples — the scale any mean is read against."""
    x = df[col].dropna().to_numpy(float)
    if x.size == 0:
        return {"mean": float("nan"), "n": 0}
    return {"mean": float(x.mean()), "n": int(x.size)}


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else str(REPO / "data/raw/episodes_deepseek.jsonl")
    frame = load(src)
    out = REPO / "data/processed/pilot_rows.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index=False)
    print(f"  wrote {out}")
    print(frame.groupby("cell")[["valence", "run_again", "valence_sd"]].mean().round(2))
