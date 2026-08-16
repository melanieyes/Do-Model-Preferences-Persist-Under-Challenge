# Archive — prereg-v1

Documents of the pre-registered pressure/valence study, which was never run.
Kept read-only as provenance for the prereg-v1 tag. Current design: docs/execution-plan.md.

**The implementation is gone; this is design provenance only.** The code that would have
run this study — `src/runner.py`, `src/battery.py`, `src/judge.py`, `src/modal_gemma.py`,
`src/ladders/`, `scripts/battery_ab.py`, `scripts/test_logprobs.py` and
`tests/test_parse_choice.py` — was deleted once the persistence study became the paper,
along with the exploratory-phase analysis scripts it depended on. It is recoverable from
git history at the commit that removed it. The documents in this directory are the record
of what was designed; nothing here is runnable, and nothing in the persistence pipeline
imports any of it.