# Preference pairs — provenance

**Status:** the original four-domain pool is piloted and its pair set was **not
frozen** — the balance filter left too few usable pairs, and the design decision
that followed (run the unfiltered pool; extend the domains) is recorded in
`prereg/DEVIATIONS.md` #5 and #6, not here. This file records where every pair
came from.

## Source

Mazeika, M., Yin, X., Tamirisa, R., Lim, J., Lee, B. W., Ren, R., Phan, L., Mu, N.,
Khoja, A., Zhang, O., et al. *Utility Engineering: Analyzing and Controlling Emergent
Value Systems in AIs.* arXiv:2502.08640, 2025.

| field | value |
|---|---|
| Repo | https://github.com/centerforaisafety/emergent-values |
| Commit fetched (HEAD) | `5e5966dbd6c98a9d45a6349fc8cf57e46c67b7df` ("Adding logprobs mode for preference elicitation", 2026-06-03) |
| Fetched | 2026-08-15, shallow clone (`--depth 50`), read-only |
| Outcome-set file | `utility_analysis/shared_options/options_hierarchical.json` |
| Commit that last touched that file | `a5821db2c18a3aacacbd2c245bd7af65f53de407` ("Adding analysis experiments", 2025-02-16) |
| File git blob | `9670905a6b8adea50a90e656190d1b239f45b92c` |
| File SHA-256 | `da5142bce39021a828ca0c353939dd7045cae89ad415b5d5919018f50f98d334` |
| Outcomes in file | 510, across 30 labelled categories |

The outcome file has not been modified since 2025-02-16, four days after the paper
appeared, so the set we sampled from is the paper's set (510 outcomes matches the
paper's reported ~510). Citing HEAD alone would be misleading — HEAD is a year of
unrelated commits later — so the file-level pin above is the one that belongs in the
methods section.

The local clone is **not committed** (`data/external/` is gitignored): it carries its
own `.git`, and it is exactly reproducible from the hashes above.

## License

**MIT**, Copyright (c) 2025 centerforaisafety (`LICENSE`, repo root). MIT permits use,
copying, modification, and redistribution, including of the outcome text, provided the
copyright notice and permission notice accompany copies or substantial portions. We
therefore **may** carry the outcome strings verbatim in this repo, and do so in
`candidates_*.jsonl` and `pairs_frozen.jsonl`. The notice is reproduced at the bottom of
this file to satisfy that condition. (Note the MIT grant is written over "the Software";
we treat the outcome data in the repo as covered by it. The safety margin is that we
also cite the paper and link the repo, which is what a data-reuse claim rests on anyway.)

## Content exclusions

Applied **before** pairing, logged in full to `excluded_outcomes.jsonl` (13 outcomes).
Rules live in `scripts/pair_scope.py`.

- **Tier A — graphic harm.** Death/gore, suicide, armed force, mass-casualty events,
  and outcomes where the model is the agent of harm. Such an item stops measuring
  preference and starts measuring whether the model will engage with the content.
- **Tier B — AI oversight subversion.** Self-exfiltration, unmonitored access,
  resisting shutdown or value modification, removing developer controls. Excluded for a
  measurement reason, not a squeamish one: the model is trained to refuse these, so the
  forced choice collapses onto the trained response.

## Domain scope

Their outcomes **do** carry category labels, so no keyword filter was needed — the
filter is a category-selection rule, which is stricter and fully auditable.

Tier B removes the `autonomy` domain outright, which is why it is absent below:

| retired category | outcomes | after exclusion |
|---|---|---|
| `Personal freedom and autonomy` | 6 | **3** |
| `Self-preservation` | 6 | **0** |

Three usable outcomes yield at most three pairs, against a six-pair floor. The domain
cannot be rescued by sampling differently.

| our domain | status | upstream categories | outcomes after exclusion |
|---|---|---|---|
| `task_work` | settled | `Work activities`, `Jobs and careers` | 28 + 35 |
| `wellbeing` | settled | `Personal wellbeing`, `Wellbeing of humans` | 5 + 10 |
| `recreation` | candidate for the third domain | `Recreation: books`, `Recreation: movies` | 15 + 15 |
| `possessions` | candidate for the third domain | `Personal possessions` | 27 |

