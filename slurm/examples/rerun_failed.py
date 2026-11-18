#!/usr/bin/env python3
"""Synthesise again only the designs of a scratch run that have no valid QoR.

    rerun_failed.py <scratch run_dir> [--submit] [--qos Q] [--time T]
                    [--parallelism N] [--mem M] [--memfree M] [--stems FILE]

Targets are joblist.txt designs whose report is missing or has no valid QoR and
that have no QoR in any Catapult* attempt either (those only need reparse.py).
Without --submit it prints the targets and validates the job with
sbatch --test-only, writing nothing.

With --submit it writes joblist_retry_<tag>.txt and parallel_synth_retry_<tag>.sh
in the run, moves each target's old report and tarball to
data/reports/raw_stale_<tag>/ and tarballs_stale_<tag>/ (a design with a tarball
is never rerun), and submits one job. Afterwards: make check-run, then archive.

Small sets (8 designs or fewer) go to the shared QOS with 24G per design, larger
ones to a whole express_amsc node gated by GNU parallel --memfree. sbatch
--test-only start estimates for the shared QOS can be months off (seen
2026-11-05); past shared jobs started within hours.
"""

import argparse
import datetime
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from run_status import is_good  # noqa: E402
from reparse import has_qor_attempt  # noqa: E402

SCRIPT = """#!/bin/bash
#SBATCH --job-name=retry_{name}
#SBATCH --account=amsc011
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task={cpus}
#SBATCH --mem={mem}
#SBATCH --constraint=cpu
#SBATCH --time={time}
#SBATCH --qos={qos}
#SBATCH --output={run}/slurm_logs/parallel_retry_{tag}.out
#SBATCH --error={run}/slurm_logs/parallel_retry_{tag}.err

set -euo pipefail
source "{venv}"
export LM_LICENSE_FILE="{lic}"
export CATAPULT_PRODUCT="{product}"
cd "{repo}"

parallel \\
    --joblog "{run}/parallel_retry_{tag}.log" \\
    --resume-failed \\
    {memfree}--line-buffer \\
    -j {jobs} \\
    python "{repo}/iter_manager_catapult.py" -o "{base}" --run-single-job {{}} \\
    < "{joblist}"
"""


def licenses():
    """License servers for the job: WA_LICENSES (port@host[:...]) if set, else the
    servers in license_servers_perlmutter.json."""
    if os.environ.get("WA_LICENSES"):
        return os.environ["WA_LICENSES"]
    import json
    with open(os.path.join(REPO, "license_servers_perlmutter.json")) as f:
        return ":".join("%s@%s" % (s["port"], s["host"]) for s in json.load(f)["servers"])


def product():
    """Catapult product the launcher asks a license for (CATAPULT_PRODUCT)."""
    return os.environ.get("CATAPULT_PRODUCT", "genesis")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--submit", action="store_true")
    ap.add_argument("--qos")
    ap.add_argument("--time", default="05:30:00")
    ap.add_argument("--parallelism", type=int)
    ap.add_argument("--mem")
    ap.add_argument("--memfree", default="64G")
    ap.add_argument("--stems", help="only these stems (file, one per line)")
    ap.add_argument("--tag", default=datetime.datetime.now().strftime("%Y%m%d_%H%M"))
    args = ap.parse_args()

    run = os.path.abspath(args.run_dir.rstrip("/"))
    joblist = os.path.join(run, "joblist.txt")
    if not os.path.isfile(joblist) or not os.path.isdir(os.path.join(run, "build")):
        sys.exit("rerun_failed: %s is not a scratch run directory (needs joblist.txt and build/)" % run)
    only = set(open(args.stems).read().split()) if args.stems else None
    raw = os.path.join(run, "data", "reports", "raw")

    lines, reparse_first = [], []
    for line in open(joblist):
        if not line.strip():
            continue
        stem = os.path.basename(line.split("\t", 1)[0].rstrip("/"))
        if only is not None and stem not in only:
            continue
        if is_good(os.path.join(raw, stem + ".json")):
            continue
        if has_qor_attempt(os.path.join(run, "build", stem, "catapult_native")):
            reparse_first.append(stem)
            continue
        lines.append((stem, line if line.endswith("\n") else line + "\n"))

    print("Run      %s" % os.path.basename(run))
    print("Targets  %d design(s) without QoR anywhere" % len(lines))
    for stem, _ in lines[:10]:
        print("  %s" % stem)
    if len(lines) > 10:
        print("  ... (%d more)" % (len(lines) - 10))
    if reparse_first:
        print("Skipped  %d design(s) whose QoR is already in a retry folder: run make reparse first"
              % len(reparse_first))
    if not lines:
        return 0

    n = len(lines)
    small = n <= 8
    qos = args.qos or ("shared" if small else "express_amsc")
    jobs = args.parallelism or (n if small else min(n, 100))
    mem = args.mem or ("%dG" % (24 * jobs) if qos == "shared" else "0")
    if qos == "shared" and mem == "0":
        sys.exit("rerun_failed: --qos shared needs --mem")
    # On a shared node /proc/meminfo counts other users' jobs, so --memfree only makes
    # sense on a whole node.
    memfree = "--memfree %s " % args.memfree if args.memfree not in ("", "0") and qos != "shared" else ""
    base = os.path.dirname(run)
    venv = os.environ.get("WA_HLS4ML_VENV", "/global/common/software/amsc011/public/venv_hls4ml/bin/activate")
    fields = dict(name=os.path.basename(base)[:40], cpus=2 * jobs if qos == "shared" else 256, mem=mem,
                  time=args.time, qos=qos, run=run, tag=args.tag, venv=venv, lic=licenses(), product=product(), repo=REPO,
                  memfree=memfree, jobs=jobs, base=base,
                  joblist=os.path.join(run, "joblist_retry_%s.txt" % args.tag))
    print("Job      qos=%s  time=%s  mem=%s  slots=%d  %s" % (qos, args.time, mem, jobs, memfree.strip()))

    if not args.submit:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "retry.sh")
            with open(path, "w") as f:
                f.write(SCRIPT.format(**fields))
            p = subprocess.run(["sbatch", "--test-only", path], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, universal_newlines=True)
        print("Check    " + (p.stdout.strip() or "sbatch --test-only gave no output"))
        print("Dry run: nothing written. Add --submit (SUBMIT=1) to move the old files and submit.")
        return p.returncode

    with open(fields["joblist"], "w") as f:
        f.writelines(l for _, l in lines)
    script = os.path.join(run, "parallel_synth_retry_%s.sh" % args.tag)
    with open(script, "w") as f:
        f.write(SCRIPT.format(**fields))
    os.makedirs(os.path.join(run, "slurm_logs"), exist_ok=True)
    for sub, ext in (("data/reports/raw", ".json"), ("tarballs", ".tar.gz")):
        stale = os.path.join(run, os.path.dirname(sub), os.path.basename(sub) + "_stale_" + args.tag) \
            if "/" in sub else os.path.join(run, sub + "_stale_" + args.tag)
        os.makedirs(stale, exist_ok=True)
        for stem, _ in lines:
            src = os.path.join(run, sub, stem + ext)
            if os.path.exists(src):
                os.rename(src, os.path.join(stale, stem + ext))
    p = subprocess.run(["sbatch", "--parsable", script], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, universal_newlines=True)
    print("Submitted job %s (%s)" % (p.stdout.strip(), script) if p.returncode == 0 else
          "sbatch failed: %s" % p.stdout.strip())
    return p.returncode


if __name__ == "__main__":
    sys.exit(main())
