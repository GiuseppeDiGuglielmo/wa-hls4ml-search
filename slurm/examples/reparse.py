#!/usr/bin/env python3
"""Rewrite reports and tarballs of designs whose QoR sits in a retry folder.

    reparse.py <scratch run_dir> [--apply] [--workers N] [--tag TAG] [--stems FILE]

A candidate is a design whose report has no valid QoR (or is missing) while one
of its build/<stem>/catapult_native/Catapult*/ attempts holds nnet_qofr.csv:
reports written before catapult_report.py read retry folders. Without --apply
only the candidates are listed.

With --apply each candidate's old report and tarball are moved to
data/reports/raw_stale_<tag>/ and tarballs_stale_<tag>/, the pipeline's own
iter_manager_catapult._process_single_build writes new ones, and if the new
report is not good the old files are moved back. Every outcome is appended to
<run>/reparsed_<tag>.tsv. Nothing outside the run directory is touched.

TensorFlow and QKeras are stubbed: the report and tarball code does not use them,
so this runs with NERSC's python (module load python) and no venv.
"""

import argparse
import collections
import datetime
import glob
import json
import os
import sys
import types
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from run_status import is_good  # noqa: E402

im = None  # iter_manager_catapult, imported lazily with stubs


def load_pipeline():
    global im
    for name in ("tensorflow", "tensorflow.keras", "tensorflow.keras.models", "qkeras", "qkeras.utils"):
        sys.modules.setdefault(name, types.ModuleType(name))
    sys.modules["tensorflow.keras.models"].model_from_json = None
    sys.modules["qkeras.utils"]._add_supported_quantized_objects = None
    sys.path.insert(0, REPO)
    import iter_manager_catapult  # noqa: E402
    im = iter_manager_catapult


def has_qor_attempt(native):
    for qofr in glob.glob(os.path.join(native, "Catapult*", "*.v*", "nnet_qofr.csv")):
        return True
    return False


def candidates(run_dir, only=None):
    raw = os.path.join(run_dir, "data", "reports", "raw")
    out = []
    for stem in sorted(only or os.listdir(os.path.join(run_dir, "build"))):
        if is_good(os.path.join(raw, stem + ".json")):
            continue
        if has_qor_attempt(os.path.join(run_dir, "build", stem, "catapult_native")):
            out.append(stem)
    return out


def one(job):
    run_dir, tag, stem = job
    raw, tar = os.path.join(run_dir, "data", "reports", "raw"), os.path.join(run_dir, "tarballs")
    raw_old, tar_old = os.path.join(run_dir, "data", "reports", "raw_stale_" + tag), \
        os.path.join(run_dir, "tarballs_stale_" + tag)
    j, t = os.path.join(raw, stem + ".json"), os.path.join(tar, stem + ".tar.gz")
    jo, to = os.path.join(raw_old, stem + ".json"), os.path.join(tar_old, stem + ".tar.gz")
    if is_good(j):
        return stem, "already good"
    if os.path.exists(jo) or os.path.exists(to):
        return stem, "SKIP backup exists in *_stale_%s" % tag
    moved = []
    for src, dst in ((j, jo), (t, to)):
        if os.path.exists(src):
            os.rename(src, dst)
            moved.append((src, dst))
    err = ""
    try:
        ok = im._process_single_build(os.path.join(run_dir, "build", stem, "catapult_native"), run_dir)
    except Exception as e:  # restore below
        ok, err = False, " " + repr(e)[:200]
    if ok and is_good(j) and os.path.exists(t):
        return stem, "rewritten"
    for p in (j, t):
        if os.path.exists(p):
            os.remove(p)
    for src, dst in moved:
        os.rename(dst, src)
    return stem, "RESTORED old files" + err


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--apply", action="store_true", help="rewrite; without it only list candidates")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--tag", default=datetime.date.today().strftime("%Y%m%d"))
    ap.add_argument("--stems", help="file of stems to consider (default: every build folder)")
    args = ap.parse_args()

    run_dir = os.path.abspath(args.run_dir.rstrip("/"))
    if not os.path.isdir(os.path.join(run_dir, "build")):
        sys.exit("reparse: %s is not a scratch run directory (needs build/)" % run_dir)
    only = open(args.stems).read().split() if args.stems else None
    todo = candidates(run_dir, only)
    print("Run      %s" % os.path.basename(run_dir))
    print("To fix   %d report(s) without QoR whose design has QoR in a retry folder (Catapult_N/)" % len(todo))
    for s in todo[:10]:
        print("  %s" % s)
    if len(todo) > 10:
        print("  ... (%d more)" % (len(todo) - 10))
    if not todo:
        return 0
    if not args.apply:
        print("Dry run: nothing written. Add --apply (APPLY=1) to rewrite; old files go to *_stale_%s/."
              % args.tag)
        if len(todo) > 200:
            print("Many designs: tarballs are rebuilt, so run it on a compute node, e.g. sbatch -A amsc011"
                  " -C cpu -q express_amsc -N1 -t 01:30 --wrap='module load python; python %s %s --apply"
                  " --workers 64'" % (os.path.abspath(__file__), run_dir))
        return 0

    load_pipeline()
    for d in ("data/reports/raw_stale_" + args.tag, "tarballs_stale_" + args.tag):
        os.makedirs(os.path.join(run_dir, d), exist_ok=True)
    with Pool(args.workers) as pool:
        results = pool.map(one, [(run_dir, args.tag, s) for s in todo], chunksize=1)
    log = os.path.join(run_dir, "reparsed_%s.tsv" % args.tag)
    with open(log, "a") as f:
        for stem, status in results:
            f.write("%s\t%s\n" % (stem, status))
    for k, v in sorted(collections.Counter(s.split(" ")[0] for _, s in results).items()):
        print("%5d  %s" % (v, k))
    print("log: %s" % log)
    return 0 if all(s in ("rewritten", "already good") for _, s in results) else 1


if __name__ == "__main__":
    sys.exit(main())
