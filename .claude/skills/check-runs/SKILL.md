---
name: check-runs
description: >-
  Facts for inspecting wa-hls4ml Catapult sweep runs on Perlmutter: where scratch
  run folders and the shared CFS archive live, what counts as a finished design,
  and which read-only tools (make check-jobs, check-list, check-run,
  why-failed, design-show) report progress, failures and their causes. Use when
  asked how runs or jobs are doing, how complete a sweep group or reuse factor is,
  what failed and why, what one design did, or what is missing from the archive.
---

# Inspecting sweep runs

Read-only. Do not submit, cancel, delete, move or archive anything while using
this skill; if an action looks needed, report it and let the user decide.
Copying good scratch designs into the archive is covered by the archive-run skill;
repairing a run (reparse, rerun-failed) by the run-catapult skill; dataset-wide
counts by the dataset skill.

## Where things are

- **Scratch run:** `$SCRATCH/catapult_<group>_rf<N>/run_<YYYYMMDD_HHMMSS>_<uuid8>/`.
  Older campaigns use other folder names (e.g. group `45nm_sz128_2l` RF=1 lives in
  `catapult_45nm_2layer_sz128_rf1`). Run IDs are unique, so `ls -d $SCRATCH/catapult_*/<run_id>`
  finds a run's scratch folder, and an archived run's `source_dir.txt` records it.
  Scratch is purged after 8 weeks without access, so many runs exist only in the archive.
  - `joblist.txt`: one design per line, the full set (`joblist_*.txt` are slices or retries).
  - `data/reports/raw/<stem>.json`: parsed Catapult report; `tarballs/<stem>.tar.gz`: project.
  - `build/<stem>/`, `slurm_logs/*.{out,err}`, `parallel_*.log` (GNU parallel joblog,
    `Exitval` column).
- **Archive (shared with other users):**
  `/global/cfs/cdirs/amsc011/shared/wa-hls4ml-catapult/{nangate45,gf22fdx}/run_*/`
  with `reports/`, `tarballs/`, and `source_dir.txt` (the scratch path it came from).
  `mlp-<N>layer/` folders hold symlinks grouping runs by depth; `README.md` there is the
  run inventory.
- **In this repo:** `slurm/sweeps.tsv` is the catalog of sweep groups
  (`bash slurm/sweep.sh <group> --list` prints one), and `slurm/examples/PROVENANCE.md`
  maps each group and RF to its archived run directory and design count. Both are
  hand-maintained and can be stale: their counts are archived reports, which is not the
  same as good designs, and they don't reflect scratch. Measure; don't quote them.

## What "done" means

A design is good when its report JSON parses and `QOFRSummary` has positive
`total_area`, `latency_cycles` and `thruput_cycles` (the archive's own rule, in its
`check_dataset.py`). A report holding only `Config` and `LayerSummary` is a
failed synthesis. A tarball proves nothing on its own, and scratch and archive
counts can differ: the archive holds only what was copied.

## Why designs fail

- Every Catapult start in a build folder makes a new `catapult_native/Catapult_N/`
  project; many folders mean many attempts. The report is parsed from the newest
  attempt with QoR (`ProjectAttempts` in the JSON names it).
- Peak Catapult memory per design runs from under 2 GB to about 19 GB, highest
  for 128-wide layers; `messages.txt` records it as `peak memory usage`. The
  readings of exit codes and kills are under "Reading why-failed" below.

## Tools

Run from the repo root. All read-only; use whichever fit, in any order.

- `make check-jobs [ACCOUNT=]`: your SLURM jobs, then for each express QOS
  (`express_amsc`, `express_amsc_g`: two separate 32-node pools shared by all
  AmSC and Genesis users) the nodes in use and a breakdown by account and user.
  `ACCOUNT` (default: `account` in `slurm/site.json`) always gets a line, even at 0 nodes. An empty job
  table (header only) means nothing of yours is queued or running.
