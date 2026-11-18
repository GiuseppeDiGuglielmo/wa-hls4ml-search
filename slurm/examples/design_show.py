#!/usr/bin/env python3
"""Everything known about one design of a sweep run, read-only.

    design_show.py <scratch run_dir | run name> <stem>

Shows the report (scratch and archive) with its QoR, every Catapult attempt in
build/<stem>/catapult_native/ (the last flow step it completed, peak memory,
whether it produced QoR), and the GNU parallel joblog entries for the design.
With only a run name, the archive side is shown.
"""

import argparse
import glob
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_status import ARCHIVE, find_archive_run, is_good  # noqa: E402

STEP_RE = re.compile(rb"Completed transformation '([^']+)'")
PEAK_RE = re.compile(rb"peak memory usage (\d+)kB")
ATTEMPT_RE = re.compile(r"^Catapult(?:_(\d+))?$")


def attempts(catapult_native):
    """[(folder name, path)] of Catapult project folders, oldest first."""
    found = []
    if os.path.isdir(catapult_native):
        for n in os.listdir(catapult_native):
            m = ATTEMPT_RE.match(n)
            p = os.path.join(catapult_native, n)
            if m and os.path.isdir(p):
                found.append((int(m.group(1) or 0), n, p))
    return [(n, p) for _, n, p in sorted(found)]


def last_log_time(path):
    """When the newest solution's messages.txt was last written, or "-".

    Not the attempt folder's own mtime: deleting files inside it (the scratch
    purge) moves that to the purge date.
    """
    logs = glob.glob(os.path.join(path, "*.v*", "messages.txt"))
    if not logs:
        return "-"
    newest = max(os.stat(f).st_mtime for f in logs)
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(newest))


def attempt_facts(path):
    """Last completed step, peak memory (GB), QoR present, for the newest solution."""
    sols = sorted(glob.glob(os.path.join(path, "*.v*")),
                  key=lambda s: int(re.sub(r".*\.v", "", s)) if re.search(r"\.v\d+$", s) else -1)
    if not sols:
        return "-", None, False
    sol = sols[-1]
    try:
        text = open(os.path.join(sol, "messages.txt"), "rb").read()
    except (IOError, OSError):
        text = b""
    steps = STEP_RE.findall(text)
    peaks = [int(x) for x in PEAK_RE.findall(text)]
    return ((steps[-1].decode() if steps else "-"),
            (max(peaks) / 1e6 if peaks else None),
            os.path.isfile(os.path.join(sol, "nnet_qofr.csv")))


def show_report(label, path):
    if not os.path.isfile(path):
        print("%-8s no report (%s)" % (label, path))
        return
    try:
        rep = json.load(open(path))
    except ValueError:
        print("%-8s report does not parse: %s" % (label, path))
        return
    q = rep.get("QOFRSummary") or {}
    state = "good" if is_good(path) else "FAILED (no valid QoR)"
    print("%-8s %s  %s" % (label, state, path))
    if q:
        print("         area %s  latency %s  thruput %s" % (q.get("total_area"), q.get("latency_cycles"),
                                                           q.get("thruput_cycles")))
    pa = rep.get("ProjectAttempts")
    if pa:
        print("         parsed from %s (of %d attempt folders)" % (pa.get("used"), len(pa.get("found", []))))


def joblog_entries(run_dir, stem):
    rows = []
    needle = "/build/%s\t" % stem
    for log in sorted(glob.glob(os.path.join(run_dir, "parallel_*.log"))):
        with open(log, errors="replace") as f:
            for line in f:
                if needle in line:
                    c = line.split("\t")
                    try:
                        rows.append((float(c[2]), float(c[3]), c[6], c[7], os.path.basename(log)))
                    except (IndexError, ValueError):
                        pass
    return sorted(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", help="scratch run directory, or a run name for the archive only")
    ap.add_argument("stem", help="design stem, e.g. dense_2l_sz128_1734")
    args = ap.parse_args()

    path = os.path.abspath(args.run.rstrip("/"))
    run_dir = path if os.path.isdir(path) and not path.startswith(ARCHIVE + "/") else None
    name = os.path.basename(path)
    stem = args.stem[:-5] if args.stem.endswith(".json") else args.stem
    archive_dir = find_archive_run(name)

    known = (run_dir and (os.path.isdir(os.path.join(run_dir, "build", stem)) or
                          os.path.isfile(os.path.join(run_dir, "data", "reports", "raw", stem + ".json")))) or \
        (archive_dir and os.path.isfile(os.path.join(archive_dir, "reports", stem + ".json")))
    if not known:
        print("design_show: no design %s in %s (no build folder or report on scratch or in the archive)"
              % (stem, name), file=sys.stderr)
        return 1
    print("Design   %s  in %s" % (stem, name))
    if run_dir:
        show_report("Scratch", os.path.join(run_dir, "data", "reports", "raw", stem + ".json"))
    if archive_dir:
        show_report("Archive", os.path.join(archive_dir, "reports", stem + ".json"))
        tb = os.path.join(archive_dir, "tarballs", stem + ".tar.gz")
        print("         tarball %s" % ("%.1f MB" % (os.path.getsize(tb) / 1e6) if os.path.isfile(tb) else "missing"))
    else:
        print("Archive  run not found under %s" % ARCHIVE)

    if not run_dir:
        print("Attempts build folder not on scratch; the archive tarball holds the used project")
        return 0
    native = os.path.join(run_dir, "build", stem, "catapult_native")
    tries = attempts(native)
    if not tries:
        print("Attempts none (%s)" % ("no %s" % native if not os.path.isdir(native) else "no Catapult* folders"))
    else:
        print("Attempts %d in %s" % (len(tries), native))
        print("         %-12s %-17s %-12s %-9s %s" % ("folder", "last log", "last step", "peak mem", "QoR"))
        shown = tries if len(tries) <= 12 else tries[:5] + [None] + tries[-6:]
        for t in shown:
            if t is None:
                print("         ... (%d more)" % (len(tries) - 11))
                continue
            n, p = t
            step, peak, qor = attempt_facts(p)
            started = last_log_time(p)
            print("         %-12s %-17s %-12s %-9s %s" % (n, started, step,
                                                       "%.1f GB" % peak if peak else "-", "yes" if qor else "no"))

    rows = joblog_entries(run_dir, stem)
    if rows:
        print("Joblog   %d GNU parallel entries (Exitval 0 = the wrapper succeeded)" % len(rows))
        for start, rt, ev, sig, log in rows[-8:]:
            print("         %s  %6.0f min  exit %-3s signal %-2s %s" % (
                time.strftime("%Y-%m-%d %H:%M", time.localtime(start)), rt / 60, ev, sig, log))
    return 0


if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped to head
    sys.exit(main())
