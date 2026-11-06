#!/usr/bin/env python3
"""Copy one scratch run's reports and tarballs into the shared archive. Never deletes.

Without --apply it only prints the plan. With --apply it copies:

  new        report/tarball not in the archive yet: copied.
  replace    archive report is not good (see run_status.is_good) but the scratch
             one is: the archive report and tarball are first copied to
             reports_stale_<tag>/ and tarballs_stale_<tag>/, then overwritten.
  kept       both sides exist and the archive report is good: left alone, even if
             the scratch copy differs (reported, so you can look).

Unlike archive_run.sh it replaces stale archive reports, and it has no code that
removes scratch data. Every copy goes to a temporary name first and is renamed
into place, and each applied action is appended to <archive run>/archive_sync.log.

Usage:
    archive_sync.py <scratch run_dir> [--tech nangate45|gf22fdx] [--apply] [--tag TAG]
"""

import argparse
import datetime
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_status import ARCHIVE, TECH_DIRS, is_good  # noqa: E402


def listing(directory, suffix):
    if not os.path.isdir(directory):
        return set()
    return {n[:-len(suffix)] for n in os.listdir(directory) if n.endswith(suffix)}


def plan(run_dir, dest):
    """Return {stem: action} for reports and tarballs, and the 'kept but differs' stems."""
    s_rep, d_rep = os.path.join(run_dir, "data", "reports", "raw"), os.path.join(dest, "reports")
    s_tar, d_tar = os.path.join(run_dir, "tarballs"), os.path.join(dest, "tarballs")
    src_r, dst_r = listing(s_rep, ".json"), listing(d_rep, ".json")
    src_t, dst_t = listing(s_tar, ".tar.gz"), listing(d_tar, ".tar.gz")

    actions, differs = {}, []
    for stem in sorted(src_r | src_t):
        sj, dj = os.path.join(s_rep, stem + ".json"), os.path.join(d_rep, stem + ".json")
        st, dt = os.path.join(s_tar, stem + ".tar.gz"), os.path.join(d_tar, stem + ".tar.gz")
        rep = tar = None
        if stem in src_r:
            if stem not in dst_r:
                rep = "new"
            elif not is_good(dj) and is_good(sj):
                rep = "replace"
        if stem in src_t:
            if stem not in dst_t:
                tar = "new"
            elif rep == "replace" or (stem not in dst_r and rep == "new"):
                # The report is being (re)written: bring its tarball along.
                if os.path.getsize(st) != os.path.getsize(dt):
                    tar = "replace"
            elif os.path.getsize(st) != os.path.getsize(dt):
                differs.append(stem)
        if rep or tar:
            actions[stem] = (rep, tar)
    return actions, differs


def copy_into(src, dst):
    tmp = dst + ".archive_sync.tmp"
    shutil.copy2(src, tmp)
    os.rename(tmp, dst)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", help="scratch run directory (run_YYYYMMDD_HHMMSS_<uuid8>)")
    ap.add_argument("--tech", choices=TECH_DIRS,
                    help="archive tech folder (default: gf22fdx if the path has catapult_gf22, else nangate45)")
    ap.add_argument("--apply", action="store_true", help="copy; without it only the plan is printed")
    ap.add_argument("--tag", default=datetime.date.today().strftime("%Y%m%d"),
                    help="suffix of the stale backup folders (default: today, YYYYMMDD)")
    args = ap.parse_args()

    run_dir = os.path.abspath(args.run_dir.rstrip("/"))
    name = os.path.basename(run_dir)
    if not name.startswith("run_") or not os.path.isdir(os.path.join(run_dir, "data", "reports", "raw")):
        sys.exit("archive_sync: %s is not a scratch run directory (needs data/reports/raw/)" % run_dir)
    if run_dir.startswith(ARCHIVE + "/"):
        sys.exit("archive_sync: %s is already in the archive" % run_dir)
    tech = args.tech or ("gf22fdx" if "/catapult_gf22" in run_dir else "nangate45")
    dest = os.path.join(ARCHIVE, tech, name)

    actions, differs = plan(run_dir, dest)
    count = lambda kind, what: sum(1 for a in actions.values() if a[kind] == what)
    print("Run      %s" % name)
    print("Scratch  %s" % run_dir)
    print("Archive  %s%s" % (dest, "" if os.path.isdir(dest) else "  (new)"))
    print("  reports   new %5d   replace (archive not good, scratch good) %5d"
          % (count(0, "new"), count(0, "replace")))
    print("  tarballs  new %5d   replace (with its report)                %5d"
          % (count(1, "new"), count(1, "replace")))
    print("  kept: archive good, scratch tarball size differs              %5d" % len(differs))
    for stem in differs[:5]:
        print("    %s" % stem)
    if len(differs) > 5:
        print("    ... (%d more)" % (len(differs) - 5))
    src_txt = os.path.join(dest, "source_dir.txt")
    if os.path.isfile(src_txt):
        recorded = open(src_txt).read().strip()
        if recorded != run_dir:
            print("  note: source_dir.txt records %s; left unchanged" % recorded)

    if not actions:
        print("Nothing to copy.")
        return 0
    if not args.apply:
        print("Dry run: nothing written. Add --apply to copy (stale backups tag: %s)." % args.tag)
        return 0

    s_rep, d_rep = os.path.join(run_dir, "data", "reports", "raw"), os.path.join(dest, "reports")
    s_tar, d_tar = os.path.join(run_dir, "tarballs"), os.path.join(dest, "tarballs")
    b_rep = os.path.join(dest, "reports_stale_" + args.tag)
    b_tar = os.path.join(dest, "tarballs_stale_" + args.tag)
    for d in (d_rep, d_tar):
        os.makedirs(d, exist_ok=True)
    if not os.path.isfile(src_txt):
        with open(src_txt, "w") as f:
            f.write(run_dir + "\n")

    with open(os.path.join(dest, "archive_sync.log"), "a") as log:
        for stem, (rep, tar) in sorted(actions.items()):
            for kind, src_dir, dst_dir, bak_dir, ext in (
                    (rep, s_rep, d_rep, b_rep, ".json"), (tar, s_tar, d_tar, b_tar, ".tar.gz")):
                if not kind:
                    continue
                src, dst = os.path.join(src_dir, stem + ext), os.path.join(dst_dir, stem + ext)
                if kind == "replace":
                    os.makedirs(bak_dir, exist_ok=True)
                    bak = os.path.join(bak_dir, stem + ext)
                    if os.path.exists(bak):
                        sys.exit("archive_sync: backup %s already exists; use another --tag" % bak)
                    shutil.copy2(dst, bak)
                copy_into(src, dst)
                log.write("%s\t%s\t%s%s\t%s\n" % (datetime.datetime.now().isoformat(timespec="seconds"),
                                                  kind, stem, ext, run_dir))
    print("Copied. Check with: make check-run RUN=%s" % run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
