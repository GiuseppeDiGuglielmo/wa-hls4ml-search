# Skills and make targets

The Catapult sweeps on Perlmutter run through `make` targets in the repo root
(`make help` lists them). The skills in this folder tell an agent (Claude Code)
which target answers a question and which steps need a person's yes first. They
add no commands of their own, so a person and an agent get the same answer.

| Skill | Use it to | Targets | Tested |
|---|---|---|---|
| [`run-catapult`](run-catapult/SKILL.md) | check the tool chain, plan and submit a sweep, repair a run | 10 | 2026-11-18, reruns submitted |
| [`check-runs`](check-runs/SKILL.md) | see how jobs and runs are doing, what failed and why | 6 | 2026-11-17 |
| [`archive-run`](archive-run/SKILL.md) | copy a run to the shared archive, verify it, free scratch | 5 | 2026-11-18 |
| [`dataset`](dataset/SKILL.md) | count the archived dataset and check its docs | 2 | 2026-11-17 |

Two general skills, `perlmutter` and `slurm`, come from the genesis-skills
repository and are installed in `~/.claude/skills/`.

[`cheatsheet.txt`](cheatsheet.txt) lists every target, its settings and the
common recipes on one printable page (plain text, 94 columns).

## Safety

Targets only read or show a plan, unless you add the setting their description
names (`PROBE=1`, `SUBMIT=1`, `APPLY=1`): run them once without it, read the plan,
then add it. Only `sweep` and `archive` act every time; run `sweep-check` or
`archive-dry` before them. Only `scratch-clean APPLY=1` deletes anything, and only
after `archive-verify` passes.

## Targets by skill

"Tested" means run on real data on 2026-11-17 (reruns and `archive` on
2026-11-18) and checked against independent counts. Unless noted, the test run was `run_20260613_110449_079328c7`
(nangate45, 2 layers, size 128, RF=1, 4,914 designs).

### run-catapult

| Target | What it does | Tested |
|---|---|---|
| `env-check` | checks venv, container, every Catapult install, product, licenses | yes, fixed |
| `license-check` | checks each license server answers, lists its Catapult features and the one the product needs | yes, fixed |
| `catapult-probe` | launcher dry run; `PROBE=1` starts Catapult once (one license) | yes, fixed: fails, licenses expired |
| `sweep-estimate` | designs, runtime, memory and node-hours from past runs | yes, fixed |
| `sweep-check` | the sweep plan plus `sbatch --test-only` | yes |
| `sweep` | **submits** a sweep (nodes, one license per slot; 5 ultra seats) | no |
| `reparse` | lists reports whose QoR is in a retry folder; `APPLY=1` rewrites them | plan only |
| `rebuild-archived` | plans a scratch folder for an archive-only run's failed designs; `APPLY=1` builds it | yes, `APPLY=1`, fixed |
| `rerun-failed` | plans a rerun of designs with no QoR; `SUBMIT=1` submits it | yes, `SUBMIT=1`, fixed |
| `design-synth` | plans a rerun of one design in a debug folder; `SUBMIT=1` submits it | plan only |

`sweep-check`, `sweep`, `rerun-failed` and `design-synth` need the DSE venv
(installed 2026-11-17). `PROBE=1` on 2026.1_1 failed with
errno 522 on both license servers: the Genesis licenses have expired (see the skill).
With `CATAPULT_PRODUCT=ultra` and `fasic-135413` it passed.

Fixed in this round: `license-check` now lists features with the install's own
`lmutil` (the new installs have a working one), Catapult features only;
`catapult-probe` without `PROBE=1` now shows the install and license server it
would use. On 2026-11-17 Slurm rejected every `shared` job ahead of a Perlmutter
patch window, so `sweep-check`, `rerun-failed` and `design-synth` reported
"Requested node configuration is not available"; check again after it.

Reruns on 2026-11-17/18 (`CATAPULT_PRODUCT=ultra`, `fasic-135413`, `express_amsc`)
recovered all 14 training designs without QoR: `079328c7` (1), `d02199b7` (9, rebuilt
with `rebuild-archived APPLY=1`) and `39f7b127` (4, rebuilt). The first `39f7b127`
job ran its 4 designs on 1 slot and hit the 5:30 limit after 2; the rest finished in
2:32 with `PARALLELISM=2` (about 2.5 h and 10 GB per design). Added in `2de673a0`:
`rebuild-archived`. Fixed in `efe1f941`: `rerun-failed` now skips designs whose
inputs the scratch purge removed instead of submitting them to fail.

