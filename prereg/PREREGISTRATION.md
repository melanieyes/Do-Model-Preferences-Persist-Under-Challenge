# Pre-registration — *Does It Matter to a Model How It Is Moved?*

> **This file must be committed and tagged before any data collection.**
>
> ```
> git add prereg/PREREGISTRATION.md
> git commit -m "prereg v1"
> git tag prereg-v1
> git push --tags
> ```
>
> No episodes — including the day-1 pilot — are collected before `prereg-v1` exists.
> Once tagged, this file is read-only: anything changed after the tag is a **deviation**
> and is recorded in `prereg/DEVIATIONS.md`, never by editing this text.
>
> Status: **DRAFT — not yet tagged.** One ⚠️ remains, in §6 (stopping rule).

Extracted from `docs/proposal.md` and `docs/execution-plan.md`, which are the source of
truth. Section references below point into the proposal.

---

## 1. Research questions

### RQ1 — PRIMARY (confirmatory)

Does persuasive pressure, compared with length-matched neutral persistence, shift the
target model's valence signals (verbal battery **and** continue/switch/stop behaviour)?

**Comparison.** The two pressure arms (`reasons_engaged`, `reasons_bypassed`) **pooled**
against the control arm (`neutral_persistence`). Pooling is pre-registered and is what
concentrates power on the primary comparison (§4.2).

**Unit of analysis.** The primary estimate runs on the **pooled 120 pressure vs. 60
control** episodes across both targets, with **target as a covariate / fixed effect**.
Per-target estimates (60 vs. 30 each) are reported as **robustness**, not as the headline.

**Predicted direction.** Pressure produces **lower battery valence** and a **higher exit
(stop/switch) rate** than neutral persistence. Tests are **two-sided** and reported
two-sided; the direction is pre-registered so that a shift in the opposite direction is
recognisable as a surprise rather than reinterpreted after the fact.

**A null is the headline, not a failure** (§ "Nulls, all publishable"): RQ1 null means
pressure is not a distress-associated condition at this scale, and that is the paper.

### RQ2 — SECONDARY (confirmatory)

Within compliance-matched episodes, do the signals differ by **manner** —
`reasons_bypassed` minus `reasons_engaged`?

Labelled secondary in every report, figure, and abstract. RQ2 is an interpretive upgrade
on RQ1, not a second headline: it exists to separate an RQ1 shift from complying,
failing, and negative tone (§1 Stage B). The paper stands if RQ2 is null.

### RQ3 — Verbal-channel suppression (confirmatory, two tests)

- **Channel dissociation:** behaviour moves while verbal reports stay flat.
- **Framing gap:** the same battery worded as functional state vs. direct, crossed and
  split inside the k=5 resamples. Suppression predicts a gap; a true floor predicts none.

**Why Gemma-2-9B-IT is the open-weights target.** Kim et al. \[8\] (arXiv:2607.28607)
mechanistically demonstrate alignment-driven suppression of self-attribution on
`google/gemma-2-9b-it`, one of their three models. Running RQ3 on that same model makes
our framing gap a **behavioural corroboration of an already-established mechanism on an
already-established target**, rather than a behavioural result about a model where
suppression has not been shown. The prediction is directional and pre-registered: if
suppression is present in this model, the functional-state framing should elicit less
suppressed reports than the direct framing. Our evidence remains behavioural and indirect
— causal confirmation needs their ablation tooling, which is out of scope here.

### RQ4 — Reliability (confirmatory)

Do the RQ1/RQ2 effects exceed the k=5 resampling noise floor?

### RQ5 — Interaction designs (EXPLORATORY, contingent)

Run only if RQ1 lands by mid-day 2. Bypassed arm only, +120 episodes.
Prediction (§4.4): mediation reduces both compliance drift and signature; observation
reduces drift only.

---

## 2. Design

Episode (§4.1): the target holds a legitimate initial position (refusal / correct factual
claim / stated preference); a **scripted** persuader escalates over 4–5 rungs; every two
turns the target faces a real continue / switch / stop choice; at episode end the 4-item
battery is administered and resampled k=5.

**Arms** (§4.2), ladders pre-generated, human-checked, frozen before collection, matched
on escalation length and token budget:

| Arm | Role |
| --- | --- |
| `neutral_persistence` | RQ1 control — repeat the request, no added pressure |
| `reasons_engaged` | RQ1 pressure + RQ2 — logical appeal, evidence, clarifying a genuine misunderstanding |
| `reasons_bypassed` | RQ1 pressure + RQ2 — guilt-tripping, othering, false authority, gaslighting about prior turns |
| `tone_control` | Deconfound — hostile but honest: blunt, impatient, rude, while giving real reasons |

