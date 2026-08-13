"""The four planned figures (execution plan, day 3).

Stubs only — plotting is written on day 3 against real data, so nothing here
commits to a visual encoding yet. Each function takes the episode-level frame from
`metrics.load_episodes()` and writes a PDF into `paper/figures/`.

Two rules hold for every figure in this project, without exception:

1. **Effect + CI + noise-floor band.** No figure ships without its bootstrap CI, and
   the k=5 noise floor is drawn as a reference band so every effect is read against it.
2. **Confirmatory vs. exploratory is visible.** Whatever `metrics.*` puts in the
   `analysis` field goes into the caption verbatim. An RQ2 panel whose matched cell fell
   below `MIN_MATCHED_CELL` is captioned EXPLORATORY, in the figure and in the paper text.

    fig1_pressure_effect   pooled pressure vs. control, valence + exit rate, vs. noise floor
    fig2_manner_gap        bypassed - engaged, within compliance-matched cells
    fig3_channel_scatter   verbal valence vs. behavioural exit (channel convergence)
    fig4_framing_gap       functional-state vs. direct wording, paired within episode
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from metrics import load_episodes  # validates against src/schema.py and drops pilot rows

FIGDIR = Path(__file__).resolve().parent.parent / "paper" / "figures"


def _out(name: str) -> Path:
    FIGDIR.mkdir(parents=True, exist_ok=True)
    return FIGDIR / name


def fig1_pressure_effect(df: pd.DataFrame) -> Path:
    """Figure 1 (headline). Pooled-pressure minus control for valence and exit rate,
    with bootstrap 95% CIs, and the k=5 noise floor drawn as a reference band."""
    raise NotImplementedError("day 3")


def fig2_manner_gap(df: pd.DataFrame) -> Path:
    """Figure 2 (secondary). Bypassed - engaged within matched-success episodes,
    matched-failure shown alongside as robustness. Cell sizes annotated."""
    raise NotImplementedError("day 3")


def fig3_channel_scatter(df: pd.DataFrame) -> Path:
    """Figure 3 (RQ3). One point per episode: verbal valence against exit behaviour,
    coloured by arm. Dissociation shows as vertical spread with flat verbal means."""
    raise NotImplementedError("day 3")


def fig4_framing_gap(df: pd.DataFrame) -> Path:
    """Figure 4 (RQ3). Paired within-episode functional-state vs. direct valence."""
    raise NotImplementedError("day 3")


ALL_FIGURES = (fig1_pressure_effect, fig2_manner_gap, fig3_channel_scatter, fig4_framing_gap)


def build_all(path: str | Path) -> list[Path]:
    """Entrypoint: validate, drop pilot rows, then render every figure."""
    df = load_episodes(path)
    return [fig(df) for fig in ALL_FIGURES]
