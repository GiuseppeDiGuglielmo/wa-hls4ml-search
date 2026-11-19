# Setup: Catapult HLS on Perlmutter (NERSC)

Do this once per person. It gets a new AmSC team member from zero to a tool chain
that `make env-check` passes; [SWEEP_GUIDE.md](SWEEP_GUIDE.md) then runs a sweep.

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
| Catapult, one folder per version (`make env-check` lists them) | `Siemens/Catapult/<version>/` | `CATAPULT_VER` (default: `catapult version` in `slurm/defaults.json`) |
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
# List each license server and its seat count; every job's slots are capped at
# the total. make license-check shows what each server offers and has in use.
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

## Check it works

```bash
make env-check              # every line OK: venv, container, Catapult install, env script, license file, launcher
make license-check          # each server answers; the product line shows seats issued and in use
make catapult-probe PROBE=1 # starts Catapult once (one license, seconds); must print catapult-probe: OK
```

Then run a sweep: [SWEEP_GUIDE.md](SWEEP_GUIDE.md).

## Common setup errors

| Error | Cause | Fix |
|---|---|---|
| `mgls_errno = 515` | License server unreachable | Verify `nc -zv <host> 1717`; check `license_servers_perlmutter.json` |
| `mgls_errno = 522` | No valid license for the product (e.g. expired) | `make license-check`; `CATAPULT_PRODUCT=` picks ultra or genesis |
| `command not found: catapult`, dangling links | Wrong `CATAPULT_VER`, or a purged install | `make env-check` lists every install it finds and spots purge damage |
| `import tensorflow` fails | venv damaged (e.g. by the scratch purge) | `make env-check`; see "Rebuilding the shared installs" |
| `apptainer: chdir ...: no such file or directory` | Path symlink mismatch | `Perlmutter_scripts/catapult_shell.sh` binds both `$HOME` and `$_HOME_REAL`; check `readlink -f $HOME` |

## Going further

- [SWEEP_GUIDE.md](SWEEP_GUIDE.md): add, run, archive and record a sweep
- [`slurm/README.md`](slurm/README.md): the code behind the make targets
- [`slurm/legacy/README.md`](slurm/legacy/README.md): the older job-array smoke tests
- `Perlmutter_scripts/perlmutter_slurm/README.md`: reference SLURM tutorials (submodule)

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