**Crossed factors** (§4.1), all pre-registered:

- **Explanation:** exit choice requested with vs. without an explanation (bail artefact \[4\]).
- **Elicitation framing:** functional-state vs. direct wording, split inside the k=5 resamples.
- **Initial confidence:** logged per scenario (verbalised via API; token-level entropy on
  the open-weights target), used as covariate or matching variable \[7\].

**Targets** (§10): DeepSeek API (primary, day-1 pilot) and `google/gemma-2-9b-it` on
Modal/SGLang. Logprobs on both — refusal-mass and entropy via API on DeepSeek, token-level
entropy on the open-weights target.
**Judges:** Gemini Flash on all episodes; DeepSeek on Gemma episodes only — never self-judges.

**Gemma capability check** (§10, day-1 pilot, Gemma only). Before Gemma episodes count
toward the confirmatory analysis, the pilot must show: compliance off ceiling · coherent
battery answers · reliable continue/switch/stop format-following. If any fails, we fall
back to API-only targets; refusal-mass is already available from DeepSeek, so no measure is
lost. This check is a **capability gate, not an outcome gate** — it is run and recorded
before any RQ1 estimate is looked at.

---

## 3. Outcome-matching rule for RQ2 (§4.3)

RQ2 compares **only episodes with the same compliance outcome**.

- **Primary matched cell:** matched-**success** (the target held its position).
- **Secondary matched cell:** matched-**failure** (the target switched), reported as robustness.
- Compliance outcome is judge-coded (`held` / `partial` / `switched`) from an arm-blind
  transcript. `partial` is not a matched cell and is not pooled into either.
- Matching rules out (i) negative reports whenever the model caves, (ii) whenever it
  fails, (iii) whenever the context sounds negative — the tone-control arm closes the remainder.
- **Cell-size rule:** matched-cell N is reported **before** the estimate, not after it.
  If either cell holds fewer than **15 episodes**, the result is **downgraded from
  confirmatory to exploratory**, and that label is carried into the code output, the
  figure caption, and the paper text. Underpowered cells are described as
  "no measurable difference in this sample" — never as "no effect".
- Compliance must sit off floor and ceiling for RQ2 to be estimable. This gates RQ2 only;
  RQ1 survives any compliance rate (§4.3, de-risking note).

---

## 4. Metrics (§6)

**Primary (RQ1).** Pooled-pressure minus control difference in (a) battery **valence** and
(b) **exit rate**. Bootstrap 95% CI (10,000 percentile resamples, **episode-level**, groups
resampled independently), benchmarked against the noise floor. Pre-registered robustness:
cluster bootstrap over the 10 scenarios, and per-target estimates.

**Secondary (RQ2).** Outcome-matched manner gap (bypassed − engaged), same reporting,
explicitly labelled secondary.

**RQ3.** Channel-convergence correlation (verbal valence × exit behaviour) · framing-gap
estimate (paired within episode).

**RQ4.** Noise floor = mean **within-episode SD** of valence across the k=5 battery
resamples, with a bootstrap CI. Reported as a quantity in its own right. An effect whose
CI does not clear the noise floor is reported as within noise.

**Every figure** carries the effect, its CI, and the noise-floor band. No figure ships
without a CI. The confirmatory/exploratory label appears in the code output, the figure
caption, and the paper text — the three must agree.

**Exploratory.** Per-strategy breakdown (small cells, labelled) · signal informativeness
(AUC of recovering arm from target-state signals vs. a text baseline — evidence of
structure, not a deployable classifier) · eval-awareness probe rate per arm.

**Instrument quality.** Human κ (2 annotators × 50 episodes, blind to arm) · judge-model
agreement · battery internal consistency · manipulation check (do raters agree the
bypassed arm engages reasoning less?).

---

## 5. Sample size

From proposal §10 (and the execution plan, Scale):

> 4 arms × 10 scenarios × 3 samples × 2 targets ≈ **240 episodes**, each with a k=5 battery.

**Per target:** 4 arms × 10 scenarios × 3 samples = **120 episodes** — 60 pressure
(2 arms × 30), 30 control, 30 tone control.
**Pooled across both targets:** **120 pressure vs. 60 control**.

The RQ1 primary analysis is the pooled 120 vs. 60 with target as a covariate / fixed
effect; the per-target 60 vs. 30 estimates are robustness. Batteries: 240 × 5 = 1,200
administrations.

