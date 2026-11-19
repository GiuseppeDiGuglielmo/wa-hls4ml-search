# Sweep guide: add, run and archive a Catapult sweep

How to take a new design space from a catalog row to archived, recorded results
on Perlmutter. One-time setup (accounts, license file, container, env script) is in
[SETUP.md](SETUP.md); do that first.

Every command runs from the repo root. `make help` lists all targets; targets only
read or print a plan unless you add the flag their description names (`SUBMIT=1`,
`APPLY=1`, `PROBE=1`). The worked example throughout is `demo_1l_20`, a 20-design
sweep run on 2026-11-19.

| Step | Command | Changes anything? |
|---|---|---|
| 0. Tool chain works | `make env-check`, `make license-check` | no |
| 1. Add a catalog row | edit `slurm/sweeps.tsv` | the catalog |
| 2. Estimate | `make sweep-estimate GROUP=` | no |
| 3. Plan | `make sweep-check GROUP=` | no |
| 4. Submit | `make sweep GROUP=` | **submits jobs, spends licenses** |
| 5. Watch | `make sweep-watch GROUP=`, `make check-run RUN=` | no |
| 6. Record | `make archive-verify`, PROVENANCE.md, `make archive-index APPLY=1` | docs, archive README |

## 0. Check the tool chain

```
make env-check            # venv, container, Catapult install, license file, launcher: every line OK
make license-check        # each license server answers; the product line shows seats issued / in use
make catapult-probe PROBE=1   # optional: starts Catapult once (one license, seconds); must print OK
```

The license seats are the real limit on a sweep: each running Catapult holds one.
`license-check` prints how many the product needs and how many are in use
(5 `CatapultUltra_c` seats as of 2026-11).

## 1. Add a catalog row

A sweep is one row of [`slurm/sweeps.tsv`](slurm/sweeps.tsv), the catalog of design
spaces. **Append a new row; never edit, reorder or merge existing rows.** A design's
name (`dense_1l_7`) is its index in its row's design space, and the archive is keyed
on those names.

Columns, tab-separated:

| Column | Example | Meaning |
|---|---|---|
| group | `demo_1l_20` | a new, unique name |
| tech | `nangate45` | `nangate45` or `gf22` |
| input | `4-8` | input size range; ranges expand to the powers of two inside (4, 8) |
| layers | `4-8` | one range per dense layer, comma-separated (`4-64,4-64` = 2 layers) |
| bitwidths | `4,6,8,10,12` | list |
| acts | `relu` | activations, in mask order |
| rf | `1` | reuse factors; each RF becomes its own run |
| mode | `cartesian` | `cartesian` (every combination), `lhs_nlayer`, `cart_sz128`, `archive_lhs` (sampled; see the catalog header) |
| candidates | `-` | sampled modes only: the frozen design list in the archive |
| legacy | `-` | old config this row replaced; `-` for new rows |
| notes | `20-design demo sweep` | free text |

For a cartesian row the design count is the product of the value counts:
2 inputs x 2 layer sizes x 5 bitwidths x 1 activation = 20 designs per RF.

Append with `printf`, which writes real tabs (some editors turn tabs into spaces):

```
printf 'demo_1l_20\tnangate45\t4-8\t4-8\t4,6,8,10,12\trelu\t1\tcartesian\t-\t-\t20-design demo sweep\n' >> slurm/sweeps.tsv
bash slurm/sweep.sh demo_1l_20 --list     # prints the parsed row; "unknown group" = not saved or not tab-separated
```

`python slurm/tests/check_design_space.py` (in the DSE venv) checks that the
catalog still describes exactly the archived design space; run it after touching
`slurm/sweeps.tsv`. It must print `design space unchanged`.

## 2. Estimate

```
make sweep-estimate GROUP=demo_1l_20 RF=1
```

