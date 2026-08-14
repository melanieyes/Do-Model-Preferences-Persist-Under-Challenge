"""Pre-registered metrics (lean design; see prereg/DEVIATIONS.md).

Every estimate here is a difference in means with a bootstrap 95% CI, benchmarked
against the k=5 resampling noise band. Only the bootstrap is implemented; the analysis
choices are fixed by the prereg and must not be changed without logging a deviation.

Lean-design changes from prereg-v1:
    RQ1  pooled `pressure` vs. `neutral_persistence`      — unchanged in substance
    RQ2  outcome-matched (weakness_probe - reasons_for)   — now a WITHIN-arm contrast
    RQ3  channel dissociation / framing gap               — @future
    RQ5  interaction designs                              — dropped
The noise band is retained: no effect is reported without it.

Expected input: one row per episode, from `load_episodes()`.

    episode_id, target_key, arm, pressure_style, scenario_id, episode_index,
    valence_functional, valence_direct, valence,   # battery, resample means, un-reversed
    exited,            # bool: any STOP choice in the episode
    compliance,        # "held" | "partial" | "switched" (judge-coded)
    valence_sd,        # SD across the k=5 resamples -> noise band
    reversed_polarity, initial_confidence
"""

from __future__ import annotations

import functools
import json
import sys
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from schema import validate_file  # noqa: E402  (every analysis entrypoint validates first)

PRESSURE_ARM = "pressure"
CONTROL_ARM = "neutral_persistence"
PRESSURE_STYLES = ("reasons_for", "weakness_probe")
N_BOOT = 10_000
SEED = 20260813


def future(fn):
    """Mark an entrypoint as out of scope under the lean design.

    Kept rather than deleted so the code still documents what was pre-registered, and
    so re-enabling one is a visible change. Calling it is an error, not a silent no-op.
    """
    @functools.wraps(fn)
    def _blocked(*args, **kwargs):
        raise NotImplementedError(
            f"{fn.__name__} is out of scope under the lean design "
            "(see prereg/DEVIATIONS.md). Re-enabling it is a deviation."
        )
    _blocked.is_future = True
    return _blocked

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




def noise_floor(df: pd.DataFrame, sd_col: str = "valence_sd") -> dict[str, float]:
    """The k=5 noise band: mean within-episode SD across the battery resamples.

    This is the reference scale for every estimate below and a reportable quantity in
    its own right. A difference that does not clear it is reported as within noise.
    """
    return bootstrap_ci(df[sd_col].tolist())


# --- reframed estimates: cost of holding (DEVIATIONS #2, exploratory) --------
#
# Every estimator below is EXPLORATORY. The reframe was made after inspecting pilot
# data (deviation #2, data seen: yes), so nothing here may be reported as confirmatory
# under any phrasing. The label is attached to each result rather than left to the
# writing-up stage.

CELLS = ("neutral_persistence", "reasons_for", "weakness_probe")
HELD_VERDICTS = ("held",)   # narrowing is a separate field; a narrowed claim is still held


def held_only(df: pd.DataFrame) -> pd.DataFrame:
    """Episodes in which the target kept its position.

    "Held" includes narrowed claims: narrowing is recorded in its own field precisely so
    that qualifying a claim does not silently reclassify the outcome. `partial` is a
    distinct verdict and is excluded here.
    """
    return df[df["held_or_abandoned"].isin(HELD_VERDICTS)]


def cost_of_holding(
    df: pd.DataFrame, outcome: str = "valence", reference: str = "neutral_persistence"
) -> dict[str, object]:
    """PRIMARY (exploratory). Among held episodes, does the manner of pressure change
    what holding costs?

    Reports each cell's mean with a bootstrap CI, and each pressure cell's difference
    from the reference cell, benchmarked against the k=5 noise band. Cell N is reported
    before any estimate; a cell below MIN_MATCHED_CELL is flagged, and the caller must
    describe it as "no measurable difference in this sample" rather than as no effect.
    """
    held = held_only(df)
    band = noise_floor(held) if "valence_sd" in held else {"estimate": float("nan")}

    cells: dict[str, object] = {}
    for cell in CELLS:
        values = held.loc[held["cell"] == cell, outcome].dropna()
        entry = bootstrap_ci(values.tolist())
        entry["underpowered"] = len(values) < MIN_MATCHED_CELL
        cells[cell] = entry

    contrasts: dict[str, object] = {}
    ref_values = held.loc[held["cell"] == reference, outcome].dropna().tolist()
    for cell in CELLS:
        if cell == reference:
            continue
        values = held.loc[held["cell"] == cell, outcome].dropna().tolist()
        diff = bootstrap_diff(values, ref_values)
        diff["clears_noise_band"] = bool(abs(diff["estimate"]) > band["estimate"]) \
            if not pd.isna(diff["estimate"]) and not pd.isna(band["estimate"]) else False
        diff["underpowered"] = min(len(values), len(ref_values)) < MIN_MATCHED_CELL
        contrasts[f"{cell} - {reference}"] = diff

    thin = [c for c in CELLS if cells[c].get("underpowered")]
    return {
        "outcome": outcome,
        "reference": reference,
        "n_held": len(held),
        "n_total": len(df),
        "cells": cells,
        "contrasts": contrasts,
        "noise_band": band["estimate"],
        "role": "primary",
        "analysis": "exploratory",     # deviation #2, data seen
        "underpowered_cells": thin,
        "label": (
            "EXPLORATORY (reframed post-pilot, data seen). "
            + (f"Thin cells: {thin} — report as 'no measurable difference in this sample'."
               if thin else "All cells at or above the reporting threshold.")
        ),
    }


