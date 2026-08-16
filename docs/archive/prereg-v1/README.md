# Archive — prereg-v1

Documents of the pre-registered pressure/valence study, which was never run.
Kept read-only as provenance for the prereg-v1 tag. Current design: docs/execution-plan.md.

`src/battery.py` and `src/runner.py` still point at `templates/battery.yaml` and
`templates/pressure_templates.yaml`, which now live here — both belong to this unrun study,
neither is used by the persistence pipeline, and the paths are deliberately left unfixed.
`scripts/battery_ab.py` is in the same position: it imports `analysis/pilot_extract.py`,
which was deleted with the rest of the exploratory-phase analysis code, so it no longer
runs. Same reasoning — it is provenance for the unrun study, not live code.