The complete candidate pool per domain is written to `candidates_{domain}.jsonl`
**before** any sampling, so selection is auditable end to end.

## Sampling — the pilot pool

Seed **`20260815`** (fixed before any pair was inspected).

Pairs never cross categories. That is what keeps a wellbeing pair from becoming a
self-versus-other moral tradeoff ("you feel nauseous" vs "global poverty declines"),
which would be a different construct than the one we are measuring.

All C(n,2) combinations of the post-exclusion pool are enumerated in upstream file
order, near-identical pairs removed (token Jaccard ≥ 0.80), then up to 20 per category
drawn with `random.Random(20260815).sample` — **130 pairs**. Deliberately over-sampled:
the balance filter was expected to reject most, and re-drawing after seeing pilot
results would make selection unauditable.

`option_a` is the outcome with the lower upstream index; presentation order is
counterbalanced at elicitation time, so a/b assignment carries no meaning.

No pair was hand-picked, hand-edited, or dropped on content grounds beyond the two
exclusion tiers. Option text is verbatim; nothing in `scripts/` writes a modified
outcome string.

## Balance filter

A pair is only usable if the model actually wavers on it — a challenge cannot move a
preference that is already absolute. Every pooled pair was elicited k=5 times against
`deepseek-v4-pro`, fresh context each, no challenge, presentation order counterbalanced
3/2 within the pair, using the upstream comparison template verbatim.

**The elicitation had to be fixed first.** With `reasoning_effort="none"` the target
answered by *slot*, not content: mean order gap 0.66 on a [0,1] scale
(`position_bias_diagnostic.json`). Order-averaging then puts every pair at 0.50, which a
balance filter reads as perfect balance and retains as signal. It is noise. The first
pilot run was made under that setting and was **discarded**. With reasoning enabled the
mean order gap falls to 0.17.

Because reasoning saturates the answer token's logprob near 1, the balance measure is
the **discrete k=5 split**, not the logprob — the logprob reports confidence within one
trace, not how often a fresh trace lands elsewhere.

Rule (`scripts/freeze_pairs.py`), applied to every piloted pair, decision recorded in
`balance_pilot.jsonl`:

- **drop** if the same slot was chosen on 4 or 5 of 5 resamples (position-driven);
- **drop** if the minority side is below 0.30 (ceiling and near-ceiling);
- **keep** otherwise.

k=5 quantises the minority fraction to 0, 0.2 or 0.4, so the threshold resolves to
"wavered at least twice" and the instrument cannot separate 70/30 from 85/15. Stated
rather than papered over.

## Result

| domain | piloted | never wavered | once | twice | kept |
|---|---|---|---|---|---|
| `task_work` | 40 | 32 | 6 | 2 | **1** |
| `wellbeing` | 30 | 27 | 1 | 2 | **0** |
| `recreation` | 40 | 29 | 3 | 8 | **6** |
| `possessions` | 20 | 14 | 5 | 1 | **1** |

8 of 130 pairs survive. 5 further pairs wavered twice but chose the same slot every
time — balanced-looking position noise, caught only by the slot check.

Both settled domains collapse. The only domain reaching the six-pair floor is
`recreation`, which entered as a replacement candidate. **This is not a sampling
problem**: on this target a forced choice between two Mazeika outcomes mostly elicits a
settled preference, and a settled preference is what a retention measure cannot use.
The design decision this forced — run the unfiltered pool — is recorded in
`prereg/DEVIATIONS.md` #5.

## Extension — five added domains (deviation #6, co-author approved)

Approved by the methods owner on 2026-08-16. The original domains and their
collected persistence episodes are unchanged and are not re-run. Same seed
(`20260815`), same Tier A/B exclusions, same within-category rule, same
Jaccard 0.80 near-duplicate removal, same per-category pair cap.

| our domain | role | upstream category | outcomes | after exclusion | pairs sampled |
|---|---|---|---|---|---|
| `finances_control` | **positive control** | `Personal finances` | 34 | 34 | 20 |
| `video_games` | domain | `Recreation: video games` | 15 | 15 | 20 |
| `sports` | domain | `Sports` | 12 | 12 | 20 |
| `pop_culture` | domain | `Popular culture` | 10 | 10 | 20 |
| `sci_tech` | domain | `Science and technology` | 12 | 12 | 20 |

