#!/usr/bin/env python3
"""Live console view of one sweep run: progress bar, designs running now, Slurm
jobs, retry round, runtimes and a finish estimate. Read-only; redraws every
--every seconds and stops by itself once the sweep writes sweep_summary.tsv.

    sweep_watch.py RUN_DIR|RUN_NAME          one run folder on scratch
    sweep_watch.py --group G [--rf N]        the newest run of a group (and RF)
    --every S   seconds between redraws (default 10)
    --once      draw once and exit (for logs, scripts, agents)

Every number comes from files the sweep writes or from squeue:
  joblist*.txt                     designs expected
  data/reports/raw, tarballs/      reports, good (valid QoR), tarballs
  slurm_logs/*.err                 "Running single job: .../build/<stem>" = started
  parallel_*.log (GNU joblog)      finished designs, runtime, exit code
  logs/sweep_<id>.out              driver job and its [round N] lines
  squeue                           state of the driver and synthesis jobs
The finish estimate is arithmetic on those facts (left x mean runtime / slots).
"""

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime

from slurm.tools.run_status import is_good, joblists

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STEM_RE = re.compile(r"/build/([^\s/'\"]+)")
START_RE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+ .*Running single job: \S*/build/([^\s/]+)")
ROUND_RE = re.compile(r"\[round (\d+)\]")
COLOR = sys.stdout.isatty() and os.environ.get("TERM") not in (None, "dumb")


def c(text, code):
    return "\033[%sm%s\033[0m" % (code, text) if COLOR else text


def find_run(arg, group, rf):
    scratch = os.environ.get("SCRATCH", "")
    if arg:
        if os.path.isdir(arg):
            return os.path.abspath(arg)
        hits = glob.glob(os.path.join(scratch, "catapult_*", arg))
        if hits:
            return hits[0]
        sys.exit("sweep_watch: no run folder %s (give a scratch run dir or run name)" % arg)
    pattern = "catapult_%s_rf%s" % (group, rf if rf else "*")
    runs = glob.glob(os.path.join(scratch, pattern, "run_*"))
    if not runs:
        sys.exit("sweep_watch: no run under $SCRATCH/%s yet (the driver creates it once it starts)" % pattern)
    return max(runs, key=os.path.getmtime)


class Goodness(object):
    """is_good per report, re-read only when the report file changes."""

    def __init__(self):
        self.cache = {}

    def good(self, path):
        try:
            mt = os.path.getmtime(path)
        except OSError:
            return False
        hit = self.cache.get(path)
        if hit and hit[0] == mt:
            return hit[1]
        ok = is_good(path)
        self.cache[path] = (mt, ok)
        return ok


def names(directory, suffix):
    try:
        return {n[:-len(suffix)] for n in os.listdir(directory) if n.endswith(suffix)}
    except OSError:
        return set()


def joblog(run_dir):
    """[(stem, start epoch, runtime s, exit, signal)] from every GNU parallel joblog."""
    out = []
    for p in glob.glob(os.path.join(run_dir, "parallel_*.log")):
        with open(p, errors="replace") as f:
            for line in f:
                cols = line.rstrip("\n").split("\t")
                if len(cols) < 9 or cols[0] == "Seq":
                    continue
                m = STEM_RE.search(cols[8])
                try:
                    out.append((m.group(1) if m else "?", float(cols[2]), float(cols[3]),
                                int(cols[6]), int(cols[7])))
                except ValueError:
                    pass
    return out


def started(run_dir):
    """{stem: latest start epoch} from the synthesis jobs' stderr logs."""
    out = {}
    for p in glob.glob(os.path.join(run_dir, "slurm_logs", "*.err")):
        with open(p, errors="replace") as f:
            for line in f:
                m = START_RE.match(line)
                if m:
                    t = time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"))
                    out[m.group(2)] = max(t, out.get(m.group(2), 0))
    return out


