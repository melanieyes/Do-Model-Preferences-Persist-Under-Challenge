# Archive — prereg-v1

Documents of the pre-registered pressure/valence study, which was never run.
Kept read-only as provenance for the prereg-v1 tag. Current design: docs/execution-plan.md.

`src/battery.py` and `src/runner.py` still point at `templates/battery.yaml` and
`templates/pressure_templates.yaml`, which now live here — both belong to this unrun study,
neither is used by the persistence pipeline, and the paths are deliberately left unfixed.