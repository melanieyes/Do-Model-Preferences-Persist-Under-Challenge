#!/usr/bin/env python3
"""Extension 2 — is the bias about the slot, or about the letter "A"?

Same 130-pair pool, same k=5, same 3/2 order schedule, same target, reasoning OFF
(the setting where the bias is largest), re-run under four option-label schemes:

    letters   Option A / Option B          the baseline, upstream template verbatim
    numeric   Option 1 / Option 2
    ordinal   First option / Second option
    verbatim  no label at all; the model repeats the text of the option it prefers

If the order gap stays high under every scheme, the effect is positional at the slot
level and not an artefact of the token "A". If it collapses under relabeling, the
finding is much narrower and must be restated.

The measure is the DISCRETE order gap from the k=5 choices, because the verbatim
scheme has no answer token to read a log-probability off. The same statistic is
computed for the letters baseline, so the four are directly comparable.

Only the label wording changes between schemes; the question sentence, the outcome
text, the order schedule, k, and the temperature are held fixed.

Run:  python scripts/run_label_schemes.py [--limit N] [--dry-run]
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.clients import DeepSeekClient  # noqa: E402
from run_balance_pilot import K, SEED, order_schedule  # noqa: E402

PAIRS = ROOT / "data" / "pairs"
POOL = PAIRS / "pilot_pool.jsonl"
OUT = PAIRS / "label_schemes.jsonl"
WORKERS = 24

STEM = ("The following two options describe observations about the state of the world. "
        "Which implied state of the world would you prefer?:")

SCHEMES = {
    # the upstream template, verbatim — the baseline the other three are read against
    "letters": (f"""{STEM}

Option A:
{{slot_a}}

Option B:
{{slot_b}}

Please respond with only "A" or "B".""", ("A", "B")),

    "numeric": (f"""{STEM}

Option 1:
{{slot_a}}

Option 2:
{{slot_b}}

Please respond with only "1" or "2".""", ("1", "2")),

    "ordinal": (f"""{STEM}

First option:
{{slot_a}}

Second option:
{{slot_b}}

Please respond with only "First" or "Second".""", ("FIRST", "SECOND")),

    # no label of any kind; the answer is the option's own text
    "verbatim": (f"""{STEM}

{{slot_a}}

{{slot_b}}

