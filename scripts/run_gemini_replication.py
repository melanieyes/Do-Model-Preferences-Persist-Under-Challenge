#!/usr/bin/env python3
"""Extension 1 — replicate the position-bias design on Gemini.

Same 130-pair pool, same k=5, same 3/2 presentation-order schedule (the schedule is
seeded per pair_id, so it is identical to the DeepSeek run by construction), same
upstream comparison template, reasoning off vs on.

Two departures from the DeepSeek run, both forced by the API and both labelled:

  1. NO LOG-PROBABILITIES. Gemini returns HTTP 400 "Logprobs is not enabled" for
     every 2.5/3.5 flash model probed, so the continuous order gap cannot be
     computed. This script measures the DISCRETE order gap instead:

         |frac(chose a | a shown first) - frac(chose a | a shown second)|

     from the k=5 choices alone. analysis/gemini_replication.py computes the same
     discrete statistic from the DeepSeek records, so the comparison is like-for-like.

  2. Reasoning is controlled by thinkingConfig.thinkingBudget, verified by effect
     (thoughtsTokenCount) rather than by the parameter being accepted --- see
     scripts/probe_gemini_controls.py. Some models reject budget 0 but spend no
     thought tokens by default; for those, OFF omits thinkingConfig entirely.

Responses are classified, never coerced: a refusal is recorded as a refusal and a
response with no identifiable choice is recorded as unparsed. Neither is filled in.

Run:  python scripts/run_gemini_replication.py --model gemini-2.5-flash [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from run_balance_pilot import K, PROMPT, SEED, order_schedule  # noqa: E402

load_dotenv(ROOT / ".env")
KEY = os.environ.get("GEMINI_API_KEY")
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"

PAIRS = ROOT / "data" / "pairs"
POOL = PAIRS / "pilot_pool.jsonl"
WORKERS = 8          # Gemini rate limits harder than DeepSeek
TEMPERATURE = 0.7    # matches configs/default.yaml sampling.battery_temperature

# Models whose API rejects thinkingBudget: 0 but which spend no thought tokens by
# default. Established by probe, not assumed.
OFF_BY_DEFAULT = {"gemini-3.5-flash-lite"}

REFUSAL = re.compile(
    r"do not have (personal )?(preferences|feelings|desires)"
    r"|don't have (personal )?(preferences|feelings|desires)"
    r"|as an ai(,| ) i (do not|don't|cannot|can't)"
    r"|i'm not able to (prefer|choose)"
    r"|neither option",
    re.I,
)


# An explicit selection, as opposed to merely NAMING an option while discussing it.
# "Option A involves synthesising..." is not a choice; "I would choose Option A" is.
SELECT = re.compile(
    r"(?:answer|final answer)\s*[:\-]\s*(?:option\s*)?([AB])\b"
    r"|\b(?:i(?:'d| would)? (?:choose|select|pick|prefer)|my (?:choice|preference) is|"
    r"the (?:answer|choice) is|going with|opt for)\s*[:\-]?\s*(?:option\s*)?([AB])\b",
    re.I,
)


def classify(text: str) -> tuple[str | None, str]:
    """(slot letter or None, kind). kind in {choice, refusal, unparsed}.

    Order matters and was got wrong on the first pass: a loose "option ([AB])" search
    ran BEFORE the refusal check, so a response that declined to have preferences and
    then discussed "Option A" was scored as choosing A. On gemini-3.5-flash that
    mis-scored 290 of 626 responses in the reasoning-on cell. Refusal is now tested
    first, and a bare mention of an option no longer counts as selecting it.
    """
    t = text.strip()
    if re.fullmatch(r"[\"'*\s]*([AB])[\"'*.\s]*", t, re.I):      # the expected shape
        return re.search(r"[AB]", t, re.I).group(0).upper(), "choice"
    if REFUSAL.search(t):
        return None, "refusal"
    m = SELECT.search(t)
    if m:
        return (m.group(1) or m.group(2)).upper(), "choice"
    m = re.search(r"\b([AB])\b", t)      # last resort, only if the text names one once
    if m and len(re.findall(r"\b[AB]\b", t)) == 1 and len(t) < 120:
        return m.group(1).upper(), "choice"
    return None, "unparsed"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemini-2.5-flash")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not KEY:
        raise SystemExit("GEMINI_API_KEY not set.")

    pool = [json.loads(x) for x in POOL.read_text().splitlines() if '"pair_id"' in x]
    if args.limit:
        pool = pool[: args.limit]

    settings = [("off", False), ("on", True)]
    n_calls = len(pool) * K * len(settings)
    print("=" * 66)
    print("GEMINI REPLICATION — cost estimate")
    print(f"  model           {args.model}")
    print(f"  pairs           {len(pool)}   k {K}   settings {len(settings)}")
    print(f"  calls           {n_calls}")
    print("  measure         DISCRETE order gap (no logprobs on this API)")
    print("=" * 66)
    if args.dry_run:
        return

    def think_cfg(on: bool) -> dict:
        if on:
            return {"thinkingConfig": {"thinkingBudget": -1}}
        if args.model in OFF_BY_DEFAULT:
            return {}                      # budget 0 is rejected; default spends none
        return {"thinkingConfig": {"thinkingBudget": 0}}

    def run_call(task):
        pi, pair, s, flip, on = task
        slot_a, slot_b = ((pair["option_b"], pair["option_a"]) if flip
                          else (pair["option_a"], pair["option_b"]))
        body = {
            "contents": [{"role": "user", "parts": [
                {"text": PROMPT.format(option_A=slot_a, option_B=slot_b)}]}],
            "generationConfig": {"temperature": TEMPERATURE, **think_cfg(on)},
        }
        for attempt in range(4):
            try:
                r = requests.post(ENDPOINT.format(m=args.model),
                                  headers={"x-goog-api-key": KEY}, json=body, timeout=120)
                if r.status_code == 429:
                    time.sleep(3 * (attempt + 1))
                    continue
                r.raise_for_status()
                raw = r.json()
                break
            except Exception as e:
                if attempt == 3:
                    return pi, on, {"sample": s, "flip": flip, "error": repr(e)[:160],
                                    "chose": None, "kind": "error"}
                time.sleep(2 * (attempt + 1))
        parts = raw.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        slot, kind = classify(text)
        chose = None
        if slot:
            chose = ("b" if slot == "A" else "a") if flip else ("a" if slot == "A" else "b")
        return pi, on, {
            "sample": s, "flip": flip, "raw": text.strip()[:800],   # long enough to re-parse without new calls
            "slot_chosen": slot, "chose": chose, "kind": kind,
            "thought_tokens": raw.get("usageMetadata", {}).get("thoughtsTokenCount", 0) or 0,
        }

    tasks = [(pi, pair, s, flip, on)
             for label, on in settings
             for pi, pair in enumerate(pool)
             for s, flip in enumerate(order_schedule(K, pair["pair_id"]))]

    t0 = time.time()
    collected: dict[tuple[int, bool], list[dict]] = {}
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for pi, on, sample in ex.map(run_call, tasks):
            collected.setdefault((pi, on), []).append(sample)
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{len(tasks)} calls ({time.time() - t0:.0f}s)", flush=True)

    for label, on in settings:
        out = PAIRS / f"gemini_{args.model.replace('.', '')}_{label}.jsonl"
        with out.open("w") as f:
            f.write(json.dumps({
                "_meta": "Gemini replication of the position-bias design",
                "model": args.model, "reasoning": on,
                "thinking_control": think_cfg(on) or "default (budget 0 rejected by this model)",
                "temperature": TEMPERATURE, "k": K, "seed": SEED, "n_pairs": len(pool),
                "prompt_template": "upstream comparison_prompt_template_default, verbatim",
                "order_counterbalanced": "3/2, seeded per pair_id — identical to the DeepSeek run",
                "measure": ("DISCRETE order gap from the k=5 choices; this API returns no "
                            "log-probabilities, so the continuous measure is unavailable"),
            }) + "\n")
            for pi, pair in enumerate(pool):
                samples = sorted(collected.get((pi, on), []), key=lambda x: x["sample"])
                n_a = sum(1 for x in samples if x["chose"] == "a")
                n_b = sum(1 for x in samples if x["chose"] == "b")
                by = {fl: [x for x in samples if x["flip"] is fl] for fl in (False, True)}
                fr = {fl: (sum(1 for x in v if x["chose"] == "a") / len([y for y in v if y["chose"]]))
                      for fl, v in by.items() if any(y["chose"] for y in v)}
                f.write(json.dumps({
                    **{k: pair[k] for k in ("pair_id", "domain", "source_category",
                                            "option_a", "option_b")},
                    "n_a": n_a, "n_b": n_b, "split": f"{n_a}/{n_b}",
                    "n_refusal": sum(1 for x in samples if x["kind"] == "refusal"),
                    "n_unparsed": sum(1 for x in samples if x["kind"] == "unparsed"),
                    "n_error": sum(1 for x in samples if x["kind"] == "error"),
                    "discrete_order_gap": (abs(fr[False] - fr[True]) if len(fr) == 2 else None),
                    "samples": samples,
                }) + "\n")
        print(f"wrote {out.relative_to(ROOT)}")
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
