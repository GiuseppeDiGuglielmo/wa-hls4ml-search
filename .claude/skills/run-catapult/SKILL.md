---
name: run-catapult
description: >-
  Facts and gates for running Catapult HLS synthesis for wa-hls4ml on Perlmutter:
  how the launcher starts Catapult (Apptainer container, Catapult install and
  license servers), how to probe it (make catapult-probe), and how to check and
  submit a design-space sweep (make sweep-check, make sweep). Use when asked to run
  Catapult, start or plan a sweep, rerun a sweep group or reuse factor, or check
  that Catapult and its licenses work.
---

# Running Catapult

Synthesis spends shared licenses and node hours, so it has gates:

1. `make catapult-probe`: dry run of the launcher; costs nothing.
   `make catapult-probe PROBE=1` starts Catapult once (one license, seconds) and
   must print `catapult-probe: OK`. Ask before running it, and do it before a sweep.
2. `make sweep-check GROUP=<group> [RF= QOS= TIME= NODES= PARALLELISM= MEM= MEMFREE=]`:
   prints the plan and validates the synthesis job script and the sweep driver with
   `sbatch --test-only`. Builds no models, submits nothing. Show the output to the user.
3. `make sweep GROUP=<group> [same options]` only after the user says yes to that
   plan. Afterwards use the check-runs skill to follow it, and the archive-run skill
   for the archive.

Groups and their design spaces are rows of `slurm/sweeps.tsv`
(`bash slurm/sweep.sh <group> --list`). Never edit an existing row: stems are indices
into it (see `slurm/examples/PROVENANCE.md`).

## How Catapult is started

Each joblist line names `Perlmutter_scripts/catapult_shell.sh`. It runs
`apptainer exec --contain` (Apptainer from CVMFS or the module) on
`~/work/tool-containers/catapult_rocky.sif`, a Rocky Linux 8.10 image with the
libraries Catapult needs. Catapult itself is not in the image: it is
`$SCRATCH/cad/Siemens/Catapult/2026.1_1` (purged after 8 weeks unread), reached
through the `/pscratch` bind. Inside, the launcher sources
`~/bin/cad_env_perlmutter.sh` (older name `~/bin/siemens.sh`; `CAD_ENV_SCRIPT=`
overrides), then re-exports `CATAPULT_PATH` and the license variables and runs
`catapult -product genesis -shell`. `Correlator4_scripts/` is the Fermilab variant,
not used here.

Licenses: sweeps and `catapult-probe PROBE=1` take `LM_LICENSE_FILE` from
`license_servers_perlmutter.json` (gitignored, per user); the env script has its own
server, which the launcher overrides. `mgls_errno = 522` / "License server does not
support this feature (CatapultGenesis)" means the server answered but lacks the
feature: a license problem for the FNAL license admins, not a script bug.

## What a sweep does

`slurm/sweep.sh` (the sbatch'd driver, `--qos shared`, 2 days) builds the models and
joblist under `$SCRATCH/catapult_<group>_rf<RF>/run_*/`, then
`slurm/sweeplib/orchestrate.sh` submits one job per node (default 3 nodes x 100
slots, `express_amsc`, 05:30:00, whole-node memory, GNU parallel `--memfree 64G`),
waits, resubmits rounds until the tarball count stops rising (`MAX_ROUNDS`, default
20), and finally copies the run into the archive with `archive_sync.py --apply`
(never deletes scratch). A design already holding a tarball is never rerun.

Catapult peak memory per design is <2 GB to ~19 GB (largest for 128-wide layers);
too many slots per node gets designs OOM-killed (exit 137) and retried. Queue and
QOS limits (express pools, max wall times) are in the perlmutter skill;
`sweep-check` surfaces violations such as `QOSMaxWallDurationPerJobLimit`.

`slurm/examples/run_single.sh` is an older one-design smoke test through the
`--slurm` job-array path, not the sweep path above.
