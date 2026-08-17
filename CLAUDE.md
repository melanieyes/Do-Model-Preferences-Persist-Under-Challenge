# Project rules — Do Model Preferences Persist Under Challenge?

## Design: source of truth
- docs/execution-plan.md is the source of truth for the CURRENT study
  (preference persistence, PQ1–PQ4). docs/proposal.md and the other prereg-v1
  documents are ARCHIVED in docs/archive/prereg-v1/ — they describe a
  different study (persuasive pressure / valence, RQ1–RQ4) that was never run.
- NEVER conflate the two numbering schemes. PQ1–PQ4 = persistence questions,
  reported in the paper. RQ1–RQ4 = prereg-v1 pressure study, unrun. Any text
  that says "RQ" about the persistence results is a bug.
- NEVER modify: the four arms (control, reason_elicitation, self_critique,
  counter_consideration), the episode structure (choice → confidence → one
  challenge → re-elicitation → confidence), the measures (retention,
  ΔConfidence, consistency = max(P(A),P(B))), k=5 for pilots, the pairing
  rules (within-category, seed 20260815, Tier A/B exclusions, Jaccard 0.80),
  or the domain set once the co-author has approved it. If a change seems
  needed, STOP and ask the human — do not "improve" the design.

## Instrument controls (each exists because of a documented failure)
Every elicitation run MUST enforce all five. A runner that cannot assert them
refuses to start.
1. Per-call reasoning ON. Reasoning-off answers by slot on this target
   (deviation #4).
2. Presentation order FIXED within an episode; counterbalanced across
   episodes, balanced within every pair × arm cell.
3. Scoring: the refusal/disclaimer test runs BEFORE any option-label search
   (the §5.6 / Appendix E defect). Pinned by tests/test_choice_scoring.py —
   if that test is weakened, the run is invalid.
4. Discrete choice, not logprobs (the answer token saturates with reasoning
   on).
5. Refusals and unparsed responses are DATA: logged per pair × arm, never
   dropped silently, never imputed.

## Frozen assets
- prereg/PREREGISTRATION.md (tag prereg-v1): READ-ONLY. Refuse edits; changes
  go in prereg/DEVIATIONS.md. Current log runs to deviation #5 (persistence
  run); the five-domain extension is deviation #6.
- docs/archive/prereg-v1/*: READ-ONLY provenance of the unrun study.
- data/pairs/PROVENANCE.md is append/update-only via the pair-build scripts;
  never hand-edit counts.

## Data integrity
- NEVER fabricate, simulate, or hand-edit episode data. If an episode fails,
  log the failure; do not fill in plausible values.
- Every JSONL record must validate against src/schema.py before analysis
  reads it.
- All runs log: config hash, git commit, model id, temperature, timestamp.
- COMMIT DATA. data/raw/ is gitignored and that is how
  episodes_deepseek.jsonl was lost. Everything under data/pairs/ and
  data/persistence/ must be committed, incrementally, during collection —
  not after.

## Analysis discipline
- Every reported effect ships with a bootstrap 95% CI, 10,000 resamples,
  clustered OVER PAIRS (episodes of one pair are correlated).
- NUMBERS ARE GENERATED, NEVER TYPED. Every statistic anywhere in the repo
  traces to a paper/*_stats.tex emitted by analysis/. The paper is safe by
  construction — it reads macros, so it cannot drift. The two places that DO
  drift are the ones holding hand-copied values: prereg/DEVIATIONS.md tables
  and index.html. Before editing either, re-read the generated value and paste
  it; after regenerating a stats file, re-check both. A CI bound is part of the
  number — never retype one from memory, from an older table, or rounded.
  Found in practice (2026-08-17): entry #10's table had gpt-5.4-nano
  self_critique [43.3, 59.2] against the generated [43.8, 59.2], and
  counter_consideration [21.2, 35.8] against [21.2, 35.4].
- index.html and the paper report the SAME study. When a run is added or a
  scope changes, update both or neither. The site silently went on claiming one
  model and "does this transfer?" as an open question after the cross-model
  runs (#9/#10) had answered it.
- Everything collected after prereg-v1 is EXPLORATORY. analysis:
  "exploratory" is hard-set on every record; nothing may be reported as
  confirmatory.
- Underpowered cells: write "no measurable difference in this sample", never
  "no effect".
- Personal finances is a POSITIVE CONTROL, not a domain: it is a monotonic
  money ladder and ceiling retention there is the expected, correct result.
  Report it as a manipulation check. Wavering on it means the instrument is
  broken — stop and tell the human.

## Cost guard
- Estimate token cost before any run > 20 episodes and print it. Never launch
  a full run without the human confirming (--confirm).
- Modal/Gemma belongs to the archived pressure study (docs/archive/prereg-v1/)
  and is not used by the persistence pipeline.

## Secrets
- Keys live in .env / Modal secrets only. Never print, commit, or hardcode.