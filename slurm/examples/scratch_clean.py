#!/usr/bin/env python3
"""Remove a scratch sweep run, only after the archive is verified to hold it.

    scratch_clean.py <scratch run_dir> [--apply] [--tech T] [--sample N]

Runs archive_verify first and stops unless it passes. Refuses runs that are
not run_* folders under $SCRATCH/catapult_*/, runs with files changed in the
last hour (a job may still be writing), and runs that have a scratch-only
*_stale_* backup unless --drop-backups is given. Without --apply it only
prints what would be removed and how big it is.

This is the only tool here that deletes data. Removing the run also removes
build/ (all Catapult attempt folders), which the archive does not keep.
"""

import argparse
import glob
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from archive_verify import verify  # noqa: E402

import re  # noqa: E402

RUN_RE = re.compile(r"run_\d{8}_\d{6}_[0-9a-f]{8}$")


def size_and_newest(root):
    total, newest, files = 0, 0.0, 0
    for d, _, names in os.walk(root):
        for n in names:
            try:
                st = os.lstat(os.path.join(d, n))
            except OSError:
                continue
            total += st.st_size
            newest = max(newest, st.st_mtime)
            files += 1
    return total, newest, files


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--apply", action="store_true", help="delete; without it only report")
    ap.add_argument("--tech")
    ap.add_argument("--sample", type=int, default=20)
    ap.add_argument("--drop-backups", action="store_true",
                    help="also allow removing scratch-only *_stale_* backups")
    args = ap.parse_args()

    run_dir = os.path.realpath(args.run_dir.rstrip("/"))
    scratch = os.path.realpath(os.environ.get("SCRATCH", "/nonexistent"))
    parent = os.path.dirname(run_dir)
    if not (RUN_RE.search(run_dir) and os.path.dirname(parent) == scratch
            and os.path.basename(parent).startswith("catapult_")):
        sys.exit("scratch_clean: refusing %s: not $SCRATCH/catapult_*/run_*" % run_dir)
    if not os.path.isdir(run_dir):
        sys.exit("scratch_clean: %s does not exist" % run_dir)

    print("Run      %s" % run_dir)
    ok, dest, problems = verify(run_dir, args.tech, args.sample, False, out=lambda s: print("  " + s))
    if not ok:
        print("Not removing: archive not verified (%s)." % ", ".join(problems))
        return 1
    stale = glob.glob(os.path.join(run_dir, "*_stale_*")) + glob.glob(os.path.join(run_dir, "data", "reports", "*_stale_*"))
    if stale and not args.drop_backups:
        print("Not removing: scratch-only backups exist (%s); copy them somewhere or pass --drop-backups."
              % ", ".join(os.path.relpath(p, run_dir) for p in stale))
        return 1
    total, newest, files = size_and_newest(run_dir)
    age_min = (time.time() - newest) / 60.0
    print("Size     %.1f GB in %d files; newest change %.0f min ago" % (total / 1e9, files, age_min))
    if age_min < 60:
        print("Not removing: files changed in the last hour; a job may still be writing.")
        return 1
    if not args.apply:
        print("Dry run: nothing removed. APPLY=1 removes %s (archive: %s)." % (run_dir, dest))
        return 0
    shutil.rmtree(run_dir)
    print("Removed %s. The archive copy is %s." % (run_dir, dest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
