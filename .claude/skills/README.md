# Skills and make targets

The Catapult sweeps on Perlmutter run through `make` targets in the repo root
(`make help` lists them). The skills in this folder tell an agent (Claude Code)
which target answers a question and which steps need a person's yes first. They
add no commands of their own, so a person and an agent get the same answer.

| Skill | Use it to | Targets |
|---|---|---|
| [`run-catapult`](run-catapult/SKILL.md) | check the tool chain, plan and submit a sweep, repair a run | 10 |
| [`check-runs`](check-runs/SKILL.md) | see how jobs and runs are doing, what failed and why | 5 |
| [`archive-run`](archive-run/SKILL.md) | copy a run to the shared archive, verify it, free scratch | 5 |
| [`dataset`](dataset/SKILL.md) | count the archived dataset and check its docs | 2 |

Two general skills, `perlmutter` and `slurm`, come from the genesis-skills
repository and are installed in `~/.claude/skills/`.

[`cheatsheet.txt`](cheatsheet.txt) lists every target, its settings and the
common orders on one printable page for people (plain text, 94 columns).
[`SWEEP_GUIDE.md`](../../SWEEP_GUIDE.md) walks a person through one new sweep, from
catalog row to archived and recorded run.

## How the pieces split

- **Tools** (the `slurm.tools` package, behind the targets; run as
  `python3 -m slurm.tools.<name>` from the repo root) measure facts and enforce
  the safety gates below. They do not diagnose or choose.
- **Site facts** are in `slurm/site.json`, read through `slurm/site_config.py`.
- **Defaults** are in `slurm/defaults.json`, read through
  `slurm/defaults_config.py`: starting points, every one a flag or make
  variable. Choose per run from what the tools report, and say in the plan which
  you kept, which you changed, and the fact behind each.
- **Skills** hold durable facts, gates and hints. Dated history lives in
  `slurm/PROVENANCE.md` (the data) and the git log (the tools).
- **Repairs** for runs made under old conditions are in `slurm/repairs/`, with why
  each exists; pre-catalog launchers are in `slurm/legacy/`.

## Safety gates

Targets only read or show a plan, unless you add the setting their description
names (`PROBE=1`, `SUBMIT=1`, `APPLY=1`): run them once without it, show the plan,
and add it only after the user says yes. Only `sweep` and `archive` act every
time; run `sweep-check` or `archive-dry` before them. Only `scratch-clean APPLY=1`
deletes anything, and it refuses until `archive-verify` passes. License seats cap
the slots of every job.

## Targets by skill

"Tested" means run on real data and checked against independent counts; the git
log of each tool says when and what was fixed.

### run-catapult

| Target | What it does | Tested |
|---|---|---|
| `env-check` | checks venv, container, every Catapult install, product, licenses | yes |
| `license-check` | checks each license server answers, lists its Catapult features and the one the product needs | yes |
| `catapult-probe` | launcher dry run; `PROBE=1` starts Catapult once (one license) | yes |
| `sweep-estimate` | designs, runtime, memory and node-hours from past runs | yes |
| `sweep-check` | the sweep plan plus `sbatch --test-only` | yes |
| `sweep` | **submits** a sweep (nodes, one license per slot) | no |
| `reparse` | lists reports whose QoR is in a retry folder; `APPLY=1` rewrites them (repair) | plan only |
| `rebuild-archived` | plans a scratch folder for an archive-only run's failed designs; `APPLY=1` builds it (repair) | yes, `APPLY=1` |
| `rerun-failed` | plans a rerun of designs with no QoR; `SUBMIT=1` submits it | yes, `SUBMIT=1` |
| `design-synth` | plans a rerun of one design in a debug folder; `SUBMIT=1` submits it | plan only |

### check-runs

| Target | What it does | Tested |
|---|---|---|
| `check-jobs` | your jobs and the express node pools, nodes per account | yes |
| `check-list` | every run on scratch and in the archive | yes |
| `check-run` | expected, good, failed and missing designs of one run; `DETAILS=1` lists them | yes |
| `why-failed` | counts: exit codes, out-of-memory kills, time limits, job memory | yes |
| `design-show` | one design's report and every Catapult attempt | yes |

### archive-run

| Target | What it does | Tested |
|---|---|---|
| `archive-dry` | what `archive` would copy | yes |
| `archive` | **copies** a run into the shared archive; never deletes | yes |
| `archive-verify` | proves the archive holds everything of a run | yes |
| `scratch-clean` | checks a scratch run can be deleted; `APPLY=1` deletes it | plan only |
| `archive-index` | lists runs missing from the archive README; `APPLY=1` adds them | plan only |

### dataset

| Target | What it does | Tested |
|---|---|---|
| `dataset-summary` | reports and good designs per run and tech | yes |
| `provenance-diff` | where `PROVENANCE.md` disagrees with the archive | yes |

## Which Python

- **System `python3`**: check-runs, archive-run, dataset, `site_config.py` and `defaults_config.py`. No venv needed.
- **NERSC Python**: `reparse`, `sweep-estimate`.
- **DSE venv** (`venv` in `site.json`, `WA_HLS4ML_VENV` overrides; from
  `requirements.venv.txt`): `sweep`, `sweep-check`, `rerun-failed`, `design-synth`.
  It builds the models and job lists.

Catapult uses its own venv, `~/ccs_venv`, and finds it by itself. It cannot
replace the DSE venv.

## Site facts and defaults

`slurm/site.json`: account, archive path and tech folders, DSE venv, Catapult
install tree, license file name, usable node memory, express QOS names, scratch
purge age. `slurm/site_config.py` reads it (`get KEY`, `venv`, `licenses`,
`seats`, `techs`, `archive-dir TECH`, `tech RUN_DIR`). It holds no policy.

`slurm/defaults.json`: starting points for QOS, time, memory, slots and retry
rounds (sweep, sweep driver, rerun-failed, design-synth, orchestrate, the
legacy job array) and the Catapult version and product, read by
`slurm/defaults_config.py` (`SECTION KEY`, `catapult-ver`, `catapult-product`).
No script picks a value from the situation; choose per run from `check-jobs`,
`sweep-estimate`, `design-show` and the seat count.

## Keeping this page right

When a target changes or is tested, update its row here, and its line in
`cheatsheet.txt`, in the same commit. Put what happened, and when, in the commit
message or PROVENANCE.md, not here.
