#!/usr/bin/env python3
"""Synthesise one design again, in a fresh copy, to debug it.

    design_synth.py <scratch run_dir> <stem> [--submit] [--qos shared] [--mem 24G]
                    [--time 04:00:00]

The original run is not touched. With --submit a new run folder
$SCRATCH/catapult_debug/run_<now>_<id>/ gets build/<stem>/ with the design's
model (keras_model.h5 and the other top-level build files, no Catapult attempt
folders), a one-line joblist, and a job script that runs it through
iter_manager_catapult.py --run-single-job, as a sweep would. The job is then
submitted. Without --submit the plan is printed and checked with
sbatch --test-only; nothing is written.

Follow it with make design-show RUN=<debug run> STEM=<stem>.
"""

import argparse
import datetime
import os
import shutil
import subprocess
import sys
import tempfile
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from rerun_failed import licenses  # noqa: E402

SCRIPT = """#!/bin/bash
#SBATCH --job-name=debug_{stem}
#SBATCH --account=amsc011
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem={mem}
#SBATCH --constraint=cpu
#SBATCH --time={time}
#SBATCH --qos={qos}
#SBATCH --output={run}/slurm_logs/debug.out
#SBATCH --error={run}/slurm_logs/debug.err

set -euo pipefail
source "{venv}"
export LM_LICENSE_FILE="{lic}"
cd "{repo}"
/usr/bin/time -v python "{repo}/iter_manager_catapult.py" -o "{base}" --run-single-job "$(cat {run}/joblist.txt)"
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("stem")
    ap.add_argument("--submit", action="store_true")
    ap.add_argument("--qos", default="shared")
    ap.add_argument("--mem", default="24G")
    ap.add_argument("--time", default="04:00:00")
    args = ap.parse_args()

    run = os.path.abspath(args.run_dir.rstrip("/"))
    src = os.path.join(run, "build", args.stem)
    line = None
    for l in open(os.path.join(run, "joblist.txt")):
        if os.path.basename(l.split("\t", 1)[0].rstrip("/")) == args.stem:
            line = l.rstrip("\n")
            break
    if line is None or not os.path.isfile(os.path.join(src, "keras_model.h5")):
        sys.exit("design_synth: %s not in %s/joblist.txt or build/%s/keras_model.h5 missing"
                 % (args.stem, run, args.stem))
    scratch = os.environ.get("SCRATCH", "")
    base = os.path.join(scratch, "catapult_debug")
    name = "run_%s_%s" % (datetime.datetime.now().strftime("%Y%m%d_%H%M%S"), uuid.uuid4().hex[:8])
    new_run = os.path.join(base, name)
    new_build = os.path.join(new_run, "build", args.stem)
    fields = line.split("\t")
    fields[0] = new_build
    venv = os.environ.get("WA_HLS4ML_VENV", "/global/common/software/amsc011/public/venv_hls4ml/bin/activate")
    script = SCRIPT.format(stem=args.stem[:40], mem=args.mem, time=args.time, qos=args.qos, run=new_run,
                           venv=venv, lic=licenses(), repo=REPO, base=base)
    top = [n for n in os.listdir(src) if os.path.isfile(os.path.join(src, n))]

    print("Design   %s from %s" % (args.stem, run))
    print("Copy     %s -> %s (%d files: %s)" % (src, new_build, len(top), ", ".join(sorted(top))[:120]))
    print("Job      qos=%s mem=%s time=%s, one design, /usr/bin/time -v for peak memory" % (args.qos, args.mem, args.time))
    if not args.submit:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "debug.sh")
            open(path, "w").write(script)
            p = subprocess.run(["sbatch", "--test-only", path], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, universal_newlines=True)
        print("Check    " + (p.stdout.strip() or "no output"))
        print("Dry run: nothing written. SUBMIT=1 copies the design and submits.")
        return p.returncode

    os.makedirs(new_build)
    os.makedirs(os.path.join(new_run, "slurm_logs"))
    for n in top:
        shutil.copy2(os.path.join(src, n), new_build)
    open(os.path.join(new_run, "joblist.txt"), "w").write("\t".join(fields) + "\n")
    open(os.path.join(new_run, "source_design.txt"), "w").write("%s\t%s\n" % (run, args.stem))
    path = os.path.join(new_run, "debug.sh")
    open(path, "w").write(script)
    p = subprocess.run(["sbatch", "--parsable", path], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, universal_newlines=True)
    if p.returncode != 0:
        print("sbatch failed: %s" % p.stdout.strip())
        return p.returncode
    print("Submitted job %s; run folder %s" % (p.stdout.strip(), new_run))
    print("Then: make design-show RUN=%s STEM=%s" % (new_run, args.stem))
    return 0


if __name__ == "__main__":
    sys.exit(main())
