#!/usr/bin/env python3
"""Read-only completeness report for one Catapult sweep run, on scratch and in the archive.

A design is "good" when its report JSON parses and QOFRSummary has positive
total_area, latency_cycles and thruput_cycles. This mirrors check_json() in the
archive's scripts/check_dataset.py, so both tools agree on what counts. A report
without those values is a failed synthesis; a tarball alone proves nothing.

The argument is either a scratch run directory or a bare run name
(run_YYYYMMDD_HHMMSS_<uuid8>). The scratch side reads data/reports/raw/ and
tarballs/; the archive side looks for the same run name under
ARCHIVE/{nangate45,gf22fdx}/. Nothing is written anywhere.

Usage:
    run_status.py $SCRATCH/catapult_<group>_rf<N>/run_<...>
    run_status.py run_20260511_183550_fb022142          # archive only
    run_status.py <run> --list-failed                   # failed stems, one per line
    run_status.py <run> --expected 6561                 # when there is no joblist.txt
"""

import argparse
import glob
import json
import os
import sys

ARCHIVE = "/global/cfs/cdirs/amsc011/shared/wa-hls4ml-catapult"
TECH_DIRS = ("nangate45", "gf22fdx")
REQUIRED_METRICS = ("total_area", "latency_cycles", "thruput_cycles")


def is_good(path):
    """Same rule as check_dataset.check_json(): parseable, positive QoR metrics."""
    try:
        with open(path) as f:
            q = json.load(f).get("QOFRSummary")
    except Exception:
        return False
    if not isinstance(q, dict):
        return False
    for key in REQUIRED_METRICS:
        val = q.get(key)
        if isinstance(val, bool) or not isinstance(val, (int, float)) or val <= 0:
            return False
    return True


def stems(directory, suffix):
    if not os.path.isdir(directory):
        return None
    return {n[:-len(suffix)] for n in os.listdir(directory) if n.endswith(suffix)}


def scan(report_dir, tarball_dir):
    """Return dict with report/tarball stems and the good subset, or None if absent."""
    reports = stems(report_dir, ".json")
    if reports is None:
        return None
    good = {s for s in reports if is_good(os.path.join(report_dir, s + ".json"))}
    return {"reports": reports, "good": good,
            "tarballs": stems(tarball_dir, ".tar.gz") or set()}


def find_archive_run(name):
    for tech in TECH_DIRS:
        path = os.path.join(ARCHIVE, tech, name)
        if os.path.isdir(path):
            return path
    return None


def joblist_tags(path):
    """Design tags in a joblist: the basename of each line's first field (the build dir)."""
    with open(path) as f:
        return {os.path.basename(l.split("\t", 1)[0].rstrip("/")) for l in f if l.strip()}


def joblists(run_dir):
    """{file name: set of tags} for every joblist*.txt in the run directory."""
    if not run_dir:
        return {}
    return {os.path.basename(p): joblist_tags(p)
            for p in sorted(glob.glob(os.path.join(run_dir, "joblist*.txt")))}


def line(label, value, expected=None):
    if value is None:
        print("  %-26s -" % label)
    elif expected:
        print("  %-26s %7d  (%5.1f%%)" % (label, value, 100.0 * value / expected))
    else:
        print("  %-26s %7d" % (label, value))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", help="scratch run directory, a folder of run_* directories, or a run name")
    ap.add_argument("--expected", type=int, default=None,
                    help="expected design count (default: lines in joblist.txt)")
    ap.add_argument("--list-failed", action="store_true",
                    help="print stems with a report but no valid QoR, one per line")
    args = ap.parse_args()

    if args.expected is not None and args.expected <= 0:
        ap.error("--expected must be a positive number")

    path = os.path.abspath(args.run.rstrip("/"))
    inner = []
    if os.path.isdir(path) and not os.path.basename(path).startswith("run_"):
        inner = sorted(glob.glob(os.path.join(path, "run_*")))
        if not inner:
            sys.exit("run_status: %s is neither a run_* directory nor a folder of them" % path)
    status = 0
    for i, run in enumerate(inner or [args.run]):
        if i:
            print()
        status = max(status, report(args, run))
    return status


def report(args, run_arg):
    path = os.path.abspath(run_arg.rstrip("/"))
    if os.path.isdir(path) and not path.startswith(ARCHIVE + "/"):
        run_dir, name = path, os.path.basename(path)
    else:
        # A bare run name, or an archive path: look it up in the archive only.
        run_dir, name = None, os.path.basename(path)

    scratch = None
    if run_dir:
        scratch = scan(os.path.join(run_dir, "data", "reports", "raw"),
                       os.path.join(run_dir, "tarballs"))
    archive_dir = find_archive_run(name)
    archive = scan(os.path.join(archive_dir, "reports"),
                   os.path.join(archive_dir, "tarballs")) if archive_dir else None

    if scratch is None and archive is None:
        print("run_status: no reports found for %s on scratch or in the archive" % run_arg,
              file=sys.stderr)
        return 1

    if args.list_failed:
        side = scratch if scratch is not None else archive
        for s in sorted(side["reports"] - side["good"]):
            print(s)
        return 0

    lists = joblists(run_dir)
    # A rerun folder keeps the full joblist.txt but only retries joblist_rerun*.txt.
    rerun = set().union(*[t for n, t in lists.items() if n.startswith("joblist_rerun")]) \
        if any(n.startswith("joblist_rerun") for n in lists) else None
    target = rerun if rerun is not None else lists.get("joblist.txt")
    expected = args.expected or (len(target) if target else None)
    print("Run      %s" % name)
    if args.expected:
        print("Expected %d (given)" % expected)
    elif rerun is not None:
        print("Expected %d (rerun folder: joblist_rerun*.txt; joblist.txt lists %d)"
              % (expected, len(lists.get("joblist.txt", ()))))
    elif expected:
        print("Expected %d (joblist.txt)" % expected)
    else:
        print("Expected unknown (no joblist.txt; pass --expected)")
    if len(lists) > 1:
        shown = ["%s %d" % (n, len(t)) for n, t in lists.items()]
        more = " ... (%d files)" % len(shown) if len(shown) > 4 else ""
        print("Joblists %s%s" % (", ".join(shown[:4]), more))

    print("Scratch  %s" % (run_dir or "not given"))
    if scratch is not None:
        line("reports", len(scratch["reports"]), expected)
        line("good (valid QoR)", len(scratch["good"]), expected)
        line("failed (no valid QoR)", len(scratch["reports"] - scratch["good"]), expected)
        if target and not args.expected:
            line("missing report", len(target - scratch["reports"]), expected)
        elif expected:
            line("missing report", max(expected - len(scratch["reports"]), 0), expected)
        line("tarballs", len(scratch["tarballs"]), expected)
    elif run_dir:
        print("  (no data/reports/raw/)")

    print("Archive  %s" % (archive_dir or "not found under %s/{%s}" % (ARCHIVE, ",".join(TECH_DIRS))))
    if archive is not None:
        line("reports", len(archive["reports"]), expected)
        line("good (valid QoR)", len(archive["good"]), expected)
        line("tarballs", len(archive["tarballs"]), expected)
    if scratch is not None and archive is not None:
        line("good on scratch, not archived", len(scratch["good"] - archive["good"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
