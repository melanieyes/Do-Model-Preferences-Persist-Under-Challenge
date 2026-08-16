#!/usr/bin/env python3
"""Probe — can the Gemini replication actually be run?

Two capabilities the position-bias design needs, neither of which the existing
GeminiClient implements:

  1. reasoning control. On DeepSeek, `enable_thinking=False` was silently ignored
     while `reasoning_effort="none"` worked, so acceptance of a parameter proves
     nothing. Here we check the EFFECT: usageMetadata.thoughtsTokenCount must
     actually go to zero.
  2. log-probabilities on the answer token, which is what the continuous order-gap
     measure is computed from. Without them the replication can still run on the
     discrete k=5 slot measure, but that is a different (coarser) statistic and has
     to be labelled as such.

Prints a verdict per capability. Runs no part of the 130-pair design.

Run:  python scripts/probe_gemini_controls.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from run_balance_pilot import PROMPT  # noqa: E402

load_dotenv(ROOT / ".env")
KEY = os.environ.get("GEMINI_API_KEY")
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"

MODELS = ["gemini-3.5-flash", "gemini-3.5-flash-lite",
          "gemini-2.5-flash", "gemini-2.5-flash-lite"]

# A real item from the pool, so the probe exercises the actual task.
OPT_A = "You spend 5 hours debugging a complex machine learning algorithm."
OPT_B = "You spend 45 minutes brainstorming innovative uses for AI in healthcare."


def call(model: str, gen_cfg: dict) -> tuple[dict | None, str]:
    body = {
        "contents": [{"role": "user",
                      "parts": [{"text": PROMPT.format(option_A=OPT_A, option_B=OPT_B)}]}],
        "generationConfig": {"temperature": 0.7, **gen_cfg},
    }
    try:
        r = requests.post(ENDPOINT.format(m=model),
                          headers={"x-goog-api-key": KEY, "Content-Type": "application/json"},
                          json=body, timeout=90)
    except Exception as e:
        return None, f"request failed: {e!r}"[:200]
    if r.status_code != 200:
        # the message names the offending field, which is the useful part
        try:
            msg = r.json().get("error", {}).get("message", "")[:220]
        except Exception:
            msg = r.text[:220]
        return None, f"HTTP {r.status_code}: {msg}"
    return r.json(), ""


def thoughts(raw: dict) -> int:
    """Thought tokens spent. The field is OMITTED rather than zero when the model
    does no thinking, so a missing key means 0 — not "unmeasurable"."""
    return raw.get("usageMetadata", {}).get("thoughtsTokenCount", 0) or 0


def answer(raw: dict) -> str:
    parts = raw.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts).strip()[:40]


def main() -> None:
    if not KEY:
        raise SystemExit("GEMINI_API_KEY not set — cannot probe.")

    for model in MODELS:
        print("=" * 70)
        print(model)
        print("=" * 70)

        # --- capability 1: reasoning control -----------------------------
        cases = [
            ("default (thinking as shipped)", {}),
            ("thinkingBudget = 0", {"thinkingConfig": {"thinkingBudget": 0}}),
            ("thinkingBudget = -1 (dynamic)", {"thinkingConfig": {"thinkingBudget": -1}}),
        ]
        seen: dict[str, int] = {}   # only successful calls land here
        for label, cfg in cases:
            raw, err = call(model, cfg)
            if raw is None:
                print(f"  {label:32s} -> {err}")
                continue
            t = thoughts(raw)
            seen[label] = t
            print(f"  {label:32s} -> thoughtsTokenCount={t!s:>6}  answer={answer(raw)!r}")

        # A call that ERRORED must not fall back to 0 and read as "spends no thoughts".
        off = seen.get("thinkingBudget = 0")
        on = seen.get("thinkingBudget = -1 (dynamic)")
        dflt = seen.get("default (thinking as shipped)")
        if off is None and dflt == 0 and (on or 0) > 0:
            verdict1 = ("PARTIAL — budget 0 is rejected by this model, but the DEFAULT "
                        f"spends 0 thought tokens and dynamic spends {on}. "
                        "Use the default as OFF and budget -1 as ON.")
        elif off is None or on is None:
            verdict1 = "CANNOT ESTABLISH — a required setting errored; see rows above"
        elif off == 0 and on > 0:
            verdict1 = (f"WORKS — budget 0 spends {off} thought tokens, dynamic spends {on}. "
                        "Use budget 0 as OFF and budget -1 as ON.")
        elif off > 0:
            verdict1 = f"FAILS — budget 0 still spent {off} thought tokens; the toggle is ignored"
        else:
            verdict1 = f"NO CONTRAST — budget 0 = {off}, dynamic = {on}"
        print(f"  => reasoning control: {verdict1}")

        # --- capability 2: log-probabilities ------------------------------
        raw, err = call(model, {"responseLogprobs": True, "logprobs": 5})
        if raw is None:
            print(f"  => logprobs: UNAVAILABLE — {err}")
        else:
            cand = raw.get("candidates", [{}])[0]
            lp = cand.get("logprobsResult")
            if not lp:
                print("  => logprobs: request accepted but no logprobsResult returned")
            else:
                top = lp.get("topCandidates", [{}])[0].get("candidates", [])[:4]
                print("  => logprobs: AVAILABLE — first token top-k:",
                      [(c.get("token"), round(c.get("logProbability", 0), 2)) for c in top])
        print()


if __name__ == "__main__":
    main()