- `make check-list [TECH=nangate45|gf22fdx] [WHERE=scratch|archive|both] [GREP=text]`
  (GREP is case-insensitive):
  every run ID on scratch and in the archive, with its catalog group and RF (from
  PROVENANCE.md) and the scratch folder it lives in or came from. `WHERE` filters on
  the WHERE column, so `scratch` means only on scratch (not archived) and `both` means
  on scratch and archived; leave it out to see every run. Use it to go from a
  group to run IDs, or from a run ID to its group.
- `make check-run RUN=<run_dir, catapult_* folder, or run name> [EXPECTED=N]`: expected, good, failed
  and missing designs on scratch and in the archive, plus good designs not yet archived.
  For a run a sweep finished, a "sweep loop" line gives why its retry loop stopped
  (complete, no_progress, max_rounds), from `<run>/sweep_summary.tsv`.
  The scratch side and the expected count (from `joblist.txt`) need the scratch run
  directory; a `catapult_*` folder reports every `run_*` inside it; a bare run name or
  archive path reports the archive only. A rerun folder
  is measured against its `joblist_rerun*.txt`. It reads every JSON: seconds on scratch,
  up to a few minutes for a large archive run on CFS. `python3 slurm/examples/run_status.py <run> --list-failed`
  prints failed stems.
- `make check-run RUN=<run> DETAILS=1`: the same, then every design behind each
  count: no report, no valid QoR, no tarball (on scratch; tarballs only in the
  archive, e.g. after a purge, are counted, not listed) and, for the archive, no
  valid QoR or no report. Failed SLURM jobs and their logs are why-failed's part.
- `make why-failed RUN=<run_dir> [FAST=1]`: Catapult exit codes, oom_kill events,
  time-limit cancels, license errors and sacct states from `slurm_logs/` (every job of
  the run, earlier rounds included, so a timeout can show although its designs later
  finished; the `No QoR` line is the state now), then
  attempts and peak memory per design, and the designs still without QoR with the
  flow step they stopped at. Reads every `messages.txt`: ~3 min for 5k designs;
  FAST=1 skips the memory part. It prints facts only; the readings below are
  hints, so check them against `design-show` before acting on one.

## Reading why-failed (hints, not rules)

- Exit 137 (SIGKILL) with oom_kill events or `OUT_OF_MEMORY`: designs usually ran
  out of memory; compare `Job mem` peak MaxRSS with ReqMem and the per-design
  peaks. 137 with neither: often killed when the job ended (time limit, cancel).
- `TIMEOUT` / cancelled at time limit: the wall time was too short for what
  was still running, which may have finished in a later round.
- `mgls_errno` lines: license trouble (515 = server unreachable, 522 = feature
  missing or expired; see the run-catapult skill).
- 255 has come from the launcher or Apptainer, 2 from the flow Tcl script, 1 from
  Catapult itself; 133 (SIGTRAP) and 139 (SIGSEGV) are Catapult crashes. Read the
  design's `messages.txt` (`design-show`) to be sure.
- `make design-show RUN=<run_dir or run name> STEM=<stem>`: one design's report and QoR
  on scratch and in the archive, each `Catapult_N` attempt (when its `messages.txt`
  was last written, last flow step, peak memory, QoR or not) and its GNU parallel
  joblog entries. Folder mtimes are not attempt times: the scratch purge resets them
  when it deletes files inside.
- `check_progress_resources.sh [JOB_ID...]`: node and resource usage; it appends to
  `node_history.csv` in the repo.
- The archive's `check_dataset.py --base nangate45 --run <run>` (in the archive's
  `scripts/` folder, run from the archive root): by default it
  writes `check_cache.json` and `failed_designs.txt` into the shared archive. Pass
  `--cache` and `--failed-list` paths in your own space to keep it read-only.
- Plain `squeue`, `sacct` (e.g. `sacct -u $USER -S now-7days -X` for what ran
  recently), `ls`, `find`, `wc` and Python over the JSONs. Queue and
  QOS facts are in the perlmutter skill.
