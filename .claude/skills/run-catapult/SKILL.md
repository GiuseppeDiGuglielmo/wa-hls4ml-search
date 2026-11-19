---
name: run-catapult
description: >-
  Facts and gates for running Catapult HLS synthesis for wa-hls4ml on Perlmutter:
  checking the tool chain (make env-check, license-check, catapult-probe), how the
  launcher starts Catapult (Apptainer container, Catapult install, license servers),
  estimating, checking and submitting a design-space sweep (make sweep-estimate,
  sweep-check, sweep), and repairing a run (make reparse, rerun-failed,
  design-synth). Use when asked to run Catapult, plan or start a sweep, rerun failed
  designs, debug one design, or check that Catapult and its licenses work.
---

# Running Catapult

Synthesis spends shared licenses and node hours, so it has gates. Free checks
first, then a plan the user approves, then the action.

## Before anything runs

1. `make env-check`: venv imports, container, Apptainer, Catapult install, env
   script, license file, product and license seats, GNU parallel, launcher dry run.
   Every line must be OK.
   It also detects purge damage (see below). Read-only, ~20 s.
2. `make license-check [LMUTIL=<path>]`: each license server answers on its port,
   and its Catapult features, using the selected install's `lmutil`. On
   2026-11-17 `fasic-admin1` (the sweep server) listed 200 `CatAIhls4ml_c` and 200
   `CatUltrGenesis_c` as "unsupported by licensed server" (FlexLM cannot count
   SALT features; only `catapult-probe PROBE=1` proves a checkout);
   `fasic-135413` (the env script's server) has 5 `CatAIhls4ml_c`, 5
   `CatapultUltra_c` and no Genesis feature. After the features, a `product` line
   says which feature `CATAPULT_PRODUCT` needs and how many are issued and in use
   (WARN when the server lacks it).
3. `make catapult-probe`: launcher dry run. `make catapult-probe PROBE=1` starts
   Catapult once (one license, seconds) and must print `catapult-probe: OK`. Ask
   before PROBE=1. `WA_LICENSES=port@host` overrides the license file here too.

## A sweep

1. `make sweep-estimate GROUP=<group> [RF= NODES=]`: designs per RF from the catalog,
   and runtime, peak memory, slots per node and node-hours from past runs still on
   scratch. Slots per node fit both the p90 memory and the license seats (same
   defaults as `sweep`: 1 node, seats from the license file, so 5 with ultra).
   Rough; says when there is no past data.
2. `make sweep-check GROUP=<group> [RF= QOS= TIME= NODES= PARALLELISM= MEM= MEMFREE=]`:
   the plan, plus `sbatch --test-only` of a synthesis job and of the sweep driver.
   Builds no models, submits nothing. Show it to the user.
3. `make sweep GROUP=<group> [same options]` only after the user says yes. Then follow
   it with the check-runs skill and archive it with the archive-run skill.

Groups and their design spaces are rows of `slurm/sweeps.tsv`
(`bash slurm/sweep.sh <group> --list`). Never edit an existing row: stems are indices
into it (see `slurm/examples/PROVENANCE.md`).

## Repairing a run

Each target prints a plan and changes nothing without its flag; show the plan, wait
for a yes, then rerun with the flag.

- `make reparse RUN=<run_dir> [APPLY=1] [WORKERS=8]`: designs whose report lacks QoR
  while a `Catapult_N` retry folder has it get their report and tarball rewritten
  (old files to `*_stale_<date>/`, log `reparsed_<date>.tsv`). No synthesis. Uses
  NERSC's Python with TensorFlow stubbed, so it works without the venv. For hundreds
  of designs it prints an sbatch line to run it on a compute node instead.
- `make rerun-failed RUN=<run_dir> [SUBMIT=1] [QOS= TIME= MEM= PARALLELISM=]`: designs
  with no QoR in any attempt are synthesised again in one job (old report/tarball
  moved to `*_stale_<tag>/` so they are not skipped). QOS, TIME, MEM and
  PARALLELISM default to `slurm/defaults.json` and are yours to choose per run:
  the plan prints the design count and seats, `check-jobs` shows the queues,
  `design-show` a design's peak memory. On `shared` MEM defaults to 24G per slot;
  on a whole node GNU parallel `--memfree` gates each start. Run reparse first;
  rerun-failed skips designs reparse can fix.
- `make rebuild-archived RUN=<archive run name> [APPLY=1]` (`Designs 0 ...; nothing
  to rebuild` when every archived design has QoR): for a run that exists only
  in the archive, recreates its original scratch folder (path from `source_dir.txt`)
  with just the designs without QoR: `keras_model.h5` from a scratch run of the same
  group at any RF, else `model[_<i>].json` + weights from a tarball of another RF;
  `dataflow_config.json` from the base flow config with the catalog's overrides for
  the RF (identical to what the sweep wrote, checked 2026-11-17). Refuses if the
  folder exists. Then `make rerun-failed RUN=<that folder>`, and archive as usual.
- `make design-synth RUN=<run_dir> STEM=<stem> [SUBMIT=1] [QOS= MEM= TIME=]`: one design
  again in a fresh `$SCRATCH/catapult_debug/run_*` (original untouched), under
  `/usr/bin/time -v`. Then `make design-show RUN=<debug run> STEM=<stem>`.

`sbatch --test-only` start estimates for `shared` can be months off (seen 2026-11-05);
past shared jobs started within hours. On 2026-11-17, before the `scrambled_patch`
reservation (2026-11-18 07:00-19:00), every `shared` test failed with "Requested node
configuration is not available" while `regular` was accepted: a machine state, not
a script bug. `sweep-check`, `rerun-failed` and `design-synth` all report it.

## How Catapult is started

Each joblist line names `Perlmutter_scripts/catapult_shell.sh`. It runs
`apptainer exec --contain` (Apptainer from CVMFS or the module) on
`~/work/tool-containers/catapult_rocky.sif`, a Rocky Linux 8.10 image with the
libraries Catapult needs. Catapult itself is not in the image: it is
`/global/common/software/amsc011/public/Siemens/Catapult/$CATAPULT_VER`
(2026.1_1 by default; 2026.3_1 also installed), bound read-only into the container.
`CATAPULT_PATH_OVERRIDE` points at another install; it wins over the path in the
env script.
Inside, the launcher sources `~/bin/cad_env_perlmutter.sh` (older name
`~/bin/siemens.sh`; `CAD_ENV_SCRIPT=` overrides), then re-exports `CATAPULT_PATH`
and the license variables and runs `catapult -product ultra -shell`
(`CATAPULT_PRODUCT=genesis` for Genesis).
`Correlator4_scripts/` is the Fermilab variant, not used here.

Licenses: sweeps and `catapult-probe PROBE=1` take `LM_LICENSE_FILE` from
`license_servers_perlmutter.json` (gitignored, per user); the env script has its
own server, which the launcher overrides.

**Scratch purge.** Files unread for 8 weeks on `$SCRATCH` are deleted. On
2026-11-05 this had gutted both the Catapult install (820 files left, 712 dangling
links) and the venv (Python reads `.pyc`, so `.py` sources looked unread and went).
Symptom: `import tensorflow` fails; `make env-check` reports it. Both now live outside `$SCRATCH`, in `/global/common/software/amsc011/public`:
Catapult per version, and the DSE venv `venv_hls4ml` (TensorFlow 2.11 needs Python
3.10, installed with conda as `python310`). QUICKSTART's "Rebuilding the shared
installs" has the commands; rebuilding is the user's call.

**errno 522 is the license, not the install.** `mgls_errno = 522` "License server
does not support this feature (CatapultGenesis)" means no server offers a valid
Genesis license; `-product genesis` needs it. Check expiry with
`<install>/Mgc_home/bin/lmutil lmstat -i -c <port@host>`. On 2026-11-17 the probe
failed on both servers: `fasic-admin1` lists `CatUltrGenesis_c` and
`CatAIhls4ml_c` that expired 2026-07-01 (200) and 2026-09-15 (100); `fasic-135413`
has `CatAIhls4ml_c` x5 to 2027-05-31 and no Genesis feature. June runs used
`fasic-admin1` while it was valid. Renewal is for FNAL/Siemens; no sweep can run
until then.

**Ultra by default.** Since 2026-11-18 the launcher runs `catapult -product ultra`
(CatapultUltra license) unless `CATAPULT_PRODUCT=genesis`, and
`license_servers_perlmutter.json` (gitignored; template in the `.example` file)
lists `fasic-135413` with 5 seats. `fasic-135413` has only 5 `CatapultUltra_c` (to
2027-05-31), so at most 5 designs run at once: `sweep` and `rerun-failed` default to
as many slots as the file lists seats and refuse more (`sweep`: nodes x slots). A
full group (4,914 designs at ~2.5 h each for 2-layer sz128) is out of reach until
Genesis is renewed; then set the file back to `fasic-admin1` with its seat count and
pass `CATAPULT_PRODUCT=genesis`. Ultra results matched Genesis (June's
`dense_2l_sz128_2970`: area 195491 vs 195490), and the 14 reruns of 2026-11-17/18
ran as ultra. `rerun-failed` and `design-synth` also take `WA_LICENSES=port@host`
to override the file.

**Two venvs.** The DSE venv (`WA_HLS4ML_VENV`) builds models and job lists outside
the container. Catapult's own hls4ml flow uses `~/ccs_venv`, which Catapult creates
and finds by itself; its Python comes from inside the 2026.1_1 install. One cannot
replace the other (`~/ccs_venv` has no ray and TensorFlow 2.15).

## What a sweep does

`slurm/sweep.sh` (the sbatch'd driver; `DRIVER_QOS= DRIVER_TIME= DRIVER_MEM=`)
builds the models and joblist under `$SCRATCH/catapult_<group>_rf<RF>/run_*/`, then
`slurm/sweeplib/orchestrate.sh` submits one job per node (nodes, slots, QOS, time,
memory and `--memfree` as given, else the `sweep` defaults in `slurm/defaults.json`;
slots never exceed the license seats), waits, resubmits rounds until the tarball
count stops rising (`MAX_ROUNDS`, default in the same file), and finally copies
the run into the archive with `archive_sync.py --apply`
(never deletes scratch). A design already holding a tarball is never rerun. The
loop does not diagnose what is left: it writes `<run>/sweep_summary.tsv` (designs,
with tarball, retry rounds, `stopped` = complete / no_progress / max_rounds, job
ids, settings, archive_sync exit code), which `make check-run` shows as its
"sweep loop" line. What to do next is decided from there, with `why-failed`.

Catapult peak memory per design is <2 GB to ~19 GB (largest for 128-wide layers);
too many slots per node gets designs OOM-killed (exit 137) and retried. Queue and
QOS limits (express pools, max wall times) are in the perlmutter skill;
`sweep-check` surfaces violations such as `QOSMaxWallDurationPerJobLimit`.

`slurm/legacy/run_single.sh` is an older one-design smoke test through the
`--slurm` job-array path, not the sweep path above.
