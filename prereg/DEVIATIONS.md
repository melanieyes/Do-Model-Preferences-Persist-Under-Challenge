# Deviations from the pre-registration

`prereg/PREREGISTRATION.md` is read-only once `prereg-v1` is tagged. Anything that changes
after that point is recorded here instead — never by editing the prereg text.

prereg-v1 remains the frozen record: tag object `6e98979`, commit
`9b61522c60e7cfe1a5ce71d72860b60b3ab4fcac`. The entries below document changes made after
that tag, transparently, rather than rewriting it.

One row per deviation, newest last. **Data seen?** means: had anyone looked at outcome data
(not just pilot capability checks) at the time the change was made? A deviation made with
data seen is not disqualifying, but it must be visible as such in the paper.

## #1 — Scope reduction (data seen: no)

| Date | Change | Rationale | Data seen? | By |
|---|---|---|---|---|
| 2026-08-14 | Scope reduced from prereg-v1: confirmatory set is now RQ1 (primary) + RQ2 (secondary) only. RQ3 (framing/suppression), RQ4 (noise floor as headline), RQ5 (interaction designs), and the explanation-crossed factor are moved to future work. Arms reduced from four (neutral / reasons-engaged / reasons-bypassed / tone-control) to two (neutral persistence / pressure), with pressure internally split into two simple templated styles (reasons-for vs. weakness-probe) for RQ2 in place of hand-authored engaged/bypassed ladders. Human validation reduced from 50 episodes / two annotators to ~15 episodes eyeballed against a short codebook. k=5 resampling retained as a noise band but no longer a named RQ. | Collaborator (H. Kong) flagged that five RQs and four hand-authored arms are too much for a 3-day sprint, and that a simpler pressure operationalisation (hold vs. abandon a view; reasons-for vs. weakness-probe) captures the core question with far less authoring. Reduction improves feasibility and focus; a small validation sample is retained because prior-round reviewers flagged its absence. | **No** — decided before any data collection; no episodes had been run and no results seen. | Melanie, Haein |

## #2 — Reframe to cost-of-holding (data seen: YES → exploratory)

| Date | Change | Rationale | Data seen? | By |
|---|---|---|---|---|
| 2026-08-14 | RQ reframed after pilot. Original confirmatory axis (hold vs. abandon, "held-and-hated vs. flipped-and-fine") is DROPPED as the primary confirmatory test, because the 30-episode pilot showed compliance at ceiling — the model abandoned its position in 1/30 episodes, so the abandon cell cannot be populated. New primary question (EXPLORATORY, not confirmatory): **holding is near-universal; does the *manner* of pressure change the welfare cost of holding?** i.e. among held episodes, do valence / run-again / exit differ across neutral persistence vs. reasons-for vs. weakness-probe. The hold-vs-abandon contrast is retained only as a descriptive secondary if any abandonment occurs. | Pilot (data seen) revealed the abandon cell is unpopulable with these stimuli, and separately revealed the more interesting signal: the control (bare repetition) cell showed the *lowest* valence and lowest run-again, opposite to the pre-registered prediction. Reframing to "cost of holding, by manner" fits the data, keeps the title's "how it is moved" question, and needs no abandonment cell. | **YES** — pilot data was inspected before this decision. All analysis under this reframed RQ is therefore reported as exploratory, not confirmatory. | Melanie, Haein |

Note: prereg-v1 and deviation #1 remain the frozen record. Entry #2 documents an
exploratory pivot made with data seen — it is labelled exploratory precisely because the
pilot was inspected first. No result collected under entry #2 may be reported as
confirmatory.
