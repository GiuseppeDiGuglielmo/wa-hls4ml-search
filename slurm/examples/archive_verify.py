#!/usr/bin/env python3
"""Is every result of a scratch run safely in the archive? Read-only.

    archive_verify.py <scratch run_dir> [--tech T] [--sample N | --all]

Passes (exit 0, last line VERIFIED) only if, for this run:
  - every scratch report is in the archive with identical content,
  - every scratch tarball is in the archive with the same size, and N randomly
    chosen ones (default 20; --all for every one) have the same MD5,
  - the archive has at least the good designs scratch has.
It also lists *_stale_* backup folders that exist only on scratch, which would
be lost if the scratch run were removed.
"""

import argparse
import glob
import hashlib
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run_status import ARCHIVE, TECH_DIRS, is_good  # noqa: E402


def md5(path, block=1 << 22):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(block), b""):
            h.update(chunk)
    return h.hexdigest()


def same_bytes(a, b):
    try:
        with open(a, "rb") as fa, open(b, "rb") as fb:
            return fa.read() == fb.read()
    except (IOError, OSError):
        return False


def listing(d, suffix):
    return {n[:-len(suffix)] for n in os.listdir(d) if n.endswith(suffix)} if os.path.isdir(d) else set()


def verify(run_dir, tech=None, sample=20, check_all=False, out=print):
    """Return (ok, archive_dir, problems)."""
    name = os.path.basename(run_dir)
    if tech:
        dest = os.path.join(ARCHIVE, tech, name)
    else:
        dest = next((os.path.join(ARCHIVE, t, name) for t in TECH_DIRS
                     if os.path.isdir(os.path.join(ARCHIVE, t, name))), None)
    if not dest or not os.path.isdir(dest):
        out("FAIL  run %s is not in the archive" % name)
        return False, dest, ["not archived"]
    problems = []
    s_rep, d_rep = os.path.join(run_dir, "data", "reports", "raw"), os.path.join(dest, "reports")
    s_tar, d_tar = os.path.join(run_dir, "tarballs"), os.path.join(dest, "tarballs")
    sr, dr = listing(s_rep, ".json"), listing(d_rep, ".json")
    st, dt = listing(s_tar, ".tar.gz"), listing(d_tar, ".tar.gz")

    missing = sr - dr
    differ = [s for s in sorted(sr & dr)
              if not same_bytes(os.path.join(s_rep, s + ".json"), os.path.join(d_rep, s + ".json"))]
    out("%-4s  reports   %d on scratch, %d missing in archive, %d with different content"
        % ("OK" if not (missing or differ) else "FAIL", len(sr), len(missing), len(differ)))
    if missing or differ:
        problems.append("reports")
        for s in (sorted(missing) + differ)[:5]:
            out("        %s" % s)

    tmissing = st - dt
    tsize = [s for s in sorted(st & dt)
             if os.path.getsize(os.path.join(s_tar, s + ".tar.gz")) != os.path.getsize(os.path.join(d_tar, s + ".tar.gz"))]
    out("%-4s  tarballs  %d on scratch, %d missing in archive, %d with different size"
        % ("OK" if not (tmissing or tsize) else "FAIL", len(st), len(tmissing), len(tsize)))
    if tmissing or tsize:
        problems.append("tarballs")
        for s in (sorted(tmissing) + tsize)[:5]:
            out("        %s" % s)

    pool = sorted((st & dt) - set(tsize))
    pick = pool if check_all else random.Random(name).sample(pool, min(sample, len(pool)))
    bad = [s for s in pick if md5(os.path.join(s_tar, s + ".tar.gz")) != md5(os.path.join(d_tar, s + ".tar.gz"))]
    out("%-4s  checksums %d tarball(s) compared by MD5%s, %d differ"
        % ("OK" if not bad else "FAIL", len(pick), " (all)" if check_all else " (sample)", len(bad)))
    if bad:
        problems.append("checksums")

    sg = {s for s in sr if is_good(os.path.join(s_rep, s + ".json"))}
    dg = {s for s in dr if is_good(os.path.join(d_rep, s + ".json"))}
    lost = sg - dg
    out("%-4s  good      %d on scratch, %d in archive, %d good only on scratch"
        % ("OK" if not lost else "FAIL", len(sg), len(dg), len(lost)))
    if lost:
        problems.append("good")

    stale = sorted(glob.glob(os.path.join(run_dir, "*_stale_*")) + glob.glob(os.path.join(run_dir, "data", "reports", "*_stale_*")))
    if stale:
        out("NOTE  scratch-only backups (lost if scratch is removed): %s"
            % ", ".join(os.path.relpath(p, run_dir) for p in stale))
    return not problems, dest, problems


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--tech", choices=TECH_DIRS)
    ap.add_argument("--sample", type=int, default=20)
    ap.add_argument("--all", action="store_true", help="MD5 every tarball (reads everything twice)")
    args = ap.parse_args()
    run_dir = os.path.abspath(args.run_dir.rstrip("/"))
    if not os.path.isdir(os.path.join(run_dir, "data", "reports", "raw")):
        sys.exit("archive_verify: %s is not a scratch run directory" % run_dir)
    print("Run      %s" % os.path.basename(run_dir))
    ok, dest, problems = verify(run_dir, args.tech, args.sample, args.all)
    print("Archive  %s" % dest)
    print("VERIFIED: the archive holds everything this scratch run has." if ok
          else "NOT VERIFIED: %s." % ", ".join(problems))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