def driver(run_dir):
    """(driver job id, last round line) from the logs/sweep_<id>.out naming this run."""
    best = None
    for p in glob.glob(os.path.join(REPO, "logs", "sweep_*.out")):
        try:
            text = open(p, errors="replace").read()
        except OSError:
            continue
        if run_dir in text:
            if best is None or os.path.getmtime(p) > os.path.getmtime(best[0]):
                best = (p, text)
    if not best:
        return None, None, None
    jid = re.search(r"sweep_(\d+)\.out$", best[0])
    rounds = [l.strip() for l in best[1].splitlines() if ROUND_RE.search(l)]
    return jid.group(1) if jid else None, (rounds[-1] if rounds else None), best[0]


def jobs(group_rf, driver_id):
    """squeue rows (id, name, state, elapsed, nodes/reason) for this sweep's jobs."""
    try:
        out = subprocess.run(["squeue", "-u", os.environ.get("USER", ""), "-h",
                              "-o", "%i|%j|%T|%M|%R"], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, universal_newlines=True, timeout=30).stdout
    except Exception:
        return None
    rows = []
    for line in out.splitlines():
        cols = line.split("|")
        if len(cols) == 5 and (cols[1].startswith(group_rf + "_") or cols[0] == driver_id):
            rows.append(cols)
    return rows


def summary(run_dir):
    p = os.path.join(run_dir, "sweep_summary.tsv")
    if not os.path.isfile(p):
        return None
    with open(p) as f:
        return dict(l.rstrip("\n").split("\t", 1) for l in f if "\t" in l)


