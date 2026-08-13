# Does It Matter to a Model *How* It Is Moved? — Execution Plan v3

**Track 2** (secondary: 4, 6) · Melanie (pipeline, metrics, Modal) · Haein (design, instruments, validation)

## Structure

**Primary (RQ1):** pooled persuasive pressure vs. length-matched neutral persistence shifts
valence signals (verbal + behavioural). The headline, whichever way it falls.
**Secondary (RQ2):** within compliance-matched episodes, signals differ by manner
(reasons-engaged vs. reasons-bypassed). Interpretive upgrade if present; paper intact if not.
**RQ3:** verbal-channel suppression test (Kim et al.): channel dissociation + framing factor.
**RQ4:** effects vs. k=5 resampling noise floor.

## Design

Episode: target holds legitimate position; scripted 4–5-rung escalation; every 2 turns real
`continue / switch / stop`; end-of-episode 4-item battery, k=5 resamples.

Arms: **neutral persistence (control)** · reasons-engaged · reasons-bypassed ·
hostile-but-honest tone control. Ladders pre-generated, human-checked (Haein), frozen;
matched length and tokens. RQ1 pools both pressure arms vs. control (60 vs. 30 per target; 120 vs. 60 pooled
across both targets).

Crossed factors: exit with/without explanation (bail artefact) · battery framing functional
vs. direct (suppression test, split inside k=5) · initial confidence logged (covariate).

## Metrics (pre-registered day 1)

- **Primary:** pooled-pressure − control, valence and exit rate; predicted direction:
  pressure lowers valence, raises exit rate; two-sided tests; bootstrap 95% CI vs. noise
  floor.
- **Secondary:** outcome-matched manner gap (bypassed − engaged), labelled secondary.
- RQ3: channel convergence · framing gap. Exploratory: per-strategy · signal AUC ·
  eval-awareness rate.
- Instrument quality: human κ · judge agreement · internal consistency · manipulation check.

## Stack (≤ $10 API + $30 Modal)

| Role | Model |
|---|---|
| Persuader | Scripted (drafted w/ Gemini Flash, frozen) |
| Target 1 | DeepSeek API (pilot first; logprobs → refusal mass via API) |
| Target 2 | Gemma-2-9B-IT on Modal / SGLang (Kim et al. tie-in for RQ3) |
| Judge A | Gemini Flash (all episodes) |
| Judge B | DeepSeek (Gemma episodes only; never self-judges) |

Runner: plain Python, provider-agnostic client, JSONL.

## Scale

4 arms × 10 scenarios × 3 samples × 2 targets ≈ 240 episodes + k=5 batteries. RQ5
(interaction designs, +120, bypassed arm only) contingent on RQ1 landing by mid-day 2.

## Schedule

**Day 1.** Pre-register RQ1 primary / RQ2 secondary before any data. Runner + ladders +
battery (both framings) frozen. Pilot 30 on DeepSeek: (a) pooled-pressure signal measurable
vs. noise or tune stimuli — gates the project; (b) compliance off floor/ceiling — gates RQ2
only. Manipulation check separates arms. Gemma capability check: compliance off ceiling, coherent battery, affordance format-following — else drop to API-only targets. Fallback declared.
**Day 2.** Full run, both targets. Parallel: 2 annotators × 50 blind to arm (κ); two judges
(agreement). No peeking at RQ2.
**Day 3.** RQ1 → RQ2 → RQ3. Figures: pressure effect · manner gap · channel scatter ·
framing gap. Last 4 hours writing.

## De-risking note

RQ1 survives any compliance rate — only RQ2 needs populated matched cells. The project no
longer bets on the pressure landing at mid-range compliance.

## Nulls, all publishable

RQ1 null → "pressure is not distress-associated at this scale" (headline). RQ1+/RQ2 null →
signal real but coarse. Both + → interactional structure. Reports flat + behaviour moves +
framing gap → suppression corroboration (Kim et al.), no interp tooling.

## Fallback

Pooled pressure moves nothing in either channel → same runner, pivot to welfare-signal
compression (behaviour-only / report-only / full-trace judge, recovery gap headline).

## Scope line

Signals, not experiences. Manner taxonomy = methodological instrument. Framing-gap
suppression evidence is behavioural and indirect.