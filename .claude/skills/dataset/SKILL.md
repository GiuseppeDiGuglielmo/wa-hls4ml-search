---
name: dataset
description: >-
  Facts about the archived wa-hls4ml Catapult dataset as a whole: how it is laid out
  by technology and run, what a good design is, which documents describe it
  (PROVENANCE.md, the archive README) and how stale they can be, and the read-only
  tools that measure it (make dataset-summary, provenance-diff, check-list). Use when
  asked how big the dataset is, how many good designs a tech, group or RF has,
  whether the docs match the archive, or which runs to use for training.
---

# The archived dataset

Read-only. Measure; don't quote the documents.

## Layout

`/global/cfs/cdirs/amsc011/shared/wa-hls4ml-catapult/` (shared with other users):
- `nangate45/` and `gf22fdx/`: one `run_<YYYYMMDD_HHMMSS>_<uuid8>/` per sweep run at
  one reuse factor, each with `reports/<stem>.json`, `tarballs/<stem>.tar.gz` and
  `source_dir.txt` (its scratch origin). Some hold `reports_stale_*`/`tarballs_stale_*`
  backups and `archive_sync.log` from later repairs.
- `README.md`: hand-written index with per-run notes (weights fixed vs programmable,
  completeness); `scripts/` there holds `check_dataset.py` (its own validator; writes
  caches into the archive unless given paths elsewhere) and transfer scripts; `backup/`.

Stems are `dense_<N>l_<index>`, the index into the catalog row's design space, so a
design is identified by (run, stem); the same stem in another run is another RF or
tech. The catalog is `slurm/sweeps.tsv`; `slurm/examples/PROVENANCE.md` maps each
group and RF to its archived run and design count.

## What counts

A design is good when its report has positive `total_area`, `latency_cycles` and
`thruput_cycles` in `QOFRSummary` (run_status.is_good, mirroring check_dataset.py). A
report without them is a failed synthesis; reports and good designs differ.
Measure counts with the tools below; never quote a remembered number.

Not every archived run is training data. Runs that PROVENANCE.md names only in its
prose notes (shown as `see PROVENANCE note` in the group column) are excluded:
legacy fixed-weight runs `run_20260504_205339_a5d590d6`, `run_20260505_145920_de8c3504`,
`run_20260506_074423_a88bd7d9` (1,101 designs, generating commands not recorded), the
superseded partial `run_20260507_143427_1450d680`, and four empty gf22fdx "ghost"
runs from 2026-06-06. Check the notes before counting a run as training data. A
failed design in an excluded run needs no rerun.

## Tools

- `make dataset-summary [TECH=] [FAST=1]`: per archive run its catalog group/RF, reports,
  good designs and tarballs, then totals per tech. Good counts read every report
  once (the first full run reads ~550k JSONs on CFS, tens of minutes), then come from
  `~/.cache/wa-hls4ml/run_counts.json` while a run's reports folder is unchanged.
  FAST=1 gives file counts only, in seconds.
- `make provenance-diff [FAST=1]`: runs where PROVENANCE.md's design count differs
  from the archive's report count, runs with designs lacking QoR or with tarball and
  report counts that differ, runs marked partial that are complete, and archive runs
  PROVENANCE does not list. Runs named only in its notes have no count to compare and
  are checked for missing QoR and tarballs only. FAST=1 skips the QoR check.
- `make check-list`, `make check-run RUN=<run name>`: from the check-runs skill, for
  one run.
- `make archive-index`: from the archive-run skill, runs the README does not mention.
