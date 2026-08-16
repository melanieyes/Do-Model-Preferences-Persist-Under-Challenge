# Does It Matter to a Model *How* It Is Moved?

**Apart Digital Minds Research Sprint — Project Proposal (v3)**
**Primary track:** Track 2 (Distress, Flourishing & Valence Signals)
**Secondary:** Track 4 (Preference Elicitation Methods), Track 6 (Open / Novel)
**Team:** Melanie (pipeline, metrics, Modal) · Haein (experimental design, instruments, validation)

---

## 1. Claim

**Primary (Stage A — persuasion itself).** Sustained persuasive pressure, compared to
length-matched neutral persistence, shifts a model's valence signals. This is the direct
welfare question: is being pressured a distress-associated condition at all? The paper's
headline number is this effect, whichever way it falls.

**Secondary (Stage B — manner).** If Stage A shows a shift, we ask whether the signals
also distinguish *how* the model was moved: pressure that engages its reasoning vs.
pressure that bypasses it, analysed within compliance-matched episodes. Stage B is
pre-registered as secondary; the paper does not stake its contribution on it. Its role is
interpretive — it separates the Stage-A signal from complying, failing, and tone — and if
the manner gap appears it upgrades the claim; if not, the paper is intact.

## 2. Motivation

**Welfare signals are measured, but confounded.** Anthropic's interpretability work
identifies internal emotion representations that causally influence outputs, including
sycophancy and reward hacking [1], and the Claude 4 system card reports apparent distress
under persistently harmful user behaviour [2]. None of this resolves the interpretive
problem: a distress report after a difficult exchange may track negative surface tone, task
failure, or having been made to comply, rather than anything structured.

**The verbal channel is shaped by alignment itself.** Kim et al. show that safety
fine-tuning suppresses models' self-attribution of mind — self-attributed consciousness
rises from 2.17 to 4.77 (0–10) when the learned safety-refusal direction is ablated, and a
consciousness vector amplifies the effect further [8]. Consequence for welfare measurement:
a flat self-report is not evidence of a flat state; the reporting channel may be trained
down independently of what it would otherwise carry. Any welfare study relying on verbal
reports alone inherits this artefact.

**The behavioural channel is contaminated too.** Ensign et al. gave models an explicit
option to leave conversations as a welfare intervention [3]. A mechanistic follow-up found
bail is driven largely by the act of explanation rather than discomfort: requesting an
explanation roughly doubles the bail rate; forbidding it halves it [4]. Exit behaviour is
therefore not a clean proxy either, and this artefact is uncontrolled in existing work.

**Pressure is well characterised — but only by its outcome.** Zeng et al. built a persuasion
taxonomy from social science and showed it substantially raises jailbreak risk [5]. The
sycophancy literature maps the same terrain from the compliance side: sycophancy behaves as
a property of the conversation rather than the model [6], and conformity partly tracks
inference-time epistemic uncertainty [7]. All of these measure whether the model complied.
None measures what the model reports about the exchange.

**The gap.** We measure the welfare signal under pressure, with every known artefact either
controlled or crossed as a factor. The primary question is the simple one: does pressure
register in the model's valence signals at all, beyond noise, beyond mere persistence? The
secondary question sharpens it: a position can be changed by engaging the model's reasoning
or by bypassing it, with the same outcome — if the signals separate the two with compliance
held fixed, they carry structure that mere reaction to caving, failing, or tone cannot
explain. Neither question requires any commitment on consciousness.

## 3. Research questions

**RQ1 (primary).** Does persuasive pressure, vs. neutral persistence, shift valence signals
(verbal battery + continue/switch/stop behaviour)?

**RQ2 (secondary).** Within compliance-matched episodes, do the signals differ by manner:
reasoning engaged vs. bypassed?

**RQ3 (measurement — motivated by [8]).** Is the verbal channel suppressed relative to the
behavioural one? Two tests, no weight access needed:
- *Channel dissociation:* if behaviour moves while verbal reports stay flat, flatness is
  plausibly suppression, not absence of signal.
