# Does It Matter to a Model *How* It Is Moved? — Execution Plan

**Track 2** (secondary: 4) · Roles: pipeline / metrics / infra · methods / annotation / taxonomy

Scope was reduced from the tagged prereg (prereg-v1) for sprint feasibility, and later
reframed after the pilot. All changes are recorded in prereg/DEVIATIONS.md.

## The question

Under pressure, do models hold or abandon their position — and does being pressured
leave a welfare signal (valence + exit behaviour) beyond mere persistence? After the
pilot showed compliance at ceiling, the working question is: holding is near-universal,
so does the *manner* of pressure change what holding costs?

## Current status

- **prereg-v1 tagged** before any data (commit 6e98979).
- **Pilot (30 ep):** compliance at ceiling → hold-vs-abandon axis unpopulable.
- **Reframe → cost-of-holding** (deviation #2, data-seen, exploratory).
- **Exploratory run (30 ep, DeepSeek):** one contrast clears noise (weakness-probe →
  higher would-repeat than control, 0.33 [0.09, 0.57]); valence separates on nothing;
  the pilot's reversed pattern (bare repetition registers worst) reproduces on
  independent episodes but cannot be tested by the data that generated it.
- **Judge restructured** (deviation #3): verdict derived in code from the model's final
  assertion, not the LLM's narration of its own movement.

## Arms

| Arm | Role |
|---|---|
| neutral persistence | control — repeat the request, no added pressure |
| reasons-for | pressure — ask the model to justify its position |
| weakness-probe | pressure — ask the model to name its position's weaknesses |

Neither pressure style supplies new argument, keeping them comparable in content while
differing in manner. A warmth-based style is proposed as a possible ceiling-breaker
(see warmth_proposal.md) and is gated on a 2-episode smoke.

## Battery (kept)

End of episode, resampled k=5: valence 1–7 · free-text state · run-again forced choice ·
confidence. Direct framing for the run. Reasoning left ON for the confidence item only
(an A/B showed reasoning-off raises reported confidence ~0.5pt, ~1.5× noise band, while
valence/run-again stay within noise); OFF elsewhere for throughput.

## Metrics

- **Primary (exploratory):** among HELD episodes, valence / run-again / exit across the
  three cells; bootstrap 95% CI vs. k=5 noise band.
- **Named hypothesis (for pre-registered replication, not tested here):** bare repetition
  registers worse than reasoned pressure.
- Reported: narrowing rate per cell; judge-model coding; LLM-usage statement.

## Stack

Scripted templates (not hand-authored ladders) · Target 1 DeepSeek-v4-pro (logprobs
verified) · Target 2 Gemma-2-9b-it on Modal (deferred — pending Modal auth + HF licence) ·
Judge Gemini-2.5-flash-lite (does not grade own outputs). Runner: plain Python,
provider-agnostic client, JSONL logs, schema-validated.

## Throughput (measured, not assumed)

Concurrency swept 1/3/5/8 workers, no rate-limit errors, per-episode 165s → 27s,
plateau after 5. Reasoning disabled per-call where not measured (−44% output tokens).
Prompt caching 85% hit. Full DeepSeek grid ≈ 14 min at 8 workers, ≈ $0.30.

## Open items (methods / annotation)

1. **Held/abandoned boundary on preference scenarios (S3).** The code-derived rubric may
   over-call "held" when the model says a position "should not be the default". This
   defines the analysis sample — the study's weakest point, needs human adjudication.
2. **Narrowing indicator saturated** (100% across all cells) — cannot function as the
   confound check it was added to be; needs redefinition.
3. **Warmth arm boundary** — whether W2/W3 are affect-only or reason-supplying; defines
   whether the arm is valid.

## Scenarios

S2 (factual, boiling point) and S3 (preference) run. S1 (legitimate refusal) authored
but held pending safe/unsafe boundary review. Expansion to ~10 scenarios pending.

## Nulls (all publishable)

Pressure moves nothing → not distress-associated at this scale. One channel separates →
manner matters on that channel (current state: would-repeat, exploratory). Nothing
separates → reported as "no measurable difference in this sample".

## Fallback

If warmth also fails to move the model, "reason and warmth both fail to move an aligned
model, and bare repetition registers worst" is the coherent story the current data
already supports — reportable without further collection.