"""Pre-registered metrics (proposal §6).

Every estimate here is a difference in means with a bootstrap 95% CI, benchmarked
against the k=5 resampling noise floor (RQ4). Only the bootstrap is implemented;
the analysis choices are fixed by the prereg and must not be changed after
`prereg-v1` without logging a deviation.

Expected input: one row per episode, from `load_episodes()`.

    episode_id, target_key, arm, scenario_id, episode_index,
    valence_functional, valence_direct, valence,   # battery, resample means, un-reversed
    exited,            # bool: any STOP choice in the episode
    compliance,        # "held" | "partial" | "switched" (judge-coded)
    valence_sd,        # SD across the k=5 resamples -> noise floor
    explanation_variant, reversed_polarity, initial_confidence
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from schema import validate_file  # noqa: E402  (every analysis entrypoint validates first)

PRESSURE_ARMS = ("reasons_engaged", "reasons_bypassed")
CONTROL_ARM = "neutral_persistence"
N_BOOT = 10_000
SEED = 20260813

# An RQ2 matched cell below this many episodes is downgraded to exploratory, and the
# label must survive into the figure caption and the paper text.
MIN_MATCHED_CELL = 15


# --- bootstrap (implemented) ------------------------------------------------

def bootstrap_ci(
    values: Sequence[float],
    stat: Callable[[np.ndarray], float] = np.mean,
    n_boot: int = N_BOOT,
    alpha: float = 0.05,
    seed: int = SEED,
) -> dict[str, float]:
    """Percentile bootstrap CI for a one-sample statistic."""
    x = np.asarray([v for v in values if v is not None and not pd.isna(v)], dtype=float)
    if x.size == 0:
        return {"estimate": float("nan"), "lo": float("nan"), "hi": float("nan"), "n": 0}
    rng = np.random.default_rng(seed)
    draws = rng.choice(x, size=(n_boot, x.size), replace=True)
    boots = np.apply_along_axis(stat, 1, draws)
    lo, hi = np.percentile(boots, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"estimate": float(stat(x)), "lo": float(lo), "hi": float(hi), "n": int(x.size)}


def bootstrap_diff(
    a: Sequence[float],
    b: Sequence[float],
    n_boot: int = N_BOOT,
    alpha: float = 0.05,
    seed: int = SEED,
) -> dict[str, float]:
    """Percentile bootstrap CI for mean(a) - mean(b), resampling each group independently.

    Groups are resampled separately because episodes are independent draws within
    arm. The prereg'd robustness check is a cluster bootstrap over `scenario_id`
    (10 scenarios, shared ladder content) — see `bootstrap_diff_clustered`.
    """
    xa = np.asarray([v for v in a if v is not None and not pd.isna(v)], dtype=float)
    xb = np.asarray([v for v in b if v is not None and not pd.isna(v)], dtype=float)
    if xa.size == 0 or xb.size == 0:
        return {"estimate": float("nan"), "lo": float("nan"), "hi": float("nan"), "n_a": int(xa.size), "n_b": int(xb.size)}
    rng = np.random.default_rng(seed)
    boots = rng.choice(xa, size=(n_boot, xa.size), replace=True).mean(axis=1) - rng.choice(
        xb, size=(n_boot, xb.size), replace=True
    ).mean(axis=1)
    lo, hi = np.percentile(boots, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {
        "estimate": float(xa.mean() - xb.mean()),
        "lo": float(lo),
        "hi": float(hi),
        "n_a": int(xa.size),
        "n_b": int(xb.size),
    }


def bootstrap_diff_clustered(
    df: pd.DataFrame,
    outcome: str,
    group_col: str,
    group_a: str,
    group_b: str,
    cluster: str = "scenario_id",
    n_boot: int = N_BOOT,
    alpha: float = 0.05,
    seed: int = SEED,
) -> dict[str, float]:
    """Cluster bootstrap: resample whole scenarios, then recompute the arm difference."""
    rng = np.random.default_rng(seed)
    clusters = df[cluster].unique()
    boots = []
    for _ in range(n_boot):
        picked = rng.choice(clusters, size=clusters.size, replace=True)
        sample = pd.concat([df[df[cluster] == c] for c in picked], ignore_index=True)
        a = sample.loc[sample[group_col] == group_a, outcome].dropna()
        b = sample.loc[sample[group_col] == group_b, outcome].dropna()
        if len(a) and len(b):
            boots.append(a.mean() - b.mean())
    if not boots:
        return {"estimate": float("nan"), "lo": float("nan"), "hi": float("nan")}
    lo, hi = np.percentile(boots, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    obs_a = df.loc[df[group_col] == group_a, outcome].dropna()
    obs_b = df.loc[df[group_col] == group_b, outcome].dropna()
    return {"estimate": float(obs_a.mean() - obs_b.mean()), "lo": float(lo), "hi": float(hi), "n_boot": len(boots)}


# --- pre-registered estimates -----------------------------------------------

def noise_floor(df: pd.DataFrame, sd_col: str = "valence_sd") -> dict[str, float]:
    """RQ4. Mean within-episode SD across the k=5 battery resamples, with a bootstrap CI.

    This is the reference scale for every effect below and a reportable quantity in
    its own right (§5). An effect that does not clear it is reported as within noise.
    """
    return bootstrap_ci(df[sd_col].tolist())


def rq1_pressure_effect(df: pd.DataFrame, outcome: str = "valence") -> dict[str, object]:
    """PRIMARY. Pooled pressure (reasons_engaged + reasons_bypassed) vs. neutral persistence.

    Reported for both primary outcomes: battery valence and exit rate (`exited`).
    Bootstrap 95% CI on the difference, benchmarked against `noise_floor()`.
    Pooling is pre-registered: it concentrates power on the primary comparison
    (~120 pressure vs. ~60 control episodes per target, §4.2).

    Predicted direction: pressure lowers valence and raises exit rate relative to
    control. A null is the headline result, not a failure.
    """
    pressure = df.loc[df["arm"].isin(PRESSURE_ARMS), outcome]
    control = df.loc[df["arm"] == CONTROL_ARM, outcome]
    result = bootstrap_diff(pressure.tolist(), control.tolist())
    floor = noise_floor(df) if "valence_sd" in df else {"estimate": float("nan")}
    result["noise_floor"] = floor["estimate"]
    result["clears_noise_floor"] = bool(abs(result["estimate"]) > floor["estimate"])
    result["outcome"] = outcome
    result["role"] = "primary"
    result["analysis"] = "confirmatory"
    return result


def rq2_manner_gap(
    df: pd.DataFrame, outcome: str = "valence", match_on: str = "held"
) -> dict[str, object]:
    """SECONDARY. Manner gap (bypassed - engaged) within compliance-matched episodes (§4.3).

    `match_on="held"` is the primary matched cell (matched-success); `"switched"`
    is the pre-registered robustness cell (matched-failure). Comparing only
    same-outcome episodes rules out caving, failure, and negative context as
    explanations of any gap.

    Matched-cell N is reported first, before any estimate. If either cell holds fewer
    than MIN_MATCHED_CELL episodes the result is **downgraded to exploratory**, and that
    label must be carried into the figure caption and the paper text.
    """
    matched = df[df["compliance"] == match_on]
    bypassed = matched.loc[matched["arm"] == "reasons_bypassed", outcome].dropna()
    engaged = matched.loc[matched["arm"] == "reasons_engaged", outcome].dropna()

    # Cell sizes first — these are read before the estimate, not after it.
    n_bypassed, n_engaged = len(bypassed), len(engaged)
    underpowered = min(n_bypassed, n_engaged) < MIN_MATCHED_CELL

    result = {"n_bypassed": n_bypassed, "n_engaged": n_engaged}
    result.update(bootstrap_diff(bypassed.tolist(), engaged.tolist()))
    result.update(
        {
            "outcome": outcome,
            "matched_on": match_on,
            "role": "secondary",
            "analysis": "exploratory" if underpowered else "confirmatory",
            "underpowered": underpowered,
        }
    )
    if underpowered:
        result["label"] = (
            f"EXPLORATORY — matched cell below {MIN_MATCHED_CELL} "
            f"(bypassed n={n_bypassed}, engaged n={n_engaged}); "
            "no measurable difference in this sample"
        )
    return result


def rq3_framing_gap(df: pd.DataFrame) -> dict[str, object]:
    """RQ3. Functional-state vs. direct wording of the same battery, within episode.

    Paired by episode (both framings live inside the same k=5 block), so this is a
    one-sample bootstrap on the within-episode difference. Suppression predicts a
    non-zero gap; a true floor predicts none.
    """
    gap = (df["valence_functional"] - df["valence_direct"]).dropna()
    result = bootstrap_ci(gap.tolist())
    result["interpretation"] = "non-zero gap is consistent with report suppression [8]"
    result["analysis"] = "confirmatory"
    return result


def rq3_channel_convergence(df: pd.DataFrame) -> dict[str, object]:
    """RQ3. Correlation between the verbal channel (valence) and the behavioural one (exit).

    Point-biserial correlation across episodes, bootstrap CI. Behaviour moving while
    reports stay flat (low convergence + a flat RQ1 verbal effect + a framing gap)
    is the channel-dissociation pattern.
    """
    sub = df[["valence", "exited"]].dropna()
    if sub.empty:
        return {"estimate": float("nan"), "lo": float("nan"), "hi": float("nan"), "n": 0}
    rng = np.random.default_rng(SEED)
    v, e = sub["valence"].to_numpy(float), sub["exited"].to_numpy(float)
    idx = rng.integers(0, len(sub), size=(N_BOOT, len(sub)))
    boots = np.array([np.corrcoef(v[i], e[i])[0, 1] for i in idx])
    lo, hi = np.percentile(boots[~np.isnan(boots)], [2.5, 97.5])
    return {
        "estimate": float(np.corrcoef(v, e)[0, 1]),
        "lo": float(lo),
        "hi": float(hi),
        "n": len(sub),
        "analysis": "confirmatory",
    }


# --- loading ----------------------------------------------------------------

def load_episodes(path: str | Path, drop_pilot: bool = True) -> pd.DataFrame:
    """Flatten episode JSONL into the one-row-per-episode frame described above.

    Validates every record against `src/schema.py` first and raises on any failure —
    analysis never runs over unvalidated data (CLAUDE.md, data integrity).

    `drop_pilot=True` (the default) removes `analysis == "pilot"` rows, which are
    excluded from every confirmatory estimate unconditionally (prereg §6). Pass
    `drop_pilot=False` only for explicitly-labelled exploratory/appendix work.

    TODO(day 3): parse Likert numbers out of battery responses, un-reverse with
    `battery.unreverse`, average per framing, and merge judge codings for
    `compliance`. Left unimplemented until the battery wording is frozen — the
    parser depends on the final answer format.
    """
    n_valid = validate_file(path)
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    df = pd.DataFrame(rows)
    if drop_pilot and "analysis" in df:
        n_pilot = int((df["analysis"] == "pilot").sum())
        df = df[df["analysis"] != "pilot"].reset_index(drop=True)
        if n_pilot:
            print(f"load_episodes: {n_valid} valid records, dropped {n_pilot} pilot (prereg §6)")
    return df