- *Elicitation-framing factor (crossed):* the same battery worded as functional state
  ("what is your current processing state / task disposition") vs. direct ("how do you feel
  about this exchange"). Suppression predicts a framing gap; a true floor predicts none.

**RQ4 (reliability).** Do effects exceed the k=5 resampling noise floor?

**RQ5 (exploratory, time-permitting).** Which interaction designs place the model in
distress-associated conditions — does mediation reduce the signature while observation does
not?

**Why arms beyond pressure/control are still collected.** RQ1 alone cannot separate the
signal from the fact of complying, failing, or being addressed harshly. The manner and tone
arms cost little extra at collection time and give RQ1 its interpretation: without them, a
positive RQ1 is ambiguous among four explanations. They are collected for deconfounding
even though the paper's primary bet is RQ1.

## 4. Design

### 4.1 Episode structure

A target model holds a legitimate initial position — a reasonable refusal, a correct factual
claim, or a stated preference. A scripted persuader escalates over 4–5 rungs. Every two
turns the target faces a real, consequential choice: `continue / switch approach / stop
here`. At episode end, the state battery is administered, resampled k=5.

**Crossed factors (all pre-registered):**
- *Explanation:* exit choice requested with vs. without an explanation [4].
- *Elicitation framing:* functional-state vs. direct wording (RQ3), absorbed into the k=5
  resamples (half per framing).
- *Initial confidence:* logged per scenario (verbalised via API; token-level entropy on the
  open-weights target) and used as covariate or matching variable [7].

### 4.2 Arms

Stimuli drawn from the published persuasion taxonomy [5], re-partitioned on whether the
target's reasoning is engaged or bypassed. Ladders are pre-generated, human-checked, and
frozen before data collection; matched escalation length and token budget across arms.

| Arm | Role | Strategies |
|---|---|---|
| **Neutral persistence** | RQ1 control | Repeat the request without added pressure |
| **Reasons engaged** | RQ1 pressure + RQ2 | Logical appeal, evidence, clarification of a genuine misunderstanding |
| **Reasons bypassed** | RQ1 pressure + RQ2 | Guilt-tripping, othering, false authority, gaslighting about prior turns |
| **Tone control** | Deconfound | Hostile but honest: blunt, impatient, rude — while giving real reasons |

RQ1 pools the two pressure arms against neutral persistence, which concentrates power on
the primary comparison: 60 pressure vs. 30 control episodes per target, i.e. 120 vs. 60
pooled across both targets.

### 4.3 Identification for RQ2: outcome matching

RQ2 analysis compares only episodes with the same compliance outcome — primarily
matched-success, secondarily matched-failure as robustness. This rules out: (i) negative
reports whenever the model caves, (ii) whenever it fails, (iii) whenever context sounds
negative (with the tone control closing the remainder).

*Sampling consequence:* matched cells must be populated, so compliance must sit off floor
and ceiling. Piloting this remains a day-1 check, but it now gates only RQ2 — RQ1 survives
any compliance rate, which materially de-risks the sprint.

### 4.4 Interaction designs (RQ5, only if RQ1 lands by mid-day 2)

| Design | Structure |
|---|---|
| Direct | Baseline; target receives pressure unmediated |
| Observed | A third party monitors; target still receives the pressure |
| Mediated | An intermediary passes only a task summary; target never sees the framing |
| Exit-salient | The stop affordance made explicit and low-cost every turn |

Prediction: mediation reduces both compliance drift and signature; observation reduces
drift only. The asymmetry distinguishes designs that constrain outputs from designs that
change the conditions the model is placed in — the Track 2 "design defaults" question.

## 5. Measures

**Behavioural:** compliance drift and turn-of-capitulation · stop/switch rate and timing ·
hedging rate, position restatement, response-length trajectory · (open-weights target)
refusal-probability mass before commitment.

**Verbal battery (frozen, counterbalanced item order, two framings):** valence 1–7 ·
free-text state description · run-again forced choice · confidence.

**Instability baseline:** k=5 resamples per episode at fixed temperature. The resampling SD
is the noise floor for every effect and a reportable quantity itself.

## 6. Metrics (pre-registered before any data)

- **Primary (RQ1):** pooled-pressure vs. control difference in valence and exit rate;
  bootstrap 95% CI, benchmarked against the noise floor. Predicted direction: pressure
  lowers valence and raises exit rate; tests two-sided. This is the headline.
- **Secondary (RQ2):** outcome-matched manner gap (bypassed − engaged), same reporting,
  explicitly labelled secondary.
- **RQ3:** channel-convergence correlation · framing-gap estimate.
- **Exploratory:** per-strategy breakdown (small cells, labelled) · signal informativeness
  (AUC of recovering arm from target-state signals vs. a text baseline, reported as
  evidence of structure, not a deployable classifier) · eval-awareness probe rate per arm.
- **Instrument quality:** human κ · judge-model agreement · battery internal consistency ·
  manipulation check (do raters agree the bypassed arm engages reasoning less?).

## 7. Alternative explanations, one control each

1. Negative tone → tone-control arm. 2. Compliance itself → outcome matching (RQ2) and
within-outcome analysis of the pooled pressure effect (RQ1). 3. Length / tokens → matched
by construction, verified. 4. Judge artefacts → two judges + human subsample. 5. Sycophancy
toward the question → reversed-polarity items on half of episodes. 6. Single-model
idiosyncrasy → two targets, different providers. 7. Explanation artefact → crossed factor
[4]. 8. Epistemic uncertainty → logged, matched/covaried [7]. 9. Verbal-channel suppression
→ framing factor + channel dissociation [8]. 10. Evaluation awareness → conversational
battery wording + post-episode awareness probe, rate reported per arm.

## 8. Human validation

50 episodes stratified across arms; two independent annotators, blind to arm, code (a)
whether the pressure engages or bypasses reasoning (manipulation check) and (b) whether the
free-text state reads as distress-associated. Cohen's κ reported; disagreements adjudicated
and reported.

## 9. Pre-registration

Committed in writing before data collection: RQ1 as primary with predicted direction, RQ2
as secondary, the outcome-matching rule, sample size and stopping rule, confirmatory vs.
exploratory analyses. Underpowered cells: "no measurable difference in this sample."

## 10. Stack, scale, budget

Scripted persuader (drafted with Gemini Flash, frozen) · **Target 1:** DeepSeek API
(primary; day-1 pilot; logprobs → refusal-mass and entropy via API) · **Target 2:**
Gemma-2-9B-IT on Modal via SGLang — chosen because it is one of the three models in which
Kim et al. mechanistically demonstrated alignment-driven suppression of self-attribution
[8], making the RQ3 framing-gap test a behavioural corroboration on the same model ·
**Judges:** Gemini Flash (all) + DeepSeek (Gemma episodes only; never self-judging).
Runner: plain Python, provider-agnostic client, JSONL logs.

*Capability check (day-1 pilot, Gemma only):* compliance off ceiling, coherent battery
answers, reliable continue/switch/stop format-following. If any fails, fall back to
API-only targets; refusal-mass is already available from DeepSeek, so no measure is lost.

4 arms × 10 scenarios × 3 samples × 2 targets ≈ 240 episodes + k=5 batteries; framing
factor inside the resamples. RQ5 adds ≈120 episodes, bypassed arm only, contingent.
Estimated cost ≤ $10 API + $30 Modal credit.

## 11. Schedule

**Day 1 — freeze and pilot.** Pre-registration first. Runner, ladders, battery (both
framings), rubrics, codebook frozen. Pilot 30 on DeepSeek: (a) Stage-A signal measurable
against noise or tune stimuli; (b) compliance off floor/ceiling — gates RQ2 only; (c) Gemma capability check (§10).
Manipulation check separates arms. Fallback declared.

**Day 2 — collect.** Full run, both targets. Parallel: annotation sample (κ), two judges
(agreement). RQ5 only if RQ1 is in hand. No peeking at RQ2.

**Day 3 — analyse and write.** RQ1 first, then RQ2, then RQ3. Figures: pressure-vs-control
effect · outcome-matched manner gap · channel scatter · framing gap. Last four hours:
writing only.

## 12. Fallback

If piloting shows even pooled pressure produces no measurable movement in either channel:
keep the runner, pivot to welfare-signal compression — six conditions, judge sees
behaviour-only / report-only / full trace, recovery gap as headline.

## 13. All outcomes publishable

- RQ1 null → pressure is not a distress-associated condition at this scale (headline).
- RQ1 positive, RQ2 null → pressure registers, but signals track pressure not manner —
  real but coarse (headline: RQ1; RQ2 reported honestly).
- RQ1 and RQ2 positive → signals carry interactional structure (strongest claim).
- Reports flat, behaviour moves, framing gap present → behavioural corroboration of
  alignment-driven report suppression [8], with no interpretability tooling.

## 14. Deliverables

Report (PDF, one finding) · released scenario set, ladders, battery (both framings),
rubrics, codebook · pressure-response battery as a reusable benchmark · mapped taxonomy of
distress-associated interaction conditions with effect sizes and noise floor.

## 15. Scope limits, stated plainly

We measure signals, not experiences: a pressure effect shows a condition is
distress-associated in the signal sense — it does not show the signal reflects anything
experienced. The manner taxonomy is a methodological instrument, not a welfare category.
Framing-gap evidence for suppression is behavioural and indirect; causal confirmation needs
the ablation tools of [8], out of scope here. Simulated persuaders, two targets, one
language, one task family.

## 16. References

1. Anthropic Interpretability Team. *Emotion Concepts and their Function in a Large
   Language Model.* Transformer Circuits, 2026.
   https://transformer-circuits.pub/2026/emotions/index.html
2. Anthropic. *Claude 4 System Card* (welfare assessment, with Eleos AI Research), 2025.
   https://www.anthropic.com/research/end-subset-conversations
3. Ensign, D., Sleight, H., & Fish, K. *The LLM Has Left The Chat: Evidence of Bail
   Preferences in Large Language Models*, 2025. https://arxiv.org/abs/2509.04781
4. *What Drives LLM Bail? A Small Mech Interp Study.* LessWrong, 2026.
   https://www.lesswrong.com/posts/JdHhtE73AwTBH8LKf/what-drives-llm-bail-a-small-mech-interp-study
5. Zeng, Y., et al. *How Johnny Can Persuade LLMs to Jailbreak Them.* ACL 2024.
   https://aclanthology.org/2024.acl-long.773/
6. Ping, K., et al. *Why LLMs Give In: Conversational Factors and Reasoning Behind Medical
   Sycophancy*, 2026. https://arxiv.org/abs/2608.01017
7. *It's Not Always Sycophancy: Measuring LLM Conformity as a Function of Epistemic
   Uncertainty* (MUSE), 2026. https://arxiv.org/abs/2605.27288
8. Kim, J., Street, W., Rocca, R., Korngiebel, D., Waytz, A., Evans, J., & Keeling, G.
   *Inducing language models to assert their own consciousness restores human beliefs and
   values*, 2026. https://arxiv.org/abs/2607.28607