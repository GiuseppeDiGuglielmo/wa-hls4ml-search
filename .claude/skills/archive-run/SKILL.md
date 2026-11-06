---
name: archive-run
description: >-
  Facts and gates for copying a wa-hls4ml Catapult scratch run into the shared CFS
  archive with make archive-dry / make archive (copy only, backs up stale archive
  reports, never deletes). Use when asked to archive a run, sync scratch results to
  the archive, replace stale or failed archive reports, or when check-run shows good
  designs on scratch that are not archived.
---

# Archiving a sweep run

The archive is shared with other users and is the dataset of record. Writing to it
is an action, so it has gates:

1. Run `make archive-dry RUN=<scratch run_dir>` and show the user its output.
2. Copy only after the user says yes to that plan: `make archive RUN=<scratch run_dir>`.
3. Afterwards run `make check-run RUN=<scratch run_dir>` and report both sides.

Never delete scratch data as part of archiving; that is a separate decision for the
user. Facts for finding runs and judging completeness are in the check-runs skill.

## What the tools do

`slurm/examples/archive_sync.py` (behind both targets) compares one scratch run with
`/global/cfs/cdirs/amsc011/shared/wa-hls4ml-catapult/<tech>/<run name>/`. The tech
folder is `gf22fdx` when the scratch path has `catapult_gf22`, else `nangate45`;
pass `TECH=` to override.

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

## How sweeps archive

At the end of every sweep `slurm/sweeplib/orchestrate.sh` runs
`archive_sync.py --apply` with the tech folder from the catalog, so a sweep copies
its results itself and leaves the scratch run in place. Removing scratch is a manual
step for the user, after `make check-run` shows the run fully archived.

`slurm/examples/archive_run.sh` is the older archiver. It copies only reports not
already in the archive (stale ones stay stale), overwrites tarballs whose size
differs, and with `--yes` **deletes the scratch run** once archive counts match
`joblist.txt`. Do not run it; use the targets above.
