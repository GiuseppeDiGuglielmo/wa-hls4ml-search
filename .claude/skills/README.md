# Skills and make targets

The Catapult sweeps on Perlmutter run through `make` targets in the repo root
(`make help` lists them). The skills in this folder tell an agent (Claude Code)
which target answers a question and which steps need a person's yes first. They
add no commands of their own, so a person and an agent get the same answer.

| Skill | Use it to | Targets | Tested |
|---|---|---|---|
| [`run-catapult`](run-catapult/SKILL.md) | check the tool chain, plan and submit a sweep, repair a run | 9 | not yet |
| [`check-runs`](check-runs/SKILL.md) | see how jobs and runs are doing, what failed and why | 6 | 2026-11-17 |
| [`archive-run`](archive-run/SKILL.md) | copy a run to the shared archive, verify it, free scratch | 5 | 2026-11-17 |
| [`dataset`](dataset/SKILL.md) | count the archived dataset and check its docs | 2 | 2026-11-17 |

Two general skills, `perlmutter` and `slurm`, come from the genesis-skills
repository and are installed in `~/.claude/skills/`.

## Safety

Every target falls into one of three kinds:

- **read**: changes nothing. Run it any time.
- **flag**: prints a plan and acts only with `PROBE=1`, `SUBMIT=1` or `APPLY=1`.
  Read the plan first.
- **acts**: `sweep` and `archive` act every time. Run `sweep-check` or
  `archive-dry` first.

Only `scratch-clean APPLY=1` deletes anything, and only after `archive-verify` passes.

## Targets by skill

"Tested" means run on real data on 2026-11-17 and checked against independent
counts. Unless noted, the test run was `run_20260613_110449_079328c7`
(nangate45, 2 layers, size 128, RF=1, 4,914 designs).

### run-catapult

| Target | What it does | Kind | Tested |
|---|---|---|---|
| `env-check` | checks venv, container, Catapult install, licenses | read | no |
| `license-check` | checks each license server answers | read | no |
| `catapult-probe` | dry run of the launcher; `PROBE=1` starts Catapult once (one license) | flag | no |
| `sweep-estimate` | designs, runtime, memory and node-hours from past runs | read | no |
| `sweep-check` | the sweep plan plus `sbatch --test-only` | read | no |
| `sweep` | submits a sweep (nodes, up to 300 licenses) | acts | no |
| `reparse` | fixes reports whose QoR is in a retry folder | flag | no |
| `rerun-failed` | resubmits designs with no QoR anywhere | flag | no |
| `design-synth` | reruns one design in a separate debug folder | flag | no |

`sweep-check`, `sweep`, `rerun-failed` and `design-synth` need the DSE venv, which
is not installed yet.

### check-runs

| Target | What it does | Kind | Tested |
|---|---|---|---|
| `check-jobs` | your jobs and the express node pools | read | yes |
| `check-list` | every run on scratch and in the archive | read | yes |
| `check-run` | expected, good, failed and missing designs of one run | read | yes |
| `check-failed` | missing reports and tarballs, reports without QoR | read | yes, fixed |
| `why-failed` | causes: exit codes, out-of-memory kills, time limits | read | yes |
| `design-show` | one design's report and every Catapult attempt | read | yes, fixed |

Fixed in `f0946393`: `check-failed` reported tarballs removed by the scratch purge
as failures and missed reports without QoR; `design-show` showed the purge date
as the attempt time.

### archive-run

| Target | What it does | Kind | Tested |
|---|---|---|---|
| `archive-dry` | what `archive` would copy | read | yes |
| `archive` | copies a run into the shared archive, never deletes | acts | no |
| `archive-verify` | proves the archive holds everything of a run | read | yes |
| `scratch-clean` | deletes a scratch run once it is verified | flag | plan only |
| `archive-index` | runs missing from the archive README | flag | plan only |

Fixed in `dd7a2416`: `scratch-clean` printed nothing during a 10-minute size
check and looked stuck.

### dataset

| Target | What it does | Kind | Tested |
|---|---|---|---|
| `dataset-summary` | reports and good designs per run and tech | read | yes |
| `provenance-diff` | where `PROVENANCE.md` disagrees with the archive | read | yes, fixed |

Fixed in `ddb9b5f2`: `provenance-diff` skipped runs mentioned only in the notes
of `PROVENANCE.md`.

## Which Python

- **System `python3`**: check-runs, archive-run and dataset. No venv needed.
- **NERSC Python**: `reparse`, `sweep-estimate`.
- **DSE venv** (`WA_HLS4ML_VENV`, from `requirements.venv.txt`): `sweep`,
  `sweep-check`, `rerun-failed`, `design-synth`. It builds the models and job lists.

Catapult uses its own venv, `~/ccs_venv`, and finds it by itself. It cannot
replace the DSE venv.

## A typical run

```
make env-check
make sweep-check GROUP=<group> RF=<n>
make sweep       GROUP=<group> RF=<n>
make check-run   RUN=<run_dir>
make why-failed  RUN=<run_dir>          # if designs failed
make archive-verify RUN=<run_dir>       # the sweep archives by itself
```

Do not use `slurm/examples/archive_run.sh`: with `--yes` it deletes the scratch run.

## Keeping this page right

When a target changes or a skill is tested, update its row here in the same commit.
