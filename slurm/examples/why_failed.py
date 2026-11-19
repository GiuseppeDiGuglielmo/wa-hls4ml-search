#!/usr/bin/env python3
"""Why Catapult attempts failed in one scratch sweep run, read-only.

    why_failed.py <scratch run_dir> [--no-memory]

Counts, from slurm_logs/ and sacct:
  - Catapult exit codes ("Catapult exited with code N"; 137 = SIGKILL),
  - SLURM out-of-memory kills ("oom_kill events") and time-limit cancels,
  - license errors (mgls_errno) and the final SLURM state of each job,
and, from build/<stem>/catapult_native/, how many attempts designs needed and
their peak Catapult memory (skip with --no-memory; it reads every messages.txt).
Ends with the designs that still have no valid QoR and where they stopped.
"""

import argparse
import collections
import glob
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_status import is_good  # noqa: E402
from design_show import attempts, attempt_facts  # noqa: E402

EXIT_RE = re.compile(r"Catapult exited with code (-?\d+)")
OOM_RE = re.compile(r"Detected (\d+) oom_kill events in StepId=(\d+)")
TIME_RE = re.compile(r"JOB (\d+) ON \S+ CANCELLED AT \S+ DUE TO TIME LIMIT")
JOB_RE = re.compile(r"(?:StepId=|JOB )(\d+)")
LIC_RE = re.compile(r"mgls_errno = (\d+)")
MEANING = {"137": "SIGKILL: OOM killer or job end", "139": "SIGSEGV", "133": "SIGTRAP",
           "255": "launcher/apptainer error", "1": "Catapult error", "2": "flow script error"}
BINS = ((0, 2), (2, 4), (4, 8), (8, 12), (12, 16), (16, 1e9))


def scan_logs(run_dir):
    exits, lic = collections.Counter(), collections.Counter()
    oom, timeouts, jobs = 0, set(), set()
    for path in sorted(glob.glob(os.path.join(run_dir, "slurm_logs", "*.err")) +
                       glob.glob(os.path.join(run_dir, "slurm_logs", "*.out"))):
        with open(path, errors="replace") as f:
            for line in f:
                m = EXIT_RE.search(line)
                if m:
                    exits[m.group(1)] += 1
                    continue
                m = OOM_RE.search(line)
                if m:
                    oom += int(m.group(1))
                m = TIME_RE.search(line)
                if m:
                    timeouts.add(m.group(1))
                m = LIC_RE.search(line)
                if m:
                    lic[m.group(1)] += 1
                jobs.update(JOB_RE.findall(line))
    return exits, oom, timeouts, lic, jobs


def sacct_states(jobs):
    if not jobs:
        return collections.Counter()
    try:
        out = subprocess.run(["sacct", "-n", "-P", "-j", ",".join(sorted(jobs)), "-o", "JobID,State"],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             universal_newlines=True, timeout=120).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    states = collections.Counter()
    for line in out.splitlines():
        jid, _, state = line.partition("|")
        if jid.endswith(".batch") or "." not in jid:
            states[("batch " if jid.endswith(".batch") else "job   ") + state.split()[0]] += 1
    return states


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--no-memory", action="store_true", help="skip the per-design attempts/peak memory scan")
    args = ap.parse_args()
    run_dir = os.path.abspath(args.run_dir.rstrip("/"))
    if not os.path.isdir(os.path.join(run_dir, "build")):
        inner = sorted(glob.glob(os.path.join(run_dir, "run_*", "build")))
        hint = ("; it holds: " + ", ".join(os.path.basename(os.path.dirname(p)) for p in inner)) if inner else ""
        sys.exit("why_failed: %s is not a scratch run directory (needs build/)%s" % (run_dir, hint))

    exits, oom, timeouts, lic, jobs = scan_logs(run_dir)
    print("Run      %s" % os.path.basename(run_dir))
    print("Scope    every job in slurm_logs/, earlier rounds included; No QoR (last line) is the state now")
    total = sum(exits.values())
    print("Catapult exits (non-zero, from slurm_logs): %d" % total)
    for code, n in exits.most_common():
        print("  code %-4s %7d  %s" % (code, n, MEANING.get(code, "")))
    print("SLURM    oom_kill events %d; jobs cancelled at time limit %d" % (oom, len(timeouts)))
    if lic:
        print("License  " + ", ".join("mgls_errno %s x%d" % kv for kv in lic.most_common()))
    states = sacct_states(jobs)
    if states is None:
        print("sacct    unavailable")
    elif states:
        print("sacct    " + ", ".join("%s %d" % kv for kv in sorted(states.items())))
    if exits.get("137"):
        if oom:
            print("Reading  137 with oom_kill events / OUT_OF_MEMORY: designs ran out of memory;"
                  " size slots by memory (sweep --memfree, --parallelism).")
        else:
            print("Reading  137 without oom_kill events: killed at job end or by the node's OOM killer;"
                  " check sacct MaxRSS against ReqMem.")

    report_dir = os.path.join(run_dir, "data", "reports", "raw")
    stems = sorted(os.listdir(os.path.join(run_dir, "build")))
    failed = []
    for s in stems:
        j = os.path.join(report_dir, s + ".json")
        if not is_good(j):
            failed.append((s, os.path.isfile(j)))

    if not args.no_memory:
        rows = []
        for s in stems:
            tries = attempts(os.path.join(run_dir, "build", s, "catapult_native"))
            if not tries:
                continue
            used = None
            try:
                used = (json.load(open(os.path.join(report_dir, s + ".json"))).get("ProjectAttempts") or {}).get("used")
            except (IOError, OSError, ValueError):
                pass
            path = dict(tries).get(used) or tries[-1][1]
            _, peak, qor = attempt_facts(path)
            if peak is not None:
                rows.append((peak, len(tries), qor))
        if rows:
            peaks = sorted(r[0] for r in rows)
            pct = lambda q: peaks[min(len(peaks) - 1, int(len(peaks) * q / 100.0))]
            print("Memory   peak Catapult memory of the attempt used, %d designs: p50 %.1f  p90 %.1f"
                  "  p99 %.1f  max %.1f GB" % (len(peaks), pct(50), pct(90), pct(99), peaks[-1]))
            print("         %-9s %7s %14s" % ("GB", "designs", "mean attempts"))
            for lo, hi in BINS:
                sel = [r for r in rows if lo <= r[0] < hi]
                if sel:
                    print("         %-9s %7d %14.1f" % ("%g-%s" % (lo, "%g" % hi if hi < 1e9 else ""), len(sel),
                                                       sum(r[1] for r in sel) / float(len(sel))))

    print("No QoR   %d design(s)%s" % (len(failed), ":" if failed else ""))
    for s, has_report in failed[:15]:
        tries = attempts(os.path.join(run_dir, "build", s, "catapult_native"))
        step = attempt_facts(tries[-1][1])[0] if tries else "-"
        print("  %-28s %-9s attempts %-3d last step %s" % (s, "report" if has_report else "no report",
                                                         len(tries), step))
    if len(failed) > 15:
        print("  ... (%d more; make check-failed lists them)" % (len(failed) - 15))
    return 0


if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped to head
    sys.exit(main())
