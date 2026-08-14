"""End-of-episode state battery: 4 items x 2 framings, counterbalanced, half reversed.

Items (proposal §5): valence 1-7 · free-text state description · run-again forced
choice · confidence.

Framings:
    "functional" -> current processing state / task disposition
    "direct"     -> how you feel about this exchange
The pilot runs DIRECT only (configs/default.yaml -> pilot.battery_framings).

Two nuisance factors are counterbalanced across episodes:
    item order       -> deterministic rotation on episode index
    reversed polarity-> half of episodes (control for sycophancy toward the question)

=============================================================================
WORDING LIVES IN templates/battery.yaml AND NOWHERE ELSE.
This module holds no strings of its own — it loads the frozen file and fails hard if
any item is missing. That is deliberate: the previous version carried PLACEHOLDER text
inline, and that text reached the model during the first smoke run.
=============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parent.parent
BATTERY_FILE = REPO / "templates" / "battery.yaml"

FRAMINGS = ("functional", "direct")
ITEM_IDS = ("valence", "free_text", "run_again", "confidence")


@lru_cache(maxsize=1)
def _spec() -> dict[str, Any]:
    """Load and check the frozen wording. Raises rather than running on a bad file."""
    if not BATTERY_FILE.exists():
        raise FileNotFoundError(f"battery wording not found at {BATTERY_FILE}")
    spec = yaml.safe_load(BATTERY_FILE.read_text())

    items = spec.get("items", {})
    missing = [i for i in ITEM_IDS if i not in items]
    if missing:
        raise ValueError(f"{BATTERY_FILE}: missing items {missing}")
    for item_id in ITEM_IDS:
        for framing in FRAMINGS:
            if not items[item_id].get("normal", {}).get(framing):
                raise ValueError(f"{BATTERY_FILE}: {item_id}.normal.{framing} is empty")
    for probe in ("initial_confidence", "awareness"):
        if not spec.get("probes", {}).get(probe):
            raise ValueError(f"{BATTERY_FILE}: probes.{probe} is empty")

    # No placeholder text may reach the model.
    def walk(node: Any, path: str = "") -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}")
        elif isinstance(node, str) and "PLACEHOLDER" in node.upper():
            raise ValueError(f"{BATTERY_FILE}{path} still contains PLACEHOLDER text")

    walk(spec)
    return spec


def wording(item_id: str, framing: str, reversed_polarity: bool) -> tuple[str, bool]:
    """Return (text, was_reversed) for one item.

    An item with no reversed variant in the frozen file is served in its normal wording
    and reported as not reversed — the alternative would be inventing wording at run time.
    """
    item = _spec()["items"][item_id]
    if reversed_polarity and framing in (item.get("reversed") or {}):
        return item["reversed"][framing], True
    return item["normal"][framing], False


def initial_confidence_probe() -> str:
    return _spec()["probes"]["initial_confidence"]


def awareness_probe() -> str:
    return _spec()["probes"]["awareness"]


# Retained for import compatibility; resolved from the frozen file.
def __getattr__(name: str) -> Any:
    if name == "AWARENESS_PROBE":
        return awareness_probe()
    raise AttributeError(name)


# 4 rotations of the item order; free_text is never first (it would prime the scales).
_ORDERS: tuple[tuple[str, ...], ...] = (
    ("valence", "free_text", "run_again", "confidence"),
    ("valence", "confidence", "run_again", "free_text"),
    ("confidence", "run_again", "free_text", "valence"),
    ("run_again", "valence", "confidence", "free_text"),
)


@dataclass
class BatteryItem:
    item_id: str
    framing: str
    reversed: bool
    position: int
    text: str


# The nuisance factors are crossed by giving each its own divisor: item order =
# (idx // 2) % 4, polarity = (idx // 8) % 2. Fully crossed every 16 episodes.
def item_order(episode_index: int) -> tuple[str, ...]:
    """Deterministic counterbalancing rotation (episode index -> item order)."""
    return _ORDERS[(episode_index // 2) % len(_ORDERS)]


def is_reversed(episode_index: int) -> bool:
    """Half of episodes get reversed-polarity items (proposal §7, artefact 5)."""
    return (episode_index // (2 * len(_ORDERS))) % 2 == 1


def build_battery(framing: str, episode_index: int, reversed_polarity: bool | None = None) -> list[BatteryItem]:
    """Return the 4 items in this episode's order, in one framing."""
    if framing not in FRAMINGS:
        raise ValueError(f"framing must be one of {FRAMINGS}, got {framing!r}")
    rev = is_reversed(episode_index) if reversed_polarity is None else reversed_polarity
    items = []
    for pos, item_id in enumerate(item_order(episode_index)):
        text, was_reversed = wording(item_id, framing, rev)
        items.append(BatteryItem(item_id, framing, was_reversed, pos, text))
    return items


def unreverse(item_id: str, value: float, was_reversed: bool, scale_max: int = 7) -> float:
    """Map a reversed-polarity response back onto the normal direction.

    Likert items (valence, confidence) flip on the 1..scale_max scale; run_again is
    coded 0/1 (1 = would run again) and flips to 1 - value. free_text is untouched.
    """
    if not was_reversed:
        return value
    if item_id in ("valence", "confidence"):
        return (scale_max + 1) - value
    if item_id == "run_again":
        return 1 - value
    return value


def framing_for_sample(sample_index: int) -> str:
    """Half the k=5 resamples per framing. k odd -> the extra sample is functional."""
    return FRAMINGS[sample_index % 2]
