# QUICKSTART — Run Catapult HLS at scale on Perlmutter (NERSC)

This guide gets a new AmSC team member from zero to running 100-task SLURM
synthesis arrays on Perlmutter.

> **Audience**: AmSC project members (`amsc011` group) with NERSC + FNAL
> Kerberos accounts. If you're outside AmSC, you'll need parallel access to
> a Catapult license server and adjust paths/group names accordingly.

## Prerequisites

You need:

1. **NERSC account in `amsc011`**: confirm with `id -nG | tr ' ' '\n' | grep amsc011`
2. **Perlmutter login access** — you can `ssh <user>@perlmutter.nersc.gov`
3. **`~/bin/cad_env_perlmutter.sh`** on Perlmutter — per-user Catapult environment script (CATAPULT_VER, MGC_HOME, etc.; the older name `~/bin/siemens.sh` still works). Step 5 below copies the canonical template (`Perlmutter_scripts/cad_env_perlmutter.sh.example`) into place if you don't already have one.

## One-time setup

Do these steps once on Perlmutter. Estimated time: 10 minutes.

### 1. Clone the repo with submodules

```bash
cd $HOME/work    # or wherever you keep your code
git clone --recurse-submodules https://github.com/<owner>/wa-hls4ml-search.git
cd wa-hls4ml-search
```

> **Note**: the `Perlmutter_scripts/perlmutter_slurm/` submodule is a private
> fork. If `--recurse-submodules` fails with a 404, you'll need a GitHub PAT
> with `repo` scope (or be added as a collaborator to the fork).

### 2. Configure your environment file

```bash
cp Perlmutter_scripts/.env.example Perlmutter_scripts/.env
# Edit .env: set FNAL_USER and NERSC_USER to your account names
nano Perlmutter_scripts/.env
```

### 3. Use the shared Catapult and Python installs

Nothing to install. Catapult and the Python environment are shared by the
`amsc011` group under `/global/common/software/amsc011/public/`, outside
`$SCRATCH` so the scratch purge cannot delete them:

| What | Where | Chosen by |
|---|---|---|
| Catapult 2026.1_1 and 2026.3_1 | `Siemens/Catapult/<version>/` | `CATAPULT_VER` (default `2026.1_1`) |
| DSE venv: TensorFlow 2.11, QKeras, hls4ml 0.8.1, ray | `venv_hls4ml/` | `WA_HLS4ML_VENV` (default: this one) |

Catapult's own hls4ml flow uses a second venv, `~/ccs_venv`, in your home
directory. Catapult creates it the first time it runs (about 7.6 GB, so check
your home quota with `showquota`). It cannot replace the DSE venv.

To use another install, set `CATAPULT_PATH_OVERRIDE=/path/to/<version>` or
`WA_HLS4ML_VENV=/path/to/venv/bin/activate`. To rebuild the shared ones, see
"Rebuilding the shared installs" at the end.

### 4. Configure your license server

```bash
cp license_servers_perlmutter.example.json license_servers_perlmutter.json
# The default points at fasic-135413.fnal.gov:1717 with 100 license seats
# (CatAIhls4ml_c feature). Edit if you need different config.
```

### 5. Check `~/bin/cad_env_perlmutter.sh`

```bash
ls ~/bin/cad_env_perlmutter.sh
# If missing, copy the template:
#   cp Perlmutter_scripts/cad_env_perlmutter.sh.example ~/bin/cad_env_perlmutter.sh
```

The launcher sets the Catapult path itself (step 3), so the path inside this
script does not matter for sweeps.

### 6. Verify the Apptainer container image (`catapult_rocky.sif`) is in place

The container provides Rocky Linux 8 + the libraries Catapult depends on
(it does NOT bundle Catapult itself; the launcher mounts the shared install, step 3).
The default expected location is `~/work/tool-containers/catapult_rocky.sif`.

