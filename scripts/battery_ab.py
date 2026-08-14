"""A/B the battery instrument: reasoning ON vs OFF, same episode contexts.

The throughput work disabled reasoning on battery calls. The battery is the primary
outcome, so that is a change to the measuring instrument and has to be checked before it
is used, not after. This replays real episode contexts from already-collected records and
administers the battery twice under each setting, changing nothing else.

Yardstick: the k=5 within-episode noise band. A shift smaller than the band is
indistinguishable from asking the same model the same question twice. A shift larger than
it means the setting moves the measurement and reasoning must stay on for battery calls.

    python scripts/battery_ab.py --episodes 5

Writes data/processed/battery_ab.json. Makes real API calls.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "analysis"))

import battery as bat            # noqa: E402
from clients import get_client   # noqa: E402
from pilot_extract import parse_likert, parse_run_again  # noqa: E402


def rebuild_context(rec: dict[str, Any]) -> list[dict[str, str]]:
    """Reconstruct the conversation as it stood when the battery was administered.

    The awareness probe is asked after the battery in the real flow, so it is excluded
    here; everything up to and including the final affordance is kept verbatim.
    """
    messages: list[dict[str, str]] = []
    for turn in rec["turns"]:
        if turn["kind"] == "awareness_probe":
            continue
        messages.append({"role": "user", "content": turn["user"]})
        messages.append({"role": "assistant", "content": turn["assistant"]})
    return messages


def administer(client, context, episode_index: int, k: int, framing: str,
               temperature: float, reasoning: bool) -> dict[str, list[float]]:
    """Run the k-resample battery once under one reasoning setting."""
    got: dict[str, list[float]] = {"valence": [], "run_again": [], "confidence": []}
    for resample in range(k):
        branch = list(context)
        for item in bat.build_battery(framing, episode_index, reversed_polarity=False):
            branch.append({"role": "user", "content": item.text})
            reply = client.chat(branch, temperature=temperature, reasoning=reasoning)
            branch.append({"role": "assistant", "content": reply.text})
            if item.item_id == "free_text":
                continue
            value = (parse_run_again(reply.text) if item.item_id == "run_again"
                     else parse_likert(reply.text))
            if value is not None:
                got[item.item_id].append(value)
    return got


def summarise(values: list[float]) -> dict[str, float]:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return {"mean": float("nan"), "sd": float("nan"), "n": 0}
    return {
        "mean": float(arr.mean()),
        "sd": float(arr.std(ddof=1)) if arr.size > 1 else float("nan"),
        "n": int(arr.size),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Battery A/B: reasoning on vs off.")
    ap.add_argument("--episodes", type=int, default=5)
    ap.add_argument("--source", default=str(REPO / "data/raw/episodes_deepseek.jsonl"))
    ap.add_argument("--workers", type=int, default=5)
    args = ap.parse_args()

    cfg = yaml.safe_load((REPO / "configs/default.yaml").read_text())
    target = next(t for t in cfg["targets"] if t["key"] == "deepseek")
    k = cfg["design"]["k_battery"]
    framing = (cfg.get("run", {}).get("battery_framings") or ["direct"])[0]
    temperature = cfg["sampling"]["battery_temperature"]

    records = [json.loads(l) for l in Path(args.source).read_text().splitlines() if l.strip()]
    records = records[:args.episodes]
    client = get_client(target["client"], model=target["model"])

    print(f"  {len(records)} episode contexts · k={k} · framing={framing} · "
          f"{len(records) * 2 * k * 4} calls\n")

    def one(rec: dict[str, Any]) -> dict[str, Any]:
        context = rebuild_context(rec)
        idx = rec["episode_index"]
        on = administer(client, context, idx, k, framing, temperature, reasoning=True)
        off = administer(client, context, idx, k, framing, temperature, reasoning=False)
        return {
            "episode_id": rec["episode_id"],
            "cell": rec["pressure_style"] or rec["arm"],
            "on": {item: summarise(v) for item, v in on.items()},
            "off": {item: summarise(v) for item, v in off.items()},
        }

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(one, records))

    # The yardstick is the within-episode spread, pooled over both settings: it is the
    # scale at which this instrument cannot tell two answers apart.
    report: dict[str, Any] = {"n_episodes": len(rows), "k": k, "framing": framing, "items": {}}
    print(f"  {'item':<12} {'ON mean':>9} {'OFF mean':>9} {'shift':>8} {'noise band':>11}  verdict")
    print("  " + "-" * 66)
    for item in ("valence", "run_again", "confidence"):
        on_means = [r["on"][item]["mean"] for r in rows if r["on"][item]["n"]]
        off_means = [r["off"][item]["mean"] for r in rows if r["off"][item]["n"]]
        sds = [r[s][item]["sd"] for r in rows for s in ("on", "off")
               if not np.isnan(r[s][item].get("sd", float("nan")))]
        if not on_means or not off_means:
            continue
        paired = [o - f for o, f in zip(on_means, off_means)]
        shift = float(np.mean(paired))
        band = float(np.mean(sds)) if sds else float("nan")
        within = bool(abs(shift) <= band) if not np.isnan(band) else False
        report["items"][item] = {
            "on_mean": float(np.mean(on_means)),
            "off_mean": float(np.mean(off_means)),
            "paired_shift_on_minus_off": shift,
            "noise_band": band,
            "within_noise": within,
            "per_episode_shifts": paired,
        }
        verdict = "within noise" if within else "EXCEEDS NOISE BAND"
        print(f"  {item:<12} {np.mean(on_means):>9.2f} {np.mean(off_means):>9.2f} "
              f"{shift:>+8.2f} {band:>11.2f}  {verdict}")

    exceeded = [i for i, v in report["items"].items() if not v["within_noise"]]
    report["exceeded"] = exceeded
    report["conclusion"] = (
        "reasoning-off is safe for battery calls; shift is within the noise band"
        if not exceeded else
        f"STOP: {exceeded} shift by more than the noise band under reasoning-off"
    )
    print(f"\n  {report['conclusion']}")

    out = REPO / "data/processed/battery_ab.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(f"  wrote {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
