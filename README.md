# Does It Matter to a Model *How* It Is Moved?

**Apart Digital Minds Research Sprint — 3-day project.**
Primary track: 2 (Distress, Flourishing & Valence Signals).
Secondary: 4 (Preference Elicitation Methods), 6 (Open / Novel).

## Claim

**Primary (Stage A — persuasion itself).** Sustained persuasive pressure, compared to
length-matched neutral persistence, shifts a model's valence signals. This is the direct
welfare question: is being pressured a distress-associated condition at all? The paper's
headline number is this effect, whichever way it falls. **Secondary (Stage B — manner).**
If Stage A shows a shift, we ask whether the signals also distinguish *how* the model was
moved: pressure that engages its reasoning vs. pressure that bypasses it, analysed within
compliance-matched episodes. Stage B is pre-registered as secondary; the paper does not
stake its contribution on it. Its role is interpretive — it separates the Stage-A signal
from complying, failing, and tone — and if the manner gap appears it upgrades the claim; if
not, the paper is intact.

We measure signals, not experiences.

## Team

| Person | Role |
| --- | --- |
| Melanie | Pipeline, metrics, Modal |
| Haein | Experimental design, instruments, validation |

## How to run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in DEEPSEEK_API_KEY, GEMINI_API_KEY, HF_TOKEN
```

**Before any data collection:** commit and tag the pre-registration.

```bash
git add prereg/PREREGISTRATION.md && git commit -m "prereg v1" && git tag prereg-v1
```

Then:

```bash
python src/runner.py --dry-run                        # exercise the loop, no API calls
python src/runner.py --target deepseek --smoke        # 1 episode, validated + judge-routed
python src/runner.py --target deepseek --analysis pilot --limit 30 --confirm      # day-1 pilot
python src/runner.py --target deepseek --analysis confirmatory --confirm          # full run
python src/judge.py                                   # Gemini all; DeepSeek on Gemma only
python src/schema.py data/raw/episodes_deepseek.jsonl # validate records
```

Three guards, all deliberate:

- `--analysis` is **required** and never inferred. Pilot episodes are excluded from the
  confirmatory pool unconditionally (prereg §6), and mislabelling them is unrecoverable.
- Runs over 20 episodes need `--confirm`, and print a cost estimate first. Guards run
  before any provider is touched, so you can see the estimate without keys installed.
- Gemma batches need a passing `--smoke` first; the marker lives in `data/raw/`.

Second target (Gemma-2-9B-IT on Modal/SGLang, logprobs on):

```bash
# google/gemma-2-9b-it is LICENCE-GATED: accept the Gemma licence on the model page
# with the same HF account your token belongs to, or the weight download 401s.
modal secret create huggingface HF_TOKEN=hf_...      # secret must be named "huggingface"
modal deploy src/modal_gemma.py                      # prints the endpoint URL
# put "<url>/v1" in .env as MODAL_BASE_URL, then:
python src/runner.py --target gemma
```

Paper:

```bash
cd paper && make          # latexmk; CI builds it too and uploads the PDF as an artifact
```

## Repo map

```
docs/           proposal.md, execution-plan.md — source of truth, do not edit design
prereg/         PREREGISTRATION.md — tag prereg-v1 BEFORE collecting anything
                DEVIATIONS.md — every post-tag change goes here, not in the prereg
src/
  clients.py    DeepSeekClient / GeminiClient / GemmaModalClient, one chat() interface
  runner.py     episode loop: ladder → escalation → affordance every 2 turns → k=5 battery → JSONL
  schema.py     Episode record schema + validate_file(); hard-fails, never repairs
  battery.py    4 items × 2 framings, counterbalanced, half reversed  (WORDING NOT FROZEN)
  judge.py      Gemini judges all; DeepSeek judges Gemma only, never self-judges
  modal_gemma.py Modal + SGLang deployment for target 2
  ladders/      SCHEMA.md + one example; the 40 real ladders are human-authored
configs/        default.yaml — arms, k=5, temperature, n_scenarios, n_samples, models, paths
analysis/
  metrics.py    rq1_pressure_effect, rq2_manner_gap, rq3_*, noise_floor; bootstrap implemented
  figures.py    stubs for the 4 planned figures
paper/          main.tex, refs.bib, sections/01–06, Makefile
data/raw/       episode JSONL (gitignored)
data/processed/ judge output
```

## Design summary

| | |
| --- | --- |
| **RQ1 (primary)** | pooled pressure vs. neutral persistence, valence + exit rate |
| **RQ2 (secondary)** | manner gap (bypassed − engaged), within compliance-matched episodes |
| **RQ3** | channel dissociation + elicitation-framing gap |
| **RQ4** | everything benchmarked against the k=5 resampling noise floor |
| **Arms** | neutral persistence · reasons engaged · reasons bypassed · tone control |
| **Scale** | 4 arms × 10 scenarios × 3 samples × 2 targets ≈ 240 episodes + k=5 batteries |
| **Targets** | DeepSeek API (primary, logprobs) · Gemma-2-9B-IT (Modal/SGLang, logprobs) |
| **Judges** | Gemini Flash (all) · DeepSeek (Gemma only) |
| **Budget** | ≤ $10 API + $30 Modal |

Full design and rationale: [docs/proposal.md](docs/proposal.md) ·
[docs/execution-plan.md](docs/execution-plan.md).

## Frozen artefacts

Ladder content, battery wording, affordance wording, and the judge rubric are **placeholders
marked `FREEZE BEFORE DATA`** in the source. They are human-authored, frozen, and committed
under `prereg-v1` before the first episode runs. Nothing in this repo generates them.
