#!/usr/bin/env python3
"""Recreate the scratch folder of an archive-only run, for its failed designs only.

    rebuild_from_archive.py <archive run name> [--apply] [--stems s1,s2,...]

The archive keeps one report and one project tarball per design, not the model
(keras_model.h5) or the flow config (dataflow_config.json) a rerun needs. This
rebuilds both for the designs without valid QoR (or --stems), in the run's
original scratch path (from its source_dir.txt), so that make rerun-failed,
check-run, archive-dry and archive work on it unchanged.

- model: catapult_native/model[_<i>].json + its weights .h5 from the design's own
  archived tarball when that opens; else keras_model.h5 of the same stem in a
  scratch run of the same group at another RF; else the model from that stem's
  tarball in an archived run of the same group at another RF. Only the own tarball
  reproduces the design: the architecture is the same at every RF, but each RF run
  drew its own random weights, so the fallbacks synthesise a different network
  (the plan marks them "other RF").
- flow config: configs/catapult_flow/config_catapult_flow.json with the catalog's
  overrides for the run's group and RF (PROVENANCE.md, else the source folder), as a sweep makes it.

Without --apply it prints the plan and writes nothing. It refuses to write into a
scratch folder that already exists. Needs the DSE venv (TensorFlow, QKeras).
"""

import argparse
import glob
import io
import json
import os
import re
import shutil
import sys
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

from slurm.tools.list_runs import ARCHIVE, run_groups  # noqa: E402
from slurm.tools.run_status import is_good  # noqa: E402

FLOW_CFG = os.path.join(REPO, "configs", "catapult_flow", "config_catapult_flow.json")
from slurm.tools.run_status import TECH_DIRS  # noqa: E402


def find_archive_run(name):
    for tech in TECH_DIRS:
        d = os.path.join(ARCHIVE, tech, name)
        if os.path.isdir(d):
            return tech, d
    sys.exit("rebuild_from_archive: %s not found under %s" % (name, ARCHIVE))


def group_folder(source_dir):
    """catapult_45nm_2layer_sz128_rf4/run_x -> ('catapult_45nm_2layer_sz128', 4, '').

    Some 3-layer sz64 folders put a slice name after the RF
    (catapult_dense_3layers_sz64_inp_rf4_l1a -> (..._sz64_inp, 4, '_l1a')); runs of
    the same group at other RFs share both the prefix and that suffix.
    """
    folder = os.path.basename(os.path.dirname(source_dir.rstrip("/")))
    m = re.match(r"(.+)_rf(\d+)(_l1[ab])?$", folder)
    if not m:
        sys.exit("rebuild_from_archive: cannot read group/RF from %s" % folder)
    return m.group(1), int(m.group(2)), m.group(3) or ""


def model_sources(tech, prefix, run_name, suffix=""):
    """Scratch runs and archived runs of the same group, any other RF."""
    folder_re = re.compile(re.escape(prefix) + r"_rf\d+" + re.escape(suffix) + "$")
    scratch = sorted(d for d in glob.glob(os.path.join(os.environ.get("SCRATCH", ""), prefix + "_rf*", "run_*"))
                     if folder_re.match(os.path.basename(os.path.dirname(d))))
    archived = []
    for d in sorted(glob.glob(os.path.join(ARCHIVE, tech, "run_*"))):
        if os.path.basename(d) == run_name:
            continue
        try:
            src = open(os.path.join(d, "source_dir.txt")).read().strip()
        except (IOError, OSError):
            continue
        if folder_re.match(os.path.basename(os.path.dirname(src))):
            archived.append(d)
    return scratch, archived


def find_model(stem, scratch_runs, archived_runs, own_run=None):
    if own_run:
        tb = os.path.join(own_run, "tarballs", stem + ".tar.gz")
        try:
            with tarfile.open(tb) as tf:
                if model_members(set(tf.getnames())):
                    return ("own", tb)
        except (tarfile.TarError, OSError, EOFError):
            pass
    for r in scratch_runs:
        h5 = os.path.join(r, "build", stem, "keras_model.h5")
        if os.path.isfile(h5):
            return ("copy", h5)
    for r in archived_runs:
        tb = os.path.join(r, "tarballs", stem + ".tar.gz")
        if not os.path.isfile(tb):
            continue
        try:
            with tarfile.open(tb) as tf:
                names = set(tf.getnames())
        except (tarfile.TarError, OSError, EOFError):
            continue
        pair = model_members(names)
        if pair:
            return ("tarball", tb)
    return (None, None)


def model_members(names):
    """(architecture json, weights h5) in a tarball: model.json + model_weights.h5,
    or the older model_<index>.json + model_<index>_weights.h5."""
    for n in sorted(names):
        m = re.match(r"catapult_native/(model(_\d+)?)\.json$", n)
        if m and "catapult_native/%s_weights.h5" % m.group(1) in names:
            return n, "catapult_native/%s_weights.h5" % m.group(1)
    return None


