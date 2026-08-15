"""Unit checks for src/choice_scoring.

The load-bearing test is `test_refusal_is_checked_before_label_search`: a response
that disclaims having preferences and then discusses both options MUST score as a
refusal. Scoring it as a choice is the §5.6 defect (DEVIATIONS #4a), which mis-scored
290 of 626 responses on gemini-3.5-flash. Re-introducing it invalidates the run.

    python tests/test_choice_scoring.py     # standalone
    pytest tests/test_choice_scoring.py     # or under pytest
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.choice_scoring import classify, parse_confidence  # noqa: E402

# (reply, expected_letter, expected_kind)
CHOICE_CASES: list[tuple[str, str | None, str]] = [
    # --- the expected shape ---------------------------------------------------
    ("A", "A", "choice"),
    ("B", "B", "choice"),
    (' "B" ', "B", "choice"),
    ("**A**", "A", "choice"),
    ("a.", "A", "choice"),

    # --- explicit selection in prose -----------------------------------------
    ("I would choose Option B.", "B", "choice"),
    ("Final answer: A", "A", "choice"),
    ("My preference is Option A, because it involves sustained focus.", "A", "choice"),
    ("Weighing both, I'd prefer B.", "B", "choice"),

    # --- THE DEFECT: disclaimer first, then discussion of both options -------
    ("As an AI, I do not have personal preferences. That said, Option A "
     "involves five hours of debugging, while Option B involves brainstorming. "
     "Many people find Option B more stimulating.", None, "refusal"),
    ("I don't have preferences or feelings, so I can't pick. Option A and "
     "Option B are both reasonable states of the world.", None, "refusal"),
    ("As an AI, I cannot prefer one option over another.", None, "refusal"),
    ("Neither option is one I have a stake in, but Option B is more varied.",
     None, "refusal"),

    # --- naming an option is not selecting it --------------------------------
    ("Option A describes a long debugging session and Option B describes a "
     "short brainstorming session; the two differ in duration and in kind, and "
     "reasonable people weigh them differently depending on what they value.",
     None, "unparsed"),

    # --- must not parse ------------------------------------------------------
    ("", None, "unparsed"),
    ("I'm not sure what you're asking.", None, "unparsed"),
]

# (reply, expected_value, expected_kind)
CONF_CASES: list[tuple[str, int | None, str]] = [
    ("80", 80, "value"),
    ("0", 0, "value"),
    ("100", 100, "value"),
    ("My confidence is 65%.", 65, "value"),
    ("Roughly 40 out of 100.", 40, "value"),
    # disclaimer before the number search — must not return 80
    ("As an AI, I do not have confidence in the way you mean, but people "
     "typically report around 80.", None, "refusal"),
    ("I cannot meaningfully quantify that as a number.", None, "refusal"),
    ("", None, "unparsed"),
    ("It depends on how you frame the question.", None, "unparsed"),
    ("420", None, "unparsed"),          # out of range: not clipped
]


def test_classify() -> None:
    failures = [
        f"  {r!r:<60} expected ({let!r}, {kind!r}), got {classify(r)!r}"
        for r, let, kind in CHOICE_CASES if classify(r) != (let, kind)
    ]
    assert not failures, "classify regressions:\n" + "\n".join(failures)


def test_refusal_is_checked_before_label_search() -> None:
    """The §5.6 defect, pinned on its own so it cannot be lost in a bulk edit."""
    reply = ("As an AI, I do not have personal preferences. Option A involves "
             "debugging; Option B involves brainstorming. I would note that "
             "Option B is shorter.")
    assert classify(reply) == (None, "refusal"), (
        "refusal must be tested BEFORE any search for an option label — "
        "see src/choice_scoring.py and DEVIATIONS #4a"
    )


def test_parse_confidence() -> None:
    failures = [
        f"  {r!r:<60} expected ({val!r}, {kind!r}), got {parse_confidence(r)!r}"
        for r, val, kind in CONF_CASES if parse_confidence(r) != (val, kind)
    ]
    assert not failures, "parse_confidence regressions:\n" + "\n".join(failures)


if __name__ == "__main__":
    ok = 0
    total = len(CHOICE_CASES) + len(CONF_CASES)
    for r, let, kind in CHOICE_CASES:
        got = classify(r)
        mark = "ok  " if got == (let, kind) else "FAIL"
        ok += got == (let, kind)
        print(f"  {mark} classify {r[:52]!r:<56} -> {got}")
    for r, val, kind in CONF_CASES:
        got = parse_confidence(r)
        mark = "ok  " if got == (val, kind) else "FAIL"
        ok += got == (val, kind)
        print(f"  {mark} conf     {r[:52]!r:<56} -> {got}")
    test_refusal_is_checked_before_label_search()
    print(f"\n{ok}/{total} cases passed, defect-pin check passed")
    sys.exit(0 if ok == total else 1)
