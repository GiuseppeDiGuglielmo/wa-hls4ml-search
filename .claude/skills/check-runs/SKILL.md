---
name: check-runs
description: >-
  Facts for inspecting wa-hls4ml Catapult sweep runs on Perlmutter: where scratch
  run folders and the shared CFS archive live, what counts as a finished design,
  and which read-only tools (make check-jobs, check-list, check-run, check-failed) report
  progress and failures. Use when asked how runs or jobs are doing, how complete a
  sweep group or reuse factor is, what failed, or what is missing from the archive.
---

# Inspecting sweep runs

Read-only. Do not submit, cancel, delete, move or archive anything while using
this skill; if an action looks needed, report it and let the user decide.

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
`total_area`, `latency_cycles` and `thruput_cycles` (the archive's own rule, in
`scripts/check_dataset.py`). A report holding only `Config` and `LayerSummary` is a
failed synthesis. A tarball proves nothing on its own, and scratch and archive
counts can differ: the archive holds only what was copied.

## Tools

Run from the repo root. All read-only; use whichever fit, in any order.

- `make check-jobs [ACCOUNT=<acct>]`: your SLURM jobs, then for each express QOS
  (`express_amsc`, `express_amsc_g`: two separate 32-node pools shared by all
  AmSC and Genesis users) the nodes in use and a breakdown by account and user,
  marking `ACCOUNT` (default `amsc011`).
- `make check-list [TECH=nangate45|gf22fdx] [WHERE=scratch|archive|both] [GREP=text]`:
  every run ID on scratch and in the archive, with its catalog group and RF (from
  PROVENANCE.md) and the scratch folder it lives in or came from. Use it to go from a
  group to run IDs, or from a run ID to its group.
- `make check-run RUN=<run_dir or run name> [EXPECTED=N]`: expected, good, failed
  and missing designs on scratch and in the archive, plus good designs not yet archived.
  The scratch side and the expected count (from `joblist.txt`) need the scratch run
  directory; a bare run name reports the archive only. Takes seconds to a minute. `python3 slurm/examples/run_status.py <run> --list-failed`
  prints failed stems.
- `make check-failed RUN=<run_dir>`: missing reports or tarballs and failed SLURM tasks,
  with the tail of their `.err` logs. Writes nothing.
- `check_progress_resources.sh [JOB_ID...]`: node and resource usage; it appends to
  `node_history.csv` in the repo.
- Archive `scripts/check_dataset.py --base nangate45 --run <run>`: by default it
  writes `check_cache.json` and `failed_designs.txt` into the shared archive. Pass
  `--cache` and `--failed-list` paths in your own space to keep it read-only.
- Plain `squeue`, `sacct` (e.g. `sacct -u $USER -S now-7days -X` for what ran
  recently), `ls`, `find`, `wc` and Python over the JSONs. Queue and
  QOS facts are in the perlmutter skill.