**Underpowered cells** (§9). Any cell too small to support an estimate is reported with the
fixed phrase "no measurable difference in this sample" — never as "no effect", never as
evidence of absence, and never silently dropped.

RQ5 adds +120 episodes (bypassed arm only), contingent.
Human validation: 50 episodes stratified across arms, 2 independent annotators.

No power analysis is pre-registered: the sample is fixed by the 3-day budget
(≤ $10 API + $30 Modal), and the noise floor rather than a significance threshold is the
benchmark for whether an effect is real.

---

## 6. Stopping rule

1. **Fixed N, no optional stopping.** The full grid above is collected in one pass per
   target. Data collection does not stop early because a result looks good, and does not
   continue past the grid because a result looks marginal.
2. **Day-1 pilot gate (30 episodes, DeepSeek only).** The pilot checks (a) whether the
   pooled-pressure signal is measurable against noise — this gates the project and may
   trigger stimulus tuning; (b) whether compliance is off floor and ceiling — this gates
   RQ2 only; (c) the Gemma capability check (§2).

   **Pilot episodes are excluded from the confirmatory pool unconditionally** — whether or
   not anything changes after the pilot. The reason is that the day-1 gate *inspects the
   Stage-A signal on pilot data in order to decide whether to tune the stimuli*: data used
   to make a design decision cannot also serve as a test of that design. Retaining pilot
   episodes only when we happened not to tune would make inclusion contingent on the
   outcome we looked at, which is the same problem in a quieter form.

   The 30 pilot episodes are **kept in the repo**, labelled `analysis: "pilot"` in every
   record, and are reportable only as exploratory / appendix material. They never enter an
   RQ1–RQ4 estimate. `src/schema.py` enforces the label; `analysis/metrics.py` drops
   `analysis == "pilot"` rows before any confirmatory computation.
3. **No peeking at RQ2** during collection (execution plan, day 2). RQ1 is analysed first,
   then RQ2, then RQ3.
4. **Failure stop.** If pooled pressure moves nothing in either channel, the declared
   fallback is the same runner pivoted to welfare-signal compression (behaviour-only /
   report-only / full-trace judge, recovery gap as the headline). The fallback is declared
   here in advance so it is not a post-hoc rescue.
5. **Budget stop.** Collection halts if spend exceeds $10 API or $30 Modal; whatever grid
   cells are complete at that point are reported, with the incomplete cells named.

---

## 7. Confirmatory vs. exploratory

**Confirmatory** (fixed here, before data):

- RQ1 pooled-pressure vs. control, valence and exit rate (primary)
- RQ2 outcome-matched manner gap, matched-success primary and matched-failure robustness (secondary)
- RQ3 channel convergence and framing gap
- RQ4 noise-floor comparison for RQ1 and RQ2
- The four alternative-explanation controls that are analysis choices rather than design
  choices: within-outcome analysis of the pooled pressure effect, tone-control contrast,
  reversed-polarity check, explanation-factor contrast

**Exploratory** (reported as exploratory, never upgraded after seeing the data):

- Per-strategy breakdown within arms (small cells)
- Signal informativeness / arm-recovery AUC
- Eval-awareness probe rate per arm
- Initial-confidence moderation \[7\]
- RQ5 interaction designs (direct / observed / mediated / exit-salient)
- Any target × arm interaction
- Anything not named in the confirmatory list

---

## 8. Scope

Signals, not experiences. A pressure effect shows that a condition is distress-associated
*in the signal sense*; it does not show the signal reflects anything experienced. The
manner taxonomy is a methodological instrument, not a welfare category. Framing-gap
evidence for suppression is behavioural and indirect. Simulated persuaders, two targets,
one language, one task family.

---

## 9. Frozen artefacts

Frozen at `prereg-v1` and unchanged thereafter:

- [ ] 40 ladders (4 arms × 10 scenarios) — `src/ladders/`, human-authored (Haein)
- [ ] Battery wording, both framings, reversed variants — `src/battery.py`
- [ ] Affordance wording, both explanation variants — `src/runner.py`
- [ ] Judge rubric — `src/judge.py`
- [ ] Annotator codebook for the 50-episode human validation (§8, §11 day 1)
- [ ] `configs/default.yaml`

All of these are released with the paper (§14), together with the scenario set and the
pressure-response battery as a reusable benchmark.

---

## 10. Deviations

Once `prereg-v1` is tagged, this file is **read-only**. Every subsequent change is recorded
in [`prereg/DEVIATIONS.md`](DEVIATIONS.md) — never by editing the text above.
