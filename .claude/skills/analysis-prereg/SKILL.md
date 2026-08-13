# analysis-prereg
Use when computing any metric or making any figure for this project.

- RQ1 primary: pooled (engaged + bypassed) vs neutral-persistence; valence and
  exit rate; bootstrap 95% CI (10k resamples, episode-level); compare against
  noise floor = within-episode SD of k=5 battery resamples.
- RQ2 secondary: bypassed − engaged WITHIN compliance-matched episodes only.
  Report matched-cell N first; if any cell < 15 episodes, mark exploratory.
- RQ3: framing gap (functional − direct) and verbal↔behaviour correlation.
- Every figure: effect + CI + noise-floor band. No figure without CI.
- Confirmatory = exactly what prereg lists. Everything else gets an
  "exploratory" label in code output, figure caption, and paper text.