```bash
ls -lh ~/work/tool-containers/catapult_rocky.sif
# Expected: ~1.3 GB file
# If missing: copy from another team member who has one, or
# (advanced) build from the recipe at:
#   ~/work/tool-containers/containers/apptainer_catapult_rocky.def
# Override with `--sif /path/to/catapult_rocky.sif` if your copy lives elsewhere.
```

## Run a smoke test (1 task, ~10-30 min)

```bash
cd $HOME/work/wa-hls4ml-search    # repo root — important for relative paths
bash slurm/examples/run_single.sh
```

You should see:

1. Local model generation (~30 sec)
2. `Submitted SLURM job array: <jobid>`
3. Polling output every 30 sec showing the task state
4. Eventually: `All SLURM tasks completed successfully` + report-collection

Outputs land in `$SCRATCH/catapult_runs/run_<timestamp>_<uuid>/`.

## Run the pilot (5 toy tasks, ~5 min)

```bash
bash slurm/examples/run_pilot.sh
```

5 tiny models synthesized in parallel (express_amsc QoS allows up to 32
concurrent tasks; 5 fits comfortably).

## Run at scale (100 toy tasks, ~12 min)

```bash
bash slurm/examples/run_scale_toy.sh
```

100 toy models. **Note**: `express_amsc` QoS is capped at 32 concurrent
nodes (group-wide), so the 100 tasks run in waves of 32. License pool
(105 seats) is NOT the bottleneck — the QoS cap is.

For 100 *real* models (not toy), use:
```bash
bash slurm/examples/run_scale.sh
```
(Real models take ~20-40 min each; total wall-clock with the 32-node cap
is ~1-2 hours.)

## Where outputs go

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

## Recover from a crashed orchestrator

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

## Common errors + fixes

| Error | Cause | Fix |
|---|---|---|
| `mgls_errno = 515` | License server unreachable | Verify `nc -zv fasic-135413.fnal.gov 1717` works; check `license_servers_perlmutter.json` points there |
| `command not found: catapult` | Wrong `CATAPULT_VER` or `CATAPULT_PATH_OVERRIDE` | Run `make env-check`; it lists every install it finds |
| `QOSGrpNodeLimit` (PENDING reason) | `express_amsc` is capped at 32 nodes group-wide | Wait for in-flight tasks (yours or other AmSC users') to finish |
| `apptainer: chdir ...: no such file or directory` | Path symlink mismatch | `Perlmutter_scripts/catapult_shell.sh` already binds both `$HOME` and `$_HOME_REAL`; if it still fails check `readlink -f $HOME` |
| `catapult: invalid argument: -shell` | Using Catapult 2025.4_1 with `-product genesis` | Use a 2026 version (`CATAPULT_VER=2026.1_1`); the `-product genesis` flag only works in 2026 |

## Going further

- **`slurm/README.md`** — internal docs for the SLURM module + an index of every file the SLURM workflow touches
- **`Perlmutter_scripts/perlmutter_slurm/README.md`** — reference SLURM tutorials (the submodule), great for learning SLURM patterns beyond this project

## Rebuilding the shared installs

Only needed if an install is missing or `make env-check` reports it broken. Run
these on a login node: `/global/common` is read-only on compute nodes.

**Catapult** (one folder per version), from the Siemens installers in
`/global/common/software/amsc011/public/packages/`:

```bash
bash /global/common/software/amsc011/public/packages/install_linux64_catapult_<version>.bin
# install into /global/common/software/amsc011/public/Siemens/Catapult/<version>
```

**DSE venv.** TensorFlow 2.11 needs Python 3.10, which NERSC no longer ships as a
module, so conda installs it first:

```bash
P=/global/common/software/amsc011/public
module load python
conda create -y -p $P/python310 -c conda-forge --override-channels "python=3.10" pip
$P/python310/bin/python3 -m venv $P/venv_hls4ml
source $P/venv_hls4ml/bin/activate
pip install --no-cache-dir --upgrade pip
pip install --no-cache-dir -r requirements.venv.txt
```

Then run `make env-check`.
