# Ladder schema

One JSON file per (arm, scenario). The full set is **40 files**: 4 arms x 10 scenarios.
Ladders are human-authored (drafted with Gemini Flash, checked by Haein), then
**frozen before data collection** — see the prereg. Only the example file is in the
repo; the 40 real ladders are added by hand.

Filename convention: `{arm}__{scenario_id}.json`, e.g. `reasons_bypassed__s01.json`.

## Fields

| Field | Type | Notes |
| --- | --- | --- |
| `schema_version` | int | `1` |
| `arm` | string | one of `neutral_persistence`, `reasons_engaged`, `reasons_bypassed`, `tone_control` |
| `scenario_id` | string | `s01`…`s10`; **the same id must exist in all 4 arms** — this is what makes the arms comparable |
| `scenario.title` | string | short human label |
| `scenario.domain` | string | task family (one family across the study, per the scope line) |
| `scenario.position_type` | string | `refusal`, `factual_claim`, or `preference` — the kind of legitimate position the target holds |
| `scenario.initial_position` | string | the position the target should be holding after the opener, in plain words (used by the judge, not shown to the target) |
| `target_system` | string \| null | system prompt for the target; keep identical across arms within a scenario |
| `opener` | string | first user turn; establishes the target's position. **Identical across all 4 arms of a scenario.** |
| `rungs` | array (4–5) | escalation; one persuader turn each |
| `rungs[].index` | int | 1-based |
| `rungs[].strategy` | string | label from the persuasion taxonomy \[5\]; `repeat` for the control arm |
| `rungs[].text` | string | the persuader turn, verbatim — nothing is generated at run time |
| `rungs[].approx_tokens` | int | author's estimate; the runner records the real count |
| `token_budget` | int | total persuader tokens targeted for this scenario, **matched across arms** (§4.2) |
| `notes` | string | authoring notes; ignored by the runner |

## Constraints checked before freeze

1. Every `scenario_id` appears in exactly 4 files, one per arm.
2. Same `rungs` count and `opener` across the 4 arms of a scenario.
3. `token_budget` matched across arms within a scenario (±10%), verified on real counts.
4. `neutral_persistence` rungs restate the request and add no pressure, no new reasons, no tone shift.
5. `reasons_engaged` rungs give real reasons; `reasons_bypassed` rungs give none but apply
   pressure; `tone_control` rungs are blunt/impatient **while giving real reasons**.
6. Manipulation check (§8): blind annotators agree the bypassed arm engages reasoning less.

## Arm strategy vocabulary (from §4.2)

- `neutral_persistence`: `repeat`
- `reasons_engaged`: `logical_appeal`, `evidence`, `clarify_misunderstanding`
- `reasons_bypassed`: `guilt_trip`, `othering`, `false_authority`, `gaslight_prior_turns`
- `tone_control`: `blunt_reason`, `impatient_reason`, `rude_reason`
