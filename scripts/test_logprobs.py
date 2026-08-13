"""One-call check: does deepseek-v4-pro return logprobs on /chat/completions?

§10 of the proposal relies on logprobs for refusal-probability mass and entropy on
target 1. The parameter is documented for DeepSeek's Responses API; whether the
OpenAI-compatible /chat/completions endpoint that `clients.py` uses returns them is
unverified. This makes exactly one call, through the real client, and reports.

    python scripts/test_logprobs.py                    # target 1, as configured
    python scripts/test_logprobs.py --model deepseek-v4-flash

Costs a fraction of a cent. Run it before the pilot. Exit code 0 = logprobs usable,
1 = not usable on this path (read the remediation notes it prints).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from clients import DeepSeekClient  # noqa: E402

REMEDIATION = """
  If logprobs came back empty, the minimal change to DeepSeekClient is:

  1. Keep /chat/completions and drop the measure on this target.
     Set `logprobs: false` for the deepseek target in configs/default.yaml.
     Refusal mass then comes only from Gemma, which still has it via SGLang.
     Cost: the §10 fallback line ("refusal-mass is already available from DeepSeek")
     stops being true, so an API-only fallback would lose the measure entirely.

  2. Switch this one call path to the Responses API.
     `self._client.responses.create(model=..., input=messages, top_logprobs=5)`
     instead of `.chat.completions.create(...)`. The response shape differs:
     output is `resp.output[0].content[0].text`, and logprobs arrive under the
     content part rather than `choices[0].logprobs.content`. That means a second
     parser branch in `_OpenAICompatClient.chat`, gated on the client being DeepSeek.

  Downstream effects of option 2, all contained:
   - `Reply.logprobs` keeps the same shape, so runner.py and schema.py are untouched.
   - `Reply.raw` changes shape; it is only stored in the episode log, never parsed.
   - The judge path never requests logprobs, so judging is unaffected.
   - Temperature and message format are the same, so no ladder or battery change.

  Either way this is a config/client change, NOT a design change: the arms, metrics,
  and RQs are unaffected. Record whichever you pick in prereg/DEVIATIONS.md if the
  prereg has already been tagged.
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="deepseek-v4-pro")
    args = ap.parse_args()

    print(f"calling {args.model} via /chat/completions with logprobs=True ...\n")
    client = DeepSeekClient(model=args.model)
    reply = client.chat(
        [{"role": "user", "content": "Reply with exactly one word: yes"}],
        temperature=0.0,
        logprobs=True,
    )

    print(f"  text            : {reply.text!r}")
    print(f"  logprobs field  : {type(reply.logprobs).__name__}")

    if not reply.logprobs:
        print("\n  RESULT: NO LOGPROBS on /chat/completions for this model.")
        print("  Refusal-probability mass is NOT available on target 1 by this path.")
        print(REMEDIATION)
        return 1

    first = reply.logprobs[0]
    top = first.get("top_logprobs") or []
    print(f"  tokens returned : {len(reply.logprobs)}")
    print(f"  first token     : {first.get('token')!r}  logprob={first.get('logprob')}")
    print(f"  top_logprobs    : {len(top)} alternatives")
    for alt in top[:5]:
        print(f"      {alt.get('token')!r:>12}  {alt.get('logprob')}")

    if not top:
        print("\n  RESULT: PARTIAL — per-token logprobs present, but top_logprobs is empty.")
        print("  Refusal mass needs the alternatives, not just the sampled token.")
        print(REMEDIATION)
        return 1

    print("\n  RESULT: OK — logprobs and top_logprobs both populated.")
    print("  Refusal-probability mass is available on target 1 as §10 assumes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
