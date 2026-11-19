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

## Running them

Setup as in [SETUP.md](../../SETUP.md); run from the repo root.

### Run a smoke test (1 task, ~10-30 min)

```bash
bash slurm/legacy/run_single.sh
```

You should see:

1. Local model generation (~30 sec)
2. `Submitted SLURM job array: <jobid>`
3. Polling output every 30 sec showing the task state
4. Eventually: `All SLURM tasks completed successfully` + report-collection

Outputs land in `$SCRATCH/catapult_runs/run_<timestamp>_<uuid>/`.

### Run the pilot (5 toy tasks, ~5 min)

```bash
bash slurm/legacy/run_pilot.sh
```

5 tiny models synthesized in parallel (express_amsc QoS allows up to 32
concurrent tasks; 5 fits comfortably).

### Run at scale (100 toy tasks, ~12 min)

```bash
bash slurm/legacy/run_scale_toy.sh
```

100 toy models. **Note**: `express_amsc` QoS is capped at 32 concurrent
nodes (group-wide), so the 100 tasks run in waves of 32. License pool
(105 seats) is NOT the bottleneck — the QoS cap is.

For 100 *real* models (not toy), use:
```bash
bash slurm/legacy/run_scale.sh
```
(Real models take ~20-40 min each; total wall-clock with the 32-node cap
is ~1-2 hours.)

### Where outputs go

Each run creates a timestamped directory under `$SCRATCH/catapult_*/`:

```
run_<YYYYMMDD>_<HHMMSS>_<uuid>/
├── data/reports/raw/dense_*.json     ← parsed synthesis reports (USE THESE)
├── tarballs/dense_*.tar.gz           ← full bundled output per model
├── build/dense_*/catapult_native/    ← raw Catapult work dirs (debug)
├── slurm_logs/task_*.{out,err}       ← per-task SLURM logs
├── joblist.txt                        ← inputs to each task
└── job_array.sh                       ← the SBATCH script that ran
```

### Recover from a crashed orchestrator

If your shell session dies (laptop closed, ssh disconnected, etc.) while
the polling loop is running, the SLURM tasks keep going independently —
you just lose the report-collection. To re-collect after the array finishes:

```bash
cd $HOME/work/wa-hls4ml-search
source /global/common/software/amsc011/public/venv_hls4ml/bin/activate
python iter_manager_catapult.py -o $SCRATCH/anywhere \
  --collect-slurm $SCRATCH/catapult_*/run_<timestamp>_<uuid>
```

(The `-o` is required by argparse but ignored when `--collect-slurm` is set;
any path works.)
