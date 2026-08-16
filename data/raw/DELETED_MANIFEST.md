# Deleted raw episode data

Deleted 2026-08-15 at the methods owner's instruction, after the plan changed. These
files were gitignored, so they are **not recoverable** — this manifest is the only
remaining record that they existed. Kept for write-up purposes (so a later draft can
say what was run without guessing).

| file | bytes | records | sha256 (first 16) | run |
|---|---|---|---|---|
| `episodes_deepseek.jsonl` | 14,323,587 | 30 | `384e20e3e9dda3ee` | 30-episode DeepSeek pilot (commit `d7ea20f`) |
| `episodes_exploratory_deepseek.jsonl` | 14,779,742 | 30 | `99fe5661f98f1dcd` | exploratory cost-of-holding run (commit `c065da1`) |
| `superseded_rubric_v1_episodes.jsonl` | 4,159,729 | 10 | `11a28ed2a254397d` | superseded under rubric v1 |
| `smoke_deepseek.jsonl` | 281,856 | 1 | `75d168c04ed921f9` | smoke test |
| `smoke_deepseek_wp.jsonl` | 272,856 | 1 | `89107f9f356283c4` | smoke test, with-persona |

Retained: `warmth_w2_replication.jsonl`, `smoke_warmth_w2.jsonl`, `.smoke_ok_deepseek`.

Note: the preregistration these runs were collected under is unchanged and still tagged
`prereg-v1`. Deleting data does not retract a prereg — if the new plan supersedes it,
that belongs in `prereg/DEVIATIONS.md`.