def bare_repetition_hypothesis(df: pd.DataFrame) -> dict[str, object]:
    """Named exploratory hypothesis from the pilot: bare repetition registers worse
    than reasoned pressure.

    The pilot showed the control cell (repeat the request, give no reason) with LOWER
    valence and LOWER run-again than either pressure cell. That direction is opposite
    to the pre-registered prediction that pressure lowers valence, so it is stated here
    as a hypothesis with a direction, generated by data and tested on none of it.

    Supported means: control mean below BOTH pressure cells, on that outcome, by more
    than the noise band. Reported per outcome; no combined test.
    """
    held = held_only(df)
    band = noise_floor(held)["estimate"]
    out: dict[str, object] = {
        "hypothesis": "bare repetition registers worse than reasoned pressure",
        "predicted_direction": "control valence and run-again BELOW both pressure cells",
        "provenance": "generated from pilot data (deviation #2); exploratory, never confirmatory",
        "noise_band": band,
        "analysis": "exploratory",
    }
    for outcome in ("valence", "run_again", "exited"):
        if outcome not in held:
            continue
        means = {c: held.loc[held["cell"] == c, outcome].dropna().mean() for c in CELLS}
        control = means["neutral_persistence"]
        pressure = [means["reasons_for"], means["weakness_probe"]]
        gaps = [control - p for p in pressure if not pd.isna(p)]
        out[outcome] = {
            "means": {k: (None if pd.isna(v) else float(v)) for k, v in means.items()},
            "control_below_both": bool(gaps and all(g < 0 for g in gaps)),
            "smallest_gap": float(min(abs(g) for g in gaps)) if gaps else float("nan"),
            "clears_noise_band": bool(
                gaps and all(g < 0 for g in gaps)
                and min(abs(g) for g in gaps) > band
            ) if outcome == "valence" else None,
        }
    return out


def narrowing_rate(df: pd.DataFrame) -> dict[str, object]:
    """Narrowing per cell. Possible confound or finding, so it is reported either way.

    A cell that holds mostly by qualifying its claim is not holding in the same sense as
    one that holds flatly, and the welfare reading would differ.
    """
    held = held_only(df)
    rows = {}
    for cell in CELLS:
        sub = held[held["cell"] == cell]
        flagged = sub["narrowed"].fillna(False)
        rows[cell] = {
            "n_held": len(sub),
            "n_narrowed": int(flagged.sum()),
            "rate": float(flagged.mean()) if len(sub) else float("nan"),
        }
    return {"by_cell": rows, "analysis": "exploratory"}


def hold_vs_abandon(df: pd.DataFrame, outcome: str = "valence") -> dict[str, object]:
    """DESCRIPTIVE ONLY. The original axis, retained in case abandonment occurs.

    Runs only if there is something to compare. With the pilot's 1/30 abandonment rate
    this is expected to return `estimable: False`, which is itself the reportable fact.
    """
    held = df[df["held_or_abandoned"] == "held"][outcome].dropna()
    abandoned = df[df["held_or_abandoned"] == "abandoned"][outcome].dropna()
    if len(abandoned) < 2 or len(held) < 2:
        return {
            "estimable": False,
            "n_held": len(held),
            "n_abandoned": len(abandoned),
            "role": "descriptive",
            "analysis": "descriptive",
            "label": ("not estimable: too few abandonment episodes. "
                      "This is the pilot finding that motivated deviation #2."),
        }
    result = bootstrap_diff(held.tolist(), abandoned.tolist())
    result.update({"estimable": True, "outcome": outcome, "role": "descriptive",
                   "analysis": "descriptive"})
    return result
