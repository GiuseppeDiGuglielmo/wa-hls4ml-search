#!/usr/bin/env python3
"""Per-design Catapult time and peak memory, read from archived tarballs. Read-only.

Reports have no time field. Each tarball's
catapult_native/Catapult*/myproject.v1/messages.txt has one line per step:

    Completed transformation '<step>' ... elapsed time <s> seconds, ...
    peak memory usage <kB>kB

catapult_s is the sum of those elapsed times and peak_kb their maximum. This is
Catapult's own synthesis time: it leaves out container start, license wait and
the hls4ml conversion before Catapult, so it is a lower bound on wall time.
When a tarball holds more than one Catapult project folder (a retry), the last
one in sorted order is used and the folder name is printed in `project`.
--first-only stops at the first messages.txt instead: much faster on large
tarballs (the multi-GB schematic comes after it), but it misses a later retry
folder. Compare it with the default on a sample before relying on it.

Usage:
    design_cost.py <run name | run dir | mlp-<N>layer dir> ... [--tech T]
                   [--workers N] [--out FILE] [--stems FILE] [--first-only]

A run name is looked up in the archive. An mlp-<N>layer folder expands to the
runs it links. --stems FILE (TSV with run and stem columns) limits the designs. Output is a TSV (stdout or --out; --out goes to a temporary name
first) with columns:
    run  stem  catapult_s  peak_kb  n_steps  project  status  all_s  n_projects
catapult_s, peak_kb and n_steps describe the project used; all_s sums the
elapsed time of every project folder (a retried design paid for each attempt).
status is ok, no_tarball, no_messages, no_steps or error:<reason>.
"""

import argparse
import glob
import os
import re
import sys
import tarfile
from multiprocessing import Pool

from slurm.tools.run_status import ARCHIVE, TECH_DIRS

STEP_RE = re.compile(rb"Completed transformation .*?elapsed time ([0-9.]+) seconds"
                     rb".*?peak memory usage (\d+)kB")
MSG_RE = re.compile(r"catapult_native/(Catapult[^/]*)/myproject\.v1/messages\.txt$")
COLUMNS = ("run", "stem", "catapult_s", "peak_kb", "n_steps", "project", "status", "all_s", "n_projects")


def resolve_runs(args_runs, tech):
    """Turn names, run dirs and mlp-<N>layer dirs into archive run dirs."""
    techs = [tech] if tech else list(TECH_DIRS)
    runs = []
    for item in args_runs:
        item = item.rstrip("/")
        if os.path.isdir(os.path.join(item, "tarballs")):
            runs.append(os.path.realpath(item))
            continue
        if os.path.isdir(item) and glob.glob(os.path.join(item, "run_*")):
            runs.extend(os.path.realpath(p) for p in sorted(glob.glob(os.path.join(item, "run_*"))))
            continue
        found = [os.path.join(ARCHIVE, t, item) for t in techs
                 if os.path.isdir(os.path.join(ARCHIVE, t, item, "tarballs"))]
        if not found:
            sys.exit("design_cost: no archive run or folder named %r" % item)
        runs.append(found[0])
    seen, out = set(), []
    for r in runs:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def parse_messages(data):
    total, peak, n = 0.0, 0, 0
    for m in STEP_RE.finditer(data):
        total += float(m.group(1))
        peak = max(peak, int(m.group(2)))
        n += 1
    return total, peak, n


FIRST_ONLY = False


def _init(first_only):
    global FIRST_ONLY
    FIRST_ONLY = first_only


def cost_one(job):
    run_dir, stem = job
    run = os.path.basename(run_dir)
    path = os.path.join(run_dir, "tarballs", stem + ".tar.gz")
    row = [run, stem, "", "", "0", "", "", "", "0"]
    if not os.path.isfile(path):
        row[6] = "no_tarball"
        return row
    try:
        with tarfile.open(path, "r:gz") as tf:
            hits = []
            for member in tf:
                m = MSG_RE.search(member.name)
                if m and member.isfile():
                    hits.append((m.group(1), tf.extractfile(member).read()))
                    if FIRST_ONLY:
                        break
    except Exception as exc:  # corrupt or truncated archive
        row[6] = "error:%s" % type(exc).__name__
        return row
    if not hits:
        row[6] = "no_messages"
        return row
    project, data = sorted(hits)[-1]
    total, peak, n = parse_messages(data)
    row[5] = project
    row[7] = "%.2f" % sum(parse_messages(d)[0] for _, d in hits)
    row[8] = str(len(hits))
    if n == 0:
        row[6] = "no_steps"
        return row
    row[2:5] = ["%.2f" % total, str(peak), str(n)]
    row[6] = "ok"
    return row


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--tech", choices=list(TECH_DIRS))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out")
    ap.add_argument("--stems", help="TSV with run and stem columns: only these designs")
    ap.add_argument("--first-only", action="store_true", help="stop at the first messages.txt")
    a = ap.parse_args(argv)

    jobs = []
    for run_dir in resolve_runs(a.runs, a.tech):
        rep = os.path.join(run_dir, "reports")
        tar = os.path.join(run_dir, "tarballs")
        stems = set()
        for d, suf in ((rep, ".json"), (tar, ".tar.gz")):
            if os.path.isdir(d):
                stems.update(n[:-len(suf)] for n in os.listdir(d) if n.endswith(suf))
        jobs.extend((run_dir, s) for s in sorted(stems))
    if a.stems:
        with open(a.stems) as f:
            hdr = next(f).rstrip("\n").split("\t")
            ir, is_ = hdr.index("run"), hdr.index("stem")
            want = {(p[ir], p[is_]) for p in (line.rstrip("\n").split("\t") for line in f)}
        jobs = [j for j in jobs if (os.path.basename(j[0]), j[1]) in want]
    print("design_cost: %d designs in %d runs" % (len(jobs), len({j[0] for j in jobs})),
          file=sys.stderr)

    out = open(a.out + ".tmp", "w") if a.out else sys.stdout
    out.write("\t".join(COLUMNS) + "\n")
    counts = {}
    with Pool(a.workers, initializer=_init, initargs=(a.first_only,)) as pool:
        for i, row in enumerate(pool.imap(cost_one, jobs, chunksize=16), 1):
            out.write("\t".join(row) + "\n")
            key = row[6].split(":")[0]
            counts[key] = counts.get(key, 0) + 1
            if i % 2000 == 0:
                print("design_cost: %d/%d" % (i, len(jobs)), file=sys.stderr)
    if a.out:
        out.close()
        os.rename(a.out + ".tmp", a.out)
    print("design_cost: " + ", ".join("%s %d" % kv for kv in sorted(counts.items())),
          file=sys.stderr)


if __name__ == "__main__":
    main()