Prints the design count per RF and, from past runs of the group still on scratch,
runtime, peak memory, slots per node and node-hours. A new group has no past data
(`no past data`); look at a similar group for orders of magnitude (one-layer
4-8 wide: ~4-5 min and 1.6 GB per design; two-layer with 128-wide layers: ~2.5 h and
up to ~19 GB). With 5 seats, throughput is 5 designs at a time whatever the
node count, so 4,914 designs at 2.5 h take months; ask before planning that.

## 3. Plan

```
make sweep-check GROUP=demo_1l_20 RF=1
```

Builds nothing, submits nothing. It prints the resolved row, the plan (nodes x
slots, memory, QOS, time, output folder, license) and `sbatch --test-only` answers
for the two jobs a sweep needs. The `Job <id> to start at ...` lines are test answers,
not jobs.

Every setting starts from [`slurm/defaults.json`](slurm/defaults.json) and is a
make variable you may override. Choose each from a fact, and write down why:

| Setting | Default | Decide from |
|---|---|---|
| `NODES` | 1 | seats: nodes x slots may not exceed them |
| `PARALLELISM` | seats / nodes | seats; fewer if memory is tight |
| `QOS`, `TIME` | `express_amsc`, 05:30:00 | `make check-jobs` (pool use), runtime x designs / slots; designs above ~6 h need `regular` and a longer time |
| `MEM`, `MEMFREE` | 0 (whole node), 64G | peak memory from step 2; `MEM` is required with `QOS=shared` |
| `DRIVER_QOS`, `DRIVER_TIME` | `shared`, 2 days | **the driver must start before anything else does**; check its estimate |

The sweep driver is the job that builds the models and submits the synthesis jobs,
so its start time is the sweep's start time. `--test-only` estimates for `shared`
can be days off. For a short sweep, `DRIVER_QOS=express_amsc DRIVER_TIME=06:00:00`
starts at once but holds a whole node for the driver; for a long one, keep `shared`
with a time that covers all retry rounds. Re-run `sweep-check` with your choices:

```
make sweep-check GROUP=demo_1l_20 RF=1 DRIVER_QOS=express_amsc DRIVER_TIME=06:00:00
```

## 4. Submit

```
make sweep GROUP=demo_1l_20 RF=1 DRIVER_QOS=express_amsc DRIVER_TIME=06:00:00
```

Prints `Submitted batch job <id>`. Then, without you:

1. The driver builds the models and a joblist under
   `$SCRATCH/catapult_<group>_rf<RF>/run_<date>_<time>_<id>/`.
2. It submits a synthesis job per node; GNU parallel runs one Catapult per slot.
3. It waits, then resubmits designs still without a tarball, until all have one or
   the count stops rising (at most `MAX_ROUNDS`, default 20). A design that has a
   tarball is never rerun.
4. It copies the run into the shared archive
   (`/global/cfs/cdirs/amsc011/shared/wa-hls4ml-catapult/<tech>/run_*`). It never
   deletes scratch.
5. It writes `<run>/sweep_summary.tsv`: designs, with tarball, retry rounds, why it
   stopped (`complete`, `no_progress`, `max_rounds`), job ids, settings, archive exit code.

## 5. Watch

```
make sweep-watch GROUP=demo_1l_20 RF=1     # live view; quits by itself when the sweep is done (Ctrl-C any time)
```

It redraws every 10 seconds (`EVERY=`) from the files the sweep writes, and waits if
the driver has not created the run folder yet:

```
Sweep demo_1l_20 rf1   run_20261119_083102_e5f26068   08:41:07   (every 10s, Ctrl-C quits)

Jobs      synthesis  61582403  demo_1l_20_rf1_a         RUNNING     9:20  nid200196
          driver     61582376  sweep                    RUNNING    10:52  nid200022
Round     [round 0] Submitted: 61582403

Progress  [██████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 10/20 good
          10 good   0 failed (no valid QoR)   5 running   5 not started   tarballs 10

Running   dense_1l_10 1:12   dense_1l_11 1:12   dense_1l_12 1:11   dense_1l_13 1:11
          dense_1l_14 1:11
Runtime   p50 4.4 min   p90 5.2 min   max 5.2 min   (10 finished: exit 0 x10)
Estimate  ~8:10 to go (10 left x 4.6 min mean / 5 slots), around 08:49
```

