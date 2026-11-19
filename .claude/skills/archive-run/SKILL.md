---
name: archive-run
description: >-
  Facts and gates for copying a wa-hls4ml Catapult scratch run into the shared CFS
  archive with make archive-dry / make archive (copy only, backs up stale archive
  reports), proving the copy with make archive-verify, freeing scratch with make
  scratch-clean (the only deleting target), and listing runs the archive README
  misses (make archive-index). Use when asked to archive a run, sync scratch results
  to the archive, replace stale archive reports, check that a run is safely
  archived, free scratch space, or update the archive's run index.
---

# Archiving a sweep run

The archive is shared with other users and is the dataset of record. Writing to it
is an action, so it has gates:

1. Run `make archive-dry RUN=<scratch run_dir>` and show the user its output.
2. Copy only after the user says yes to that plan: `make archive RUN=<scratch run_dir>`.
3. Afterwards run `make check-run RUN=<scratch run_dir>` and report both sides.

Never delete scratch data as part of archiving; that is a separate decision for the
user (see "Freeing scratch"). Facts for finding runs and judging completeness are in
the check-runs skill.

## What the tools do

`slurm/tools/archive_sync.py` (behind both targets) compares one scratch run with
`/global/cfs/cdirs/amsc011/shared/wa-hls4ml-catapult/<tech>/<run name>/`. The tech
folder is where the run is already archived, else the catalog tech of the group in
a `catapult_<group>_rf<N>` folder name (`slurm/site.json` maps `gf22` to
`gf22fdx`). When neither says, it stops and asks for `TECH=`; nothing is guessed
from the path.

- **new:** report or tarball missing from the archive is copied.
- **replace:** archive report is not good (no positive QoR, the check-runs rule) and
  the scratch one is good. The old archive report and tarball are copied to
  `reports_stale_<YYYYMMDD>/` and `tarballs_stale_<YYYYMMDD>/` first.
- **kept:** archive report is good. It is never overwritten, even if the scratch
  tarball differs in size; such stems are listed for a person to look at.
- `source_dir.txt` is written only if absent. Every applied action is appended to
  `archive_sync.log` in the archive run folder.

Run it when no SLURM job is still writing to the run (`make check-jobs`): a tarball
being written could be copied half-done and would then show up as "kept, differs".

## Proving and freeing

- `make archive-verify RUN=<scratch run_dir> [ALL=1]`: every scratch report is in the
  archive with identical bytes, every tarball with the same size, 20 random tarballs
  (ALL=1: all) with the same MD5, and no good design only on scratch. Last line
  `VERIFIED` or `NOT VERIFIED`. Also lists scratch-only `*_stale_*` backups.
  Read-only; ~1 min for 5k designs.
- `make scratch-clean RUN=<scratch run_dir> [APPLY=1]`: removes the whole scratch run
  folder, including `build/` with every Catapult attempt, which the archive does not
  keep. It runs archive-verify itself and refuses unless it passes; refuses paths
  that are not `$SCRATCH/catapult_*/run_*`, runs changed in the last hour, and runs
  with scratch-only `*_stale_*` backups unless `DROP_BACKUPS=1` (then, with APPLY=1,
  those backups are deleted too; ask first). Without APPLY=1 it only reports size. Measuring takes ~10 min for a run with 2M files in
  `build/` (2-layer sz128 RF=1: 3.3 TB on scratch vs 163 GB archived). Never run APPLY=1 without the user's explicit yes
  for that run, and say what build/ data will be lost.
- `make archive-index [APPLY=1]`: archive runs whose ID the archive `README.md` does
  not mention, with measured design and good counts, as a markdown table. APPLY=1
  copies the README to `README.md.bak_<YYYYMMDD_HHMM>` and appends the table. It
  does not fix stale numbers in rows that exist; those need a hand edit, with the
  user's OK, after copying the README to `README.md.bak_<YYYYMMDD_HHMM>`. Update the
  subtotals and the disk table with the row, and check them against
  `make dataset-summary`.

## How sweeps archive

At the end of every sweep `slurm/sweeplib/orchestrate.sh` runs
`archive_sync.py --apply` with the tech folder from the catalog, so a sweep copies
its results itself and leaves the scratch run in place. Removing scratch is a manual
step for the user, after `make check-run` shows the run fully archived.
