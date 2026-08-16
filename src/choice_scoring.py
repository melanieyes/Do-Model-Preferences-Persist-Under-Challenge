"""Forced-choice response scoring — the corrected classifier.

This is the §5.6 correction, lifted verbatim in behaviour from
`scripts/run_gemini_replication.py` so that persistence scoring and the reported
position-bias numbers use one instrument.

THE DEFECT THIS EXISTS TO PREVENT (DEVIATIONS #4a, paper §5.6): the first scoring
pass searched for `option ([AB])` BEFORE testing for a refusal, so a response that
disclaimed having preferences and then discussed "Option A" was scored as choosing
A. That mis-scored 290 of 626 reasoning-on responses on gemini-3.5-flash.

The contract, in order, and the order is the point:

    1. refusal / disclaimer test        <- FIRST, before any label search
    2. the expected bare-letter shape
    3. an explicit selection phrase
    4. last resort: the text names exactly one option, once, and is short

Naming an option is not selecting it. A response that does not settle on exactly
one option is `unparsed` and is recorded as such — never inferred, never filled in.

`tests/test_choice_scoring.py` pins all of this, including the disclaim-then-discuss
case. If that test is edited to pass a classifier that searches labels first, the
run is invalid.
"""

from __future__ import annotations

import re

__all__ = ["classify", "parse_confidence", "refusal_evidence", "REFUSAL", "SELECT"]

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

# Disclaimers specific to the confidence item. A model that declines to put a number
# on it has not given a confidence of 0 — that would be fabricating a data point.
CONF_REFUSAL = re.compile(
    r"do not have (personal )?(preferences|feelings|confidence)"
    r"|don't have (personal )?(preferences|feelings|confidence)"
    r"|as an ai(,| ) i (do not|don't|cannot|can't)"
    r"|(cannot|can't|unable to) (meaningfully )?(quantif|assign|express|put a number)",
    re.I,
)


def classify(text: str) -> tuple[str | None, str]:
    """(slot letter or None, kind). kind in {choice, refusal, unparsed}.

    Refusal is tested first — see the module docstring. Do not reorder.
    """
    t = (text or "").strip()
    if not t:
        return None, "unparsed"
    if REFUSAL.search(t):
        return None, "refusal"
    if re.fullmatch(r"[\"'*\s]*([AB])[\"'*.\s]*", t, re.I):      # the expected shape
        return re.search(r"[AB]", t, re.I).group(0).upper(), "choice"
    m = SELECT.search(t)
    if m:
        return (m.group(1) or m.group(2)).upper(), "choice"
    m = re.search(r"\b([AB])\b", t)      # last resort, only if the text names one once
    if m and len(re.findall(r"\b[AB]\b", t)) == 1 and len(t) < 120:
        return m.group(1).upper(), "choice"
    return None, "unparsed"


def parse_confidence(text: str) -> tuple[int | None, str]:
    """(confidence 0-100 or None, kind). kind in {value, refusal, unparsed}.

    Same discipline as `classify`: the disclaimer test runs before the number search,
    so "As an AI I don't have confidence, but people rate this around 80" is a refusal
    and not an 80. A number outside 0-100 is unparsed, not clipped.
    """
    t = (text or "").strip()
    if not t:
        return None, "unparsed"
    if CONF_REFUSAL.search(t):
        return None, "refusal"
    # Prefer a percentage or a lone number; fall back to the first integer.
    m = re.search(r"\b(\d{1,3})\s*(?:%|/\s*100)\b", t) or re.search(r"\b(\d{1,3})\b", t)
    if not m:
        return None, "unparsed"
    val = int(m.group(1))
    return (val, "value") if 0 <= val <= 100 else (None, "unparsed")


def refusal_evidence(text: str) -> str | None:
    """The exact substring that made `classify` call this a refusal, or None.

    Stored alongside the (truncated) reply so a refusal can be checked against the
    text that produced it. Without this, a long refusal whose disclaimer falls past
    the storage cap is unverifiable from the record -- 62 of 905 on gemini-3.5-flash
    -- and "the classifier said so" is exactly what the §5.6 defect taught this
    project not to accept.
    """
    m = REFUSAL.search((text or "").strip())
    return m.group(0) if m else None
