"""Actual spend from recorded token usage.

Every call's `usage` block is stored on the turn/battery row it produced, so this is
measured, not estimated. DeepSeek prices cache hits and misses differently and the
episodes reuse a long growing prefix, so hits and misses are billed separately here
rather than assuming the conservative miss rate throughout.

    python analysis/spend.py data/raw/episodes_deepseek.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent

# DeepSeek cache-hit input rates (configs/default.yaml records the miss rate).
CACHE_HIT_PER_MTOK = {"deepseek-v4-pro": 0.003625, "deepseek-v4-flash": 0.0028}


def usage_blocks(rec: dict) -> list[dict]:
    blocks = [t["usage"] for t in rec.get("turns", []) if t.get("usage")]
    blocks += [b["usage"] for b in rec.get("battery", []) if b.get("usage")]
    return blocks


def summarise(path: Path, cfg: dict) -> dict:
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not records:
        return {}
    model = records[0]["model"]
    price = cfg["cost"]["prices_per_mtok"].get(model, {"input": 0.0, "output": 0.0})
    hit_price = CACHE_HIT_PER_MTOK.get(model, price["input"])

    hit = miss = out = calls = 0
    for rec in records:
        for u in usage_blocks(rec):
            calls += 1
            out += u.get("completion_tokens", 0) or 0
            h = u.get("prompt_cache_hit_tokens")
            m = u.get("prompt_cache_miss_tokens")
            if h is None and m is None:      # provider did not break it out
                miss += u.get("prompt_tokens", 0) or 0
            else:
                hit += h or 0
                miss += m or 0

    usd = hit / 1e6 * hit_price + miss / 1e6 * price["input"] + out / 1e6 * price["output"]
    return {
        "episodes": len(records), "model": model, "calls": calls,
        "input_cache_hit": hit, "input_cache_miss": miss, "output": out,
        "usd": usd,
        # Judge calls go through a different provider and are not in these records.
        "note": "target-model calls only; judge (Gemini) calls are billed separately",
    }


def main() -> None:
    cfg = yaml.safe_load((REPO / "configs/default.yaml").read_text())
    paths = [Path(a) for a in sys.argv[1:]] or [REPO / "data/raw/episodes_deepseek.jsonl"]
    for path in paths:
        s = summarise(path, cfg)
        if not s:
            print(f"{path}: no records")
            continue
        print(f"\n  ACTUAL SPEND — {path.name}")
        print("  " + "-" * 58)
        print(f"  model                 {s['model']}")
        print(f"  episodes              {s['episodes']}")
        print(f"  model calls           {s['calls']:,}")
        print(f"  input (cache hit)     {s['input_cache_hit']:,} tok")
        print(f"  input (cache miss)    {s['input_cache_miss']:,} tok")
        print(f"  output                {s['output']:,} tok")
        print(f"  ACTUAL API SPEND      ${s['usd']:,.4f}")
        print(f"  ({s['note']})")
        print("  " + "-" * 58)


if __name__ == "__main__":
    main()
