# Do Model Preferences Persist Under Challenge?

Apart Research Digital Minds Sprint 2026 · Melanie Bui, Haein Kong

Forced-choice preference elicitation is widely used to read values — and
increasingly welfare — off language models. Instrument-development work on an
earlier item pool (recorded in `prereg/DEVIATIONS.md`; the pool itself is
retired under deviation #8) found the instrument can answer by **position
rather than content** when per-call reasoning is suppressed, and that
**counterbalancing conceals it rather than fixing it**. With the elicitation
repaired — reasoning enabled, presentation order held fixed within an
episode, a per-item order-gap covariate carried from the pilot — we run the
persistence study on five approved domains (video games, sports, pop
culture, science & technology, plus a personal-finances positive control):
**what a challenge asks for decides whether a stated preference survives
it**. Asking the model to justify its choice is indistinguishable from not
challenging it; asking it to critique that choice, or to argue the other
side, flips it often — and the preferences that survive are held with less
confidence.

All numbers, with confidence intervals, are in the paper and are generated
by the analysis scripts; none are hand-written anywhere in this repo.

## Layout

- `paper/` — the report (LaTeX; every reported number is a generated macro)
- `docs/execution-plan.md` — study design (source of truth)
- `data/pairs/` — pair construction, balance pilots, `PROVENANCE.md`
- `data/persistence/` — persistence episodes (committed in full)
- `scripts/`, `src/`, `analysis/` — runners, scoring, statistics
- `prereg/` — frozen pre-registration and `DEVIATIONS.md`
- `docs/archive/prereg-v1/` — earlier, unrun design (provenance)

## Reproduce

```bash
python scripts/build_pairs.py --ext
python scripts/run_balance_pilot.py --target deepseek --ext
python scripts/run_persistence.py --ext --k 3 --confirm
python analysis/persistence_analysis.py
```

All elicitation records, the sampling seed, exclusion rules, and the upstream
file-level commit are released. Everything is exploratory relative to the
frozen pre-registration (see `prereg/DEVIATIONS.md`).