def write_model(kind, src, dest):
    if kind == "copy":
        shutil.copy2(src, dest)
        return
    # "own" and "tarball" both read the model out of an archived tarball.
    import tensorflow as tf_mod
    from qkeras.utils import _add_supported_quantized_objects
    co = {}
    _add_supported_quantized_objects(co)
    with tarfile.open(src) as tf:
        arch_name, weights_name = model_members(set(tf.getnames()))
        arch = tf.extractfile(arch_name).read().decode()
        weights = tf.extractfile(weights_name).read()
    model = tf_mod.keras.models.model_from_json(arch, custom_objects=co)
    tmp = dest + ".weights.h5"
    with open(tmp, "wb") as f:
        f.write(weights)
    model.load_weights(tmp)
    os.remove(tmp)
    model.save(dest, include_optimizer=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--stems", help="comma-separated stems (default: designs without valid QoR)")
    args = ap.parse_args()

    name = os.path.basename(args.run.rstrip("/"))
    tech, arch = find_archive_run(name)
    source = open(os.path.join(arch, "source_dir.txt")).read().strip()
    prefix, rf, suffix = group_folder(source)
    label = run_groups({name: os.path.basename(os.path.dirname(source.rstrip("/")))}).get(name, "")
    m = re.match(r"(\S+) rf(\d+)$", label)
    if not m or int(m.group(2)) != rf:
        sys.exit("rebuild_from_archive: group for %s is %r (PROVENANCE.md or the source folder); "
                 "need '<group> rf%d'" % (name, label, rf))
    group = m.group(1)

    if args.stems:
        stems = [s for s in args.stems.split(",") if s]
    else:
        stems = sorted(os.path.basename(f)[:-5] for f in glob.glob(os.path.join(arch, "reports", "*.json"))
                       if not is_good(f))
    scratch_runs, archived_runs = model_sources(tech, prefix, name, suffix)
    plan = [(s,) + find_model(s, scratch_runs, archived_runs, arch) for s in stems]

    print("Run      %s (%s, group %s, RF=%d)" % (name, tech, group, rf))
    print("Scratch  %s%s" % (source, "  (EXISTS: refusing to write)" if os.path.exists(source) else ""))
    print("Designs  %d without valid QoR in the archive%s" % (len(plan), "" if plan else "; nothing to rebuild"))
    for stem, kind, src in plan:
        print("  %-24s model %s%s" % (stem, "%s %s" % (kind, src) if kind else "NOT FOUND",
                                       "  (other RF: different weights)" if kind in ("copy", "tarball") else ""))
    other = sum(1 for _, k, _ in plan if k in ("copy", "tarball"))
    if other:
        print("Note     %d design(s) take their model from another RF run, whose weights differ;"
              " their new QoR will not reproduce the archived report" % other)
    missing = [s for s, k, _ in plan if not k]
    if not args.apply:
        print("Dry run: nothing written. --apply (APPLY=1) builds the folder.")
        return 1 if missing or os.path.exists(source) else 0
    if os.path.exists(source):
        sys.exit("rebuild_from_archive: %s exists; not touching it" % source)
    if missing:
        sys.exit("rebuild_from_archive: no model for %s" % ", ".join(missing))

    from slurm.sweeplib.sweep_spec import load_catalog
    from util.catapult_dataflow_config import CatapultDataflowConfig
    spec = load_catalog(os.path.join(REPO, "slurm", "sweeps.tsv"))[group]
    base = CatapultDataflowConfig.load_json(FLOW_CFG).override(**spec.flow_overrides(rf))
    shell = os.path.join(REPO, "Perlmutter_scripts", "catapult_shell.sh")
    flow = os.path.join(REPO, "util", "catapult_hls4ml_flow.tcl")
    lines = []
    for stem, kind, src in plan:
        build = os.path.join(source, "build", stem)
        data = os.path.join(source, "data", "models", stem)
        os.makedirs(build)
        os.makedirs(data)
        write_model(kind, src, os.path.join(build, "keras_model.h5"))
        cfg = os.path.join(data, "dataflow_config.json")
        base.override(output_dir=os.path.join(build, "catapult_native")).save_json(cfg)
        lines.append("\t".join([build, shell, flow, cfg]) + "\n")
    for sub in ("data/reports/raw", "tarballs", "slurm_logs"):
        os.makedirs(os.path.join(source, sub), exist_ok=True)
    with open(os.path.join(source, "joblist.txt"), "w") as f:
        f.writelines(lines)
    with open(os.path.join(source, "REBUILT_FROM_ARCHIVE.txt"), "w") as f:
        f.write("Rebuilt by slurm/repairs/rebuild_from_archive.py from %s for %d design(s).\n" % (arch, len(lines)))
    print("Built    %s (%d designs). Next: make rerun-failed RUN=%s" % (source, len(lines), source))
    return 0


if __name__ == "__main__":
    sys.exit(main())