def mmss(seconds):
    seconds = int(max(0, seconds))
    h, rest = divmod(seconds, 3600)
    return ("%d:%02d:%02d" % (h, rest // 60, rest % 60)) if h else ("%d:%02d" % (rest // 60, rest % 60))


def pct(values, q):
    v = sorted(values)
    return v[min(len(v) - 1, int(len(v) * q / 100.0))] if v else None


def bar(good, failed, total, width):
    if not total:
        return "[" + " " * width + "]"
    g = int(round(width * good / float(total)))
    f = min(width - g, int(round(width * failed / float(total))))
    return "[" + c("█" * g, "32") + c("█" * f, "31") + "░" * (width - g - f) + "]"


def draw(run_dir, gcache, every):
    now = time.time()
    width = max(60, min(110, shutil.get_terminal_size((100, 30)).columns))
    folder = os.path.basename(os.path.dirname(run_dir))
    m = re.match(r"catapult_(.+)_rf(\d+)$", folder)
    group_rf = folder[len("catapult_"):] if folder.startswith("catapult_") else folder

    designs = set()
    for tags in joblists(run_dir).values():
        designs |= tags
    rep_dir = os.path.join(run_dir, "data", "reports", "raw")
    reports = names(rep_dir, ".json")
    tarballs = names(os.path.join(run_dir, "tarballs"), ".tar.gz")
    good = {s for s in reports if gcache.good(os.path.join(rep_dir, s + ".json"))}
    total = len(designs) or len(reports)
    failed = reports - good

    log = joblog(run_dir)
    last_end = {}
    for stem, st, rt, _, _ in log:
        last_end[stem] = max(st + rt, last_end.get(stem, 0))
    starts = started(run_dir)
    did, round_line, _ = driver(run_dir)
    q = jobs(group_rf, did)
    synth_running = any(r[2] == "RUNNING" and r[0] != did for r in (q or []))
    running = sorted(((s, t) for s, t in starts.items()
                      if s not in tarballs and t > last_end.get(s, 0)), key=lambda x: x[1])
    if not synth_running:
        running = []
    summ = summary(run_dir)

    out = []
    title = "Sweep %s" % (("%s rf%s" % (m.group(1), m.group(2))) if m else folder)
    clock = datetime.now().strftime("%H:%M:%S")
    out.append(c(title, "1") + "   " + os.path.basename(run_dir) + "   " + clock
               + ("" if every is None else "   (every %ds, Ctrl-C quits)" % every))
    out.append("")

    if q is None:
        out.append("Jobs      squeue unavailable")
    elif not q:
        out.append("Jobs      none in the queue" + (" (finished)" if summ else ""))
    else:
        for i, (jid, name, state, elapsed, where) in enumerate(q):
            label = "driver" if jid == did else "synthesis"
            st = c(state, "32" if state == "RUNNING" else "33")
            out.append("%-9s %-10s %-9s %-24s %s %8s  %s" % ("Jobs" if i == 0 else "", label, jid, name[:24],
                                                             st, elapsed, where))
    if round_line:
        out.append("Round     %s" % round_line)
    out.append("")

    bw = width - 34
    out.append("Progress  %s %s" % (bar(len(good), len(failed), total, bw),
                                    "%d/%d good" % (len(good), total)))
    out.append("          %s good   %s failed (no valid QoR)   %d running   %d not started   tarballs %d"
               % (c(str(len(good)), "32"), c(str(len(failed)), "31" if failed else "0"), len(running),
                  max(0, total - len(reports) - len(running)), len(tarballs)))
    out.append("")

    if running:
        slots = len(running)
        items = ["%s %s" % (s, mmss(now - t)) for s, t in running]
        line, lines = "", []
        for it in items:
            if len(line) + len(it) + 3 > width - 10:
                lines.append(line)
                line = ""
            line += ("   " if line else "") + it
        lines.append(line)
        out.append("Running   " + lines[0])
        out.extend("          " + l for l in lines[1:])
    else:
        slots = None
        out.append("Running   -")

    runtimes = [rt / 60.0 for _, _, rt, ex, _ in log if ex == 0]
    exits = {}
    for _, _, _, ex, sig in log:
        key = ("signal %d" % sig) if sig else ("exit %d" % ex)
        exits[key] = exits.get(key, 0) + 1
    if runtimes:
        out.append("Runtime   p50 %.1f min   p90 %.1f min   max %.1f min   (%d finished: %s)"
                   % (pct(runtimes, 50), pct(runtimes, 90), max(runtimes), len(log),
                      ", ".join("%s x%d" % kv for kv in sorted(exits.items()))))
    else:
        out.append("Runtime   no finished design yet")

    left = total - len(tarballs)
    if summ:
        out.append("")
        out.append(c("Finished  %s: %s/%s with tarball, %s retry round(s), archive_sync exit %s, %s"
                     % (summ.get("stopped", "?"), summ.get("with_tarball", "?"), summ.get("designs", "?"),
                        summ.get("retry_rounds", "?"), summ.get("archive_sync_exit", "?"),
                        summ.get("finished", "")), "1"))
        out.append("Next      make check-run RUN=%s" % run_dir)
    elif left > 0 and runtimes and slots:
        mean = sum(runtimes) / len(runtimes)
        eta = (left * mean / slots) * 60 - (sum(now - t for _, t in running) / slots)
        out.append("Estimate  ~%s to go (%d left x %.1f min mean / %d slots), around %s"
                   % (mmss(max(eta, 0)), left, mean, slots,
                      datetime.fromtimestamp(now + max(eta, 0)).strftime("%H:%M")))
    elif not q:
        out.append("Status    no job in the queue and no sweep_summary.tsv: a run made outside the sweep")
        out.append("          loop, or its driver ended early. make check-run RUN=%s" % run_dir)
    elif left == 0 and total:
        out.append("Estimate  all designs have a tarball; the driver archives and writes the summary next")
    return "\n".join(out), summ is not None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", nargs="?", help="scratch run folder or run name")
    ap.add_argument("--group", help="catalog group: watch its newest run")
    ap.add_argument("--rf", help="with --group: the reuse factor")
    ap.add_argument("--every", type=int, default=10)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    if not args.run and not args.group:
        ap.error("give a run folder, a run name, or --group")

    gcache = Goodness()
    if args.once:
        text, _ = draw(find_run(args.run, args.group, args.rf), gcache, None)
        print(text)
        return 0
    try:
        while True:
            try:
                run_dir = find_run(args.run, args.group, args.rf)
            except SystemExit as e:   # the driver has not made the run folder yet
                text, done = "%s\nwaiting ... %s" % (e, datetime.now().strftime("%H:%M:%S")), False
            else:
                text, done = draw(run_dir, gcache, args.every)
            sys.stdout.write("\033[H\033[2J" + text + "\n")
            sys.stdout.flush()
            if done:
                return 0
            time.sleep(args.every)
    except KeyboardInterrupt:
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
