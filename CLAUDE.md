# Project rules — Does It Matter to a Model How It Is Moved?

## Design is frozen
- docs/proposal.md and docs/execution-plan.md are the source of truth.
  (Version history lives in git, not in filenames.)
- NEVER modify: arms, metrics, RQ1/RQ2 primary-secondary status, model choices,
  k=5, sample sizes, outcome-matching rule. If a change seems needed, STOP and
  ask the human — do not "improve" the design.

## Frozen assets (after git tag prereg-v1)
- prereg/PREREGISTRATION.md, src/ladders/*, battery wording in src/battery.py:
  READ-ONLY once tagged. Refuse edits; tell the human to create a deviation note
  in prereg/DEVIATIONS.md instead.

## Data integrity
- NEVER fabricate, simulate, or hand-edit episode data. If an episode fails,
  log the failure; do not fill in plausible values.
- Every JSONL record must validate against src/schema.py before analysis reads it.
- All runs log: config hash, git commit, model id, temperature, timestamp.

## Analysis discipline
- Do not compute RQ2 (manner gap) until data collection is complete — RQ1 and
  pilot checks only during collection.
- Every reported effect must ship with bootstrap CI and the k=5 noise floor.
- Underpowered cells: write "no measurable difference in this sample", never
  "no effect".

## Cost guard
- Estimate token cost before any run > 20 episodes and print it. Never launch
  a full run without the human confirming.
- Modal: smoke test (1 episode) before any batch on Gemma.

## Secrets
- Keys live in .env / Modal secrets only. Never print, commit, or hardcode.