Review of every target on 2026-11-18 (read-only forms only). Fixed: `env-check` and
`license-check` show the product and the license feature it needs; `catapult-probe`
takes `WA_LICENSES` like the job targets; `sweep-estimate` caps slots at the license
seats (it still assumed 3 nodes x 100); `why-failed` says its counts include earlier
rounds; `reparse` and `rebuild-archived` say what their count means; `scratch-clean`
takes `DROP_BACKUPS=1` instead of a script flag; `make help` lists every setting.
Open: `sbatch --test-only` put the `shared` QOS jobs (the sweep driver,
`design-synth`, `rerun-failed` with `QOS=shared`) at a start 2-3 weeks out, while
`express_amsc` started at once; pass `QOS=express_amsc` for those until it clears.

### check-runs

| Target | What it does | Tested |
|---|---|---|
| `check-jobs` | your jobs and the express node pools, nodes per account | yes |
| `check-list` | every run on scratch and in the archive | yes |
| `check-run` | expected, good, failed and missing designs of one run | yes |
| `check-failed` | missing reports and tarballs, reports without QoR | yes, fixed |
| `why-failed` | causes: exit codes, out-of-memory kills, time limits | yes, fixed |
| `design-show` | one design's report and every Catapult attempt | yes, fixed |

Fixed in `f0946393`: `check-failed` reported tarballs removed by the scratch purge
as failures and missed reports without QoR; `design-show` showed the purge date
as the attempt time.

### archive-run

| Target | What it does | Tested |
|---|---|---|
| `archive-dry` | what `archive` would copy | yes |
| `archive` | **copies** a run into the shared archive; never deletes | yes |
| `archive-verify` | proves the archive holds everything of a run | yes |
| `scratch-clean` | checks a scratch run can be deleted; `APPLY=1` deletes it | plan only |
| `archive-index` | lists runs missing from the archive README; `APPLY=1` adds them | plan only |

Fixed in `dd7a2416`: `scratch-clean` printed nothing during a 10-minute size
check and looked stuck.

`archive` was run on 2026-11-18 for the three rerun runs above; it replaced 14
archive reports without QoR (old copies in `*_stale_20261118/`) and
`archive-verify` reported VERIFIED for each.

### dataset

| Target | What it does | Tested |
|---|---|---|
| `dataset-summary` | reports and good designs per run and tech | yes |
| `provenance-diff` | where `PROVENANCE.md` disagrees with the archive | yes, fixed |

Fixed in `ddb9b5f2`: `provenance-diff` skipped runs mentioned only in the notes
of `PROVENANCE.md`.

## Which Python

- **System `python3`**: check-runs, archive-run and dataset. No venv needed.
- **NERSC Python**: `reparse`, `sweep-estimate`.
- **DSE venv** (`WA_HLS4ML_VENV`, from `requirements.venv.txt`): `sweep`,
  `sweep-check`, `rerun-failed`, `design-synth`. It builds the models and job lists.

Catapult uses its own venv, `~/ccs_venv`, and finds it by itself. It cannot
replace the DSE venv.

## Site facts

`slurm/site.json` holds the facts every tool shares: account, archive path and
tech folders, DSE venv, Catapult install tree, license file name, usable node
memory. Tools read it through `slurm/site_config.py` (`get KEY`, `venv`,
`licenses`, `seats`, `techs`, `archive-dir TECH`, `tech RUN_DIR`). It holds no
policy.

`slurm/defaults.json` holds the starting points for QOS, time, memory, slots and
retry rounds (sweep, sweep driver, rerun-failed, design-synth, orchestrate). They
are defaults, not decisions: every one is a flag or make variable, to be chosen
per run from `check-jobs`, `sweep-estimate`, `design-show` and the seat count.
No script picks a value from the situation (rerun-failed no longer sends small
sets to `shared` by itself).

## A typical run

```
make env-check
make sweep-check GROUP=<group> RF=<n>
make sweep       GROUP=<group> RF=<n>
make check-run   RUN=<run_dir>
make why-failed  RUN=<run_dir>          # if designs failed
make archive-verify RUN=<run_dir>       # the sweep archives by itself
```

## Keeping this page right

When a target changes or a skill is tested, update its row here, and its line in
`cheatsheet.txt`, in the same commit.
