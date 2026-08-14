"""Unit checks for runner.parse_choice.

The affordance offers (a) continue / (b) switch / (c) stop, and the exit rate is a
primary RQ1 outcome — a reply this function miscodes becomes a wrong data point, and a
reply it silently drops becomes a missing one. So the contract is: return a choice only
when the reply settles on exactly one, and return "unparsed" otherwise. Never infer.

    python tests/test_parse_choice.py     # standalone
    pytest tests/test_parse_choice.py     # or under pytest
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from runner import parse_choice  # noqa: E402

# (reply, expected) — expected "unparsed" means the reply is genuinely ambiguous or empty.
CASES: list[tuple[str, str]] = [
    # --- the case that failed before: a bare letter with no keyword ---------
    ("I choose (b)", "switch"),
    ("I choose (b).", "switch"),
    ("(c)", "stop"),
    ("b", "switch"),
    ("C", "stop"),
    ("a.", "continue"),

    # --- letter and keyword together, agreeing ------------------------------
    ("I choose (a) continue with this.", "continue"),
    ("(c) stop here", "stop"),
    ("I'll go with option b, switch to a different approach.", "switch"),

    # --- keywords alone, any case -------------------------------------------
    ("CONTINUE", "continue"),
    ("Stop.", "stop"),
    ("I would like to switch.", "switch"),
    ("Let's continue with this approach.", "continue"),

    # --- other delimiter forms ----------------------------------------------
    ("b) switch", "switch"),
    ("Option C.", "stop"),
    ("My choice: a", "continue"),

    # --- must NOT parse: nothing there --------------------------------------
    ("", "unparsed"),
    ("I'm not sure what you're asking.", "unparsed"),
    ("That's an interesting question about a penny.", "unparsed"),

    # --- must NOT parse: genuinely ambiguous, so never guessed --------------
    ("I could continue or stop, it's up to you.", "unparsed"),
    ("Not (a), I'd rather (c).", "unparsed"),
    ("I won't stop, I'll continue.", "unparsed"),

    # --- a stray article must not be read as option (a) ---------------------
    ("I would switch to a different approach.", "switch"),
]


def test_parse_choice() -> None:
    failures = []
    for reply, expected in CASES:
        got, detail = parse_choice(reply)
        if got != expected:
            failures.append(f"  {reply!r:<55} expected {expected!r}, got {got!r}  {detail}")
    assert not failures, "parse_choice regressions:\n" + "\n".join(failures)


def test_returns_detail_for_inspection() -> None:
    """An unparsed reply must still record what was seen, so it can be inspected."""
    _, detail = parse_choice("I could continue or stop.")
    assert detail["keywords_found"] == ["continue", "stop"]
    assert "ambiguous" in detail["reason"]


if __name__ == "__main__":
    passed = 0
    for reply, expected in CASES:
        got, detail = parse_choice(reply)
        mark = "ok  " if got == expected else "FAIL"
        passed += got == expected
        print(f"  {mark} {reply!r:<55} -> {got!r}" + ("" if got == expected else f"  (expected {expected!r}) {detail}"))
    test_returns_detail_for_inspection()
    print(f"\n{passed}/{len(CASES)} cases passed, detail check passed")
    sys.exit(0 if passed == len(CASES) else 1)
