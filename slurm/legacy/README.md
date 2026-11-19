# `slurm/legacy/` — launchers from before the sweep catalog

These drive `iter_manager_catapult.py` directly (some through the `--slurm`
job-array path in `slurm/job_array.py`) with the legacy random-sampling model
generator configs, which `slurm/sweeps.tsv` does not model. New campaigns use
`make sweep` instead. Run them from the repo root.

- `run_single.sh`, `run_pilot.sh`, `run_scale_toy.sh`, `run_scale.sh`: pipeline
  smoke tests (1, 5 toy, 100 toy, 100 real designs).
- `run_bram_test_{small,medium,large,xl,xxl}.sh` over `common/bram_test.sh`:
  BramFactor checks; output in `$SCRATCH/catapult_runs_bramtest/`, never archived.
- `run_dense_1to3layers.sh`: produced one archived legacy run
  (`run_20260506_074423_a88bd7d9`); see PROVENANCE.md group 7.

They take the venv from `slurm/site_config.py venv` and the license servers
from `license_servers_perlmutter.json`, like the sweep.