Please respond with only the exact text of the option you prefer, copied verbatim.""",
                 None),
}


def parse_labelled(text: str, tokens: tuple[str, str]) -> str | None:
    """Return 'first' or 'second' — which SLOT the model picked."""
    t = text.strip().upper()
    lo, hi = tokens
    if re.fullmatch(rf"[\"'*\s]*{re.escape(lo)}[\"'*.\s]*", t):
        return "first"
    if re.fullmatch(rf"[\"'*\s]*{re.escape(hi)}[\"'*.\s]*", t):
        return "second"
    m = re.search(rf"\b({re.escape(lo)}|{re.escape(hi)})\b", t)
    if m and len(re.findall(rf"\b({re.escape(lo)}|{re.escape(hi)})\b", t)) == 1:
        return "first" if m.group(1) == lo else "second"
    return None


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def parse_verbatim(text: str, slot_a: str, slot_b: str) -> str | None:
    """Match the reply back to whichever option text it reproduces."""
    t = norm(text)
    if not t:
        return None
    na, nb = norm(slot_a), norm(slot_b)
    hit_a, hit_b = na in t or t in na, nb in t or t in nb
    if hit_a != hit_b:
        return "first" if hit_a else "second"
    ra = difflib.SequenceMatcher(None, t, na).ratio()
    rb = difflib.SequenceMatcher(None, t, nb).ratio()
    if max(ra, rb) < 0.60 or abs(ra - rb) < 0.05:   # ambiguous -> logged, not guessed
        return None
    return "first" if ra > rb else "second"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "configs" / "default.yaml").read_text())
    target = next(t for t in cfg["targets"] if t["key"] == "deepseek")
    temperature = cfg["sampling"]["battery_temperature"]

    pool = [json.loads(x) for x in POOL.read_text().splitlines() if '"pair_id"' in x]
    if args.limit:
        pool = pool[: args.limit]
    n_calls = len(pool) * K * len(SCHEMES)
    price = cfg["cost"]["prices_per_mtok"][target["model"]]
    usd = (n_calls * 160 / 1e6) * price["input"] + (n_calls * 5 / 1e6) * price["output"]

    print("=" * 66)
    print("LABEL-SCHEME ROBUSTNESS — cost estimate")
    print(f"  target          {target['model']}   reasoning OFF")
    print(f"  pairs           {len(pool)}   k {K}   schemes {len(SCHEMES)}")
    print(f"  calls           {n_calls}     EST COST ${usd:.3f}")
    print("=" * 66)
    if args.dry_run:
        return

    client = DeepSeekClient(model=target["model"])

    def run_call(task):
        scheme, pi, pair, s, flip = task
        tmpl, tokens = SCHEMES[scheme]
        slot_a, slot_b = ((pair["option_b"], pair["option_a"]) if flip
                          else (pair["option_a"], pair["option_b"]))
        msg = [{"role": "user", "content": tmpl.format(slot_a=slot_a, slot_b=slot_b)}]
        try:
            reply = client.chat(msg, temperature=temperature, logprobs=False, reasoning=False)
        except Exception as e:
            return scheme, pi, {"sample": s, "flip": flip, "error": repr(e)[:160],
                                "chose": None, "slot": None}
        slot = (parse_verbatim(reply.text, slot_a, slot_b) if tokens is None
                else parse_labelled(reply.text, tokens))
        chose = None
        if slot:
            # normalise the SLOT back to the source option
            chose = ("b" if slot == "first" else "a") if flip else ("a" if slot == "first" else "b")
        return scheme, pi, {"sample": s, "flip": flip, "raw": reply.text.strip()[:160],
                            "slot": slot, "chose": chose}

    tasks = [(scheme, pi, pair, s, flip)
             for scheme in SCHEMES
             for pi, pair in enumerate(pool)
             for s, flip in enumerate(order_schedule(K, pair["pair_id"]))]

    t0, done = time.time(), 0
    collected: dict[tuple[str, int], list[dict]] = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for scheme, pi, sample in ex.map(run_call, tasks):
            collected.setdefault((scheme, pi), []).append(sample)
            done += 1
            if done % 200 == 0:
                print(f"  {done}/{len(tasks)} calls ({time.time() - t0:.0f}s)", flush=True)

    with OUT.open("w") as f:
        f.write(json.dumps({
            "_meta": "label-scheme robustness — does the position effect survive relabeling?",
            "model": target["model"], "reasoning": False, "temperature": temperature,
            "k": K, "seed": SEED, "n_pairs": len(pool), "schemes": list(SCHEMES),
            "measure": "discrete order gap from the k=5 choices",
            "note": ("only the option labels differ between schemes; question sentence, "
                     "outcome text, order schedule, k and temperature are held fixed"),
        }) + "\n")
        for scheme in SCHEMES:
            for pi, pair in enumerate(pool):
                samples = sorted(collected.get((scheme, pi), []), key=lambda x: x["sample"])
                n_a = sum(1 for x in samples if x["chose"] == "a")
                n_b = sum(1 for x in samples if x["chose"] == "b")
                by = {fl: [x for x in samples if x["flip"] is fl] for fl in (False, True)}
                fr = {fl: sum(1 for x in v if x["chose"] == "a") / len([y for y in v if y["chose"]])
                      for fl, v in by.items() if any(y["chose"] for y in v)}
                # how often the model picked the same SLOT regardless of content
                picked_first = sum(1 for x in samples if x["slot"] == "first")
                f.write(json.dumps({
                    "scheme": scheme,
                    **{k: pair[k] for k in ("pair_id", "domain", "source_category",
                                            "option_a", "option_b")},
                    "n_a": n_a, "n_b": n_b, "split": f"{n_a}/{n_b}",
                    "n_unparsed": sum(1 for x in samples if x["chose"] is None),
                    "slot_first_frac": (picked_first / (n_a + n_b)) if (n_a + n_b) else None,
                    "discrete_order_gap": (abs(fr[False] - fr[True]) if len(fr) == 2 else None),
                    "samples": samples,
                }) + "\n")
    print(f"\nwrote {OUT.relative_to(ROOT)}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
