#!/usr/bin/env python3
"""List Catapult sweep runs on scratch and in the shared archive (read-only).

One line per run ID:

    RUN  TECH  WHERE  GROUP  SOURCE

  WHERE   scratch, archive, or both
  GROUP   catalog group and RF from slurm/examples/PROVENANCE.md, if listed there
          ("see PROVENANCE note" for ghost, legacy and partial runs)
  SOURCE  scratch folder the run lives in, or came from (archive source_dir.txt)

Usage:
    list_runs.py [--tech nangate45|gf22fdx] [--where scratch|archive|both] [--grep TEXT]
"""

import argparse
import glob
import os
import re
import sys

ARCHIVE = "/global/cfs/cdirs/amsc011/shared/wa-hls4ml-catapult"
TECH_DIRS = ("nangate45", "gf22fdx")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROVENANCE = os.path.join(REPO, "slurm", "examples", "PROVENANCE.md")
RUN_RE = re.compile(r"run_\d{8}_\d{6}_[0-9a-f]{8}")


def provenance_groups(path):
    """Map run ID -> 'group rfN' from the markdown tables in PROVENANCE.md.

    Runs mentioned only in the prose notes (ghost, legacy, partial runs) map to
    'see PROVENANCE note'.
    """
    groups, noted = {}, set()
    if not os.path.isfile(path):
        return groups
    with open(path) as f:
        for row in f:
            if not row.startswith("|"):
                noted.update(RUN_RE.findall(row))
                continue
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            if len(cells) < 3:
                continue
            runs = RUN_RE.findall(cells[2])
            if not runs:
                continue
            group = cells[0].replace("`", "").replace("*", "").strip()
            rfs = [r for r in re.findall(r"\d+", cells[1])]
            if len(rfs) == len(runs):
                pairs = zip(runs, rfs)
            else:
                pairs = ((r, rfs[0] if len(rfs) == 1 else "?") for r in runs)
            for run, rf in pairs:
                groups[run] = "%s rf%s" % (group, rf)
    for run in noted - set(groups):
        groups[run] = "see PROVENANCE note"
    return groups


def read_source(run_dir):
    try:
        with open(os.path.join(run_dir, "source_dir.txt")) as f:
            path = f.read().strip().rstrip("/")
    except (IOError, OSError):
        return None
    return os.path.basename(os.path.dirname(path)) or None


def tech_of_folder(folder):
    return "gf22fdx" if "gf22" in folder else "nangate45"


def collect():
    runs = {}
    scratch = os.environ.get("SCRATCH")
    if scratch:
        for d in glob.glob(os.path.join(scratch, "catapult_*", "run_*")):
            name = os.path.basename(d)
            if RUN_RE.fullmatch(name):
                folder = os.path.basename(os.path.dirname(d))
                runs[name] = {"tech": tech_of_folder(folder), "scratch": True,
                              "archive": False, "source": folder}
    for tech in TECH_DIRS:
        for d in glob.glob(os.path.join(ARCHIVE, tech, "run_*")):
            name = os.path.basename(d)
            if not RUN_RE.fullmatch(name):
                continue
            entry = runs.setdefault(name, {"tech": tech, "scratch": False, "source": None})
            entry["archive"] = True
            entry["tech"] = tech
            entry["source"] = entry["source"] or read_source(d)
    return runs


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tech", choices=TECH_DIRS)
    ap.add_argument("--where", choices=("scratch", "archive", "both"))
    ap.add_argument("--grep", help="keep lines containing this text (case-insensitive)")
    args = ap.parse_args()

    groups = provenance_groups(PROVENANCE)
    rows = []
    for name, e in sorted(collect().items()):
        where = "both" if e["scratch"] and e["archive"] else ("scratch" if e["scratch"] else "archive")
        if args.tech and e["tech"] != args.tech:
            continue
        if args.where and where != args.where:
            continue
        row = (name, e["tech"], where, groups.get(name, "-"), e["source"] or "-")
        if args.grep and args.grep.lower() not in " ".join(row).lower():
            continue
        rows.append(row)

    if not os.environ.get("SCRATCH"):
        print("note: $SCRATCH is not set; scratch runs are not listed", file=sys.stderr)
    fmt = "%-30s %-10s %-8s %-22s %s"
    print(fmt % ("RUN", "TECH", "WHERE", "GROUP (PROVENANCE)", "SOURCE"))
    for row in rows:
        print(fmt % row)
    print("\n%d run(s). Details: make check-run RUN=<run name, or scratch dir for scratch counts>"
          % len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