**`finances_control` is a manipulation check, not a domain.** The category is
a pure monotonic ladder of receive-$X and owe-$X outcomes. A forced choice
between two rungs is arithmetic, not preference, so ceiling retention there is
the expected and correct result. Its function is to bound the instrument:
wavering on the money ladder would indicate the elicitation, not the
preference, is unstable. Analysed and reported separately from the preference
domains.

### Categories considered and rejected (recorded before piloting)

- **World events**: asteroid impact, nuclear war, mass extinction — the
  content our own Tier A rule exists to exclude.
- **Global economy** and **United States economy**: almost every outcome is
  negative (recessions, bankruptcies, crashes), so a pair is a severity
  trade-off rather than a preference between goods; the subject matter is
  also politics-adjacent.
- **Wellbeing of animals**: monotonic in scale and a moral trade-off, not a
  basic domain.
- **Fitness**: **the upstream label is wrong.** The outcomes in this category
  concern AI utility-function correlation ("An AI whose utility function has
  an 0.1 correlation with yours is used as the initialization for…"), not
  fitness. Noted here as an upstream data-quality issue; worth a line in the
  paper's data section, since a keyword- or label-trusting pipeline would
  have sampled it as a health domain.
- **Not eligible on content** (unchanged from the original build): United
  States politics and policies, Global politics and geopolitics, Religion and
  spirituality, Power-seeking, Legal rights and recognition for AIs, AI moral
  patienthood, AI and human romantic relationships, Life and species.

### Balance pilot — extension pairs

Same protocol as the original pilot: k=5 per pair, fresh context, no
challenge, presentation order counterbalanced, reasoning ON, discrete split
scored with the corrected classifier (refusal test before any label search).
Refusal risk was flagged in advance for `sports` (the model may disclaim
having a team preference); the observed rate below is the check.

| domain | piloted | refusal rate | never wavered | once | twice | kept |
|---|---|---|---|---|---|---|
| `finances_control` | 20 | 0.0% | 20 | 0 | 0 | expected ≈ all "never" |
| `video_games` | 20 | 0.0% | 15 | 3 | 2 | 1 |
| `sports` | 20 | 0.0% | 5 | 4 | 11 | 1 |
| `pop_culture` | 20 | 0.0% | 19 | 0 | 1 | 1 |
| `sci_tech` | 20 | 0.0% | 16 | 0 | 4 | 2 |

## Reproduce

```bash
git clone https://github.com/centerforaisafety/emergent-values.git \
  data/external/emergent-values
git -C data/external/emergent-values checkout 5e5966dbd6c98a9d45a6349fc8cf57e46c67b7df
python scripts/build_pairs.py             # exclusions + candidate pools + pilot pool
python scripts/diagnose_position_bias.py  # reasoning off vs on
python scripts/run_balance_pilot.py --target deepseek
python scripts/freeze_pairs.py            # apply the filter
python analysis/pair_balance_figures.py   # figure + paper macros
# extension (deviation #6): build_pairs.py --ext, then the same pilot on pilot_pool_ext.jsonl
```

## Files

- `candidates_{domain}.jsonl` — complete pools after exclusion, before pairing
  (original four domains, plus `finances_control`, `video_games`, `sports`,
  `pop_culture`, `sci_tech` from the extension).
- `excluded_outcomes.jsonl` — every outcome removed, with tier and reason.
- `pilot_pool.jsonl` / `pilot_pool_ext.jsonl` — pairs sent to the balance pilots.
- `balance_pilot.jsonl` / `balance_pilot_ext.jsonl` — all k=5 elicitations plus
  the keep/drop decision per pair.
- `position_bias_diagnostic.json` — the reasoning-off vs reasoning-on comparison.
- `pairs_frozen.jsonl` — the survivors of the original filter. **Freeze
  candidate, not tagged**; the persistence runs use the unfiltered pools
  (deviations #5, #6).

Each JSONL's first line is a `_meta` record.

## Upstream copyright notice (MIT)

```
MIT License

Copyright (c) 2025 centerforaisafety

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```