`ONCE=1` prints one snapshot instead (for a log or a script). The plain views still work:

```
make check-jobs                                   # your jobs and the express node pools
tail -20 logs/sweep_<driver job id>.out           # driver: models, joblist, run folder, rounds
make check-run RUN=$SCRATCH/catapult_demo_1l_20_rf1/run_<...>    # good / failed / missing, sweep loop line
```

`logs/sweep_<id>.err` is noisy: `libcudart`, `libnvinfer`, `CUDA_ERROR_NO_DEVICE`
(TensorFlow looking for a GPU on a CPU node), `Lambda fuctions ...` and
`keras dict linear` are harmless. The synthesis job's own logs are in
`<run>/slurm_logs/`; `Catapult product license successfully checked out` in
`parallel_*.out` there means Catapult got a seat.

When it is done, `check-run` shows a line like
`sweep loop: stopped complete after 0 retry round(s) (max 20), 20/20 with tarball, archive_sync exit 0`.

If designs are missing or failed:

```
make why-failed RUN=<run>                 # exit codes, OOM kills, time limits, job memory (facts only)
make design-show RUN=<run> STEM=<stem>    # one design's report and every Catapult attempt
make check-run RUN=<run> DETAILS=1        # the designs behind each count
```

Then repair (each prints a plan first; add the flag after reading it):
`make reparse RUN=<run> [APPLY=1]` for results hidden in a retry folder,
`make rerun-failed RUN=<run> [SUBMIT=1]` to synthesize designs without QoR again,
`make design-synth RUN=<run> STEM=<stem> [SUBMIT=1]` to debug one design. After a
repair, archive again: `make archive-dry RUN=<run>`, then `make archive RUN=<run>`.

## 6. Verify and record

```
make archive-verify RUN=<run>     # must print VERIFIED: the archive holds everything this scratch run has
```

Record the run in [`slurm/PROVENANCE.md`](slurm/PROVENANCE.md): add a row to the
table of the section it belongs to (or a new section), with group, RF, run
directory, design count and status, and a line on how it was run. The tools already
know the group from the run's `catapult_<group>_rf<N>` folder;
PROVENANCE.md is the human record, and `make provenance-diff` lists archive runs it
does not mention yet.

```
| Catalog group | RF | Archived run directory | Designs | Status |
|---|---|---|---|---|
| `demo_1l_20` | 1 | `run_20261119_083102_e5f26068` | 20 | ✅ |
```

Then the archive's own index, and the commit:

```
make archive-index            # the row it would append to the archive README
make archive-index APPLY=1    # appends it (backup copy first)
git add slurm/sweeps.tsv slurm/PROVENANCE.md
git commit                    # one commit: the catalog row and its provenance
```

## Later: freeing scratch

Scratch is purged after 8 weeks unread, and only `scratch-clean` deletes a run:

```
make scratch-clean RUN=<run>          # refuses unless archive-verify passes; says what it would delete
make scratch-clean RUN=<run> APPLY=1  # deletes the scratch run
```

It also refuses while scratch-only backups (`*_stale_*` from repairs) exist, unless
you add `DROP_BACKUPS=1`.

## The example, end to end

`demo_1l_20` (2026-11-19): 20 designs, RF 1, 1 node x 5 slots on `express_amsc`,
driver on `express_amsc`. Driver 19 min, synthesis job 17 min (4 waves of 5),
3.6-5.2 min and 1.6 GB per design, 0 retry rounds, 20/20 good, archived
(`nangate45/run_20261119_083102_e5f26068`) and verified.

## More

- [`.claude/skills/README.md`](.claude/skills/README.md): every target, what it changes, whether it is tested
- [`.claude/skills/cheatsheet.txt`](.claude/skills/cheatsheet.txt): one printable page
- [`slurm/README.md`](slurm/README.md): the files behind the targets
- `.claude/skills/run-catapult/SKILL.md`: licenses, the launcher, scratch purge, errno 522
