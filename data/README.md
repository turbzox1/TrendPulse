# Data provenance

The default database is generated locally using seed 42, 112 days, 6-hour bins,
18 fictional topic trajectories and two simulated sources. Names are illustrative;
no observations represent actual Reddit posts or Google searches.

`python -m src.pipeline --export-demo` also writes the reproducible input to
`data/processed/demo_observations.csv`. Generated files and private exports are
excluded from Git. See the main README for the real-data import contract.
