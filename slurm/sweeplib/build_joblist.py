#!/usr/bin/env python
"""Turn a candidates file into models plus a joblist for one reuse-factor group.

Writes, under the run directory:

    build/<tag>/keras_model.h5      the model to synthesise
    data/models/<tag>/dataflow_config.json   its flow config
    joblist.txt                     one tab-separated job line per design

The job lines are exactly what `iter_manager_catapult.py --run-single-job`
consumes, so GNU parallel can fan them out unchanged.

Two model sources, which is the only real difference between the campaigns that
used this path:

    synth    build the QKeras model from the architecture in the candidates file
             (45nm N-layer LHS, sz128)
    archive  extract model.json from the matching 45nm tarball and rebuild it, so
             GF22 re-synthesises the identical network (GF22 N-layer LHS). Here
             the candidates file holds (run_name, stem) pairs and the build tag
             is '<run uuid>__<stem>' to keep stems from different runs apart.
"""

import argparse
import os
import re
import sys
import tarfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sweep_spec import load_catalog  # noqa: E402
from util.catapult_dataflow_config import CatapultDataflowConfig  # noqa: E402

SHELL_SCRIPT = os.path.join(REPO, "Perlmutter_scripts", "catapult_shell.sh")
FLOW_TCL = os.path.join(REPO, "util", "catapult_hls4ml_flow.tcl")
ARCHIVE_45NM = "/global/cfs/cdirs/amsc011/shared/wa-hls4ml-catapult/nangate45"
MODEL_JSON_RE = re.compile(r"^model(_\d+)?\.json$")


def _keras_from_json(model_json):
    """Rebuild a QKeras model from its serialized architecture."""
    from tensorflow.keras.models import model_from_json

    custom = {}
    try:
        from qkeras.utils import _add_supported_quantized_objects

        _add_supported_quantized_objects(custom)
    except Exception:
        custom = None
    return model_from_json(model_json, custom_objects=custom) if custom \
        else model_from_json(model_json)


def build_synth(line, n_layers, config_params, build_dir):
    """Build the model described by a candidates line."""
    from gen_models import _build_dense_model

    parts = line.split("\t")
    stem = parts[0]
    in_sz = int(parts[1])
    sizes = [int(x) for x in parts[2:2 + n_layers]]
    bw = int(parts[2 + n_layers])
    acts = parts[3 + n_layers:3 + 2 * n_layers]

    model = _build_dense_model(list(zip(sizes, acts)), bw, config_params, input_size=in_sz)
    os.makedirs(build_dir, exist_ok=True)
    model.save(os.path.join(build_dir, "keras_model.h5"), include_optimizer=False)
    return stem


def find_model_json(names):
    """Locate the serialized Keras architecture inside an archived tarball.

    The archive holds two layouts. The cartesian runs write a top-level
    model.json; the joblist-driven runs (N-layer LHS, sz128) write it under
    catapult_native/ and suffix it with the design index, e.g. model_974.json.
    Prefer the top-level file, then any model[_<idx>].json, and never match the
    cat_ai_nn_config*.json files sitting alongside them.
    """
    if "model.json" in names:
        return "model.json"
    matches = [n for n in names if MODEL_JSON_RE.match(os.path.basename(n))]
    return sorted(matches)[0] if matches else None


def build_archive(line, build_dir):
    """Rebuild the model of an already-synthesised 45nm design from its tarball."""
    run_name, stem = line.split("\t", 1)
    tarball = os.path.join(ARCHIVE_45NM, run_name, "tarballs", stem + ".tar.gz")
    if not os.path.exists(tarball):
        raise IOError("no tarball %s" % tarball)

    with tarfile.open(tarball) as tf:
        member = find_model_json(tf.getnames())
        if member is None:
            raise IOError("no model json in %s" % tarball)
        model_json = tf.extractfile(tf.getmember(member)).read().decode()

    os.makedirs(build_dir, exist_ok=True)
    with open(os.path.join(build_dir, "model.json"), "w") as f:
        f.write(model_json)
    model = _keras_from_json(model_json)
    model.save(os.path.join(build_dir, "keras_model.h5"), include_optimizer=False)


def tag_for(source, line):
    if source == "synth":
        return line.split("\t", 1)[0]
    run_name, stem = line.split("\t", 1)
    return "%s__%s" % (run_name.rsplit("_", 1)[-1], stem)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--group", required=True)
    ap.add_argument("--catalog", default=os.path.join(REPO, "slurm", "sweeps.tsv"))
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--rf", type=int, required=True)
    ap.add_argument("--flow-config", default=os.path.join(
        REPO, "configs", "catapult_flow", "config_catapult_flow.json"))
    args = ap.parse_args()

    spec = load_catalog(args.catalog).get(args.group)
    if spec is None:
        ap.error("group %r not in %s" % (args.group, args.catalog))

    source = "archive" if spec.mode == "archive_lhs" else "synth"
    base_cfg = CatapultDataflowConfig.load_json(args.flow_config)
    base_cfg = base_cfg.override(**spec.flow_overrides(args.rf))

    build_root = os.path.join(args.run_dir, "build")
    data_root = os.path.join(args.run_dir, "data", "models")
    joblist_path = os.path.join(args.run_dir, "joblist.txt")

    config_params = {
        "weight_int_width": spec.weight_int_width,
        "activ_int_width": spec.activ_int_width,
        "probs": {"activations": spec.activation_mask()},
    }

    with open(args.candidates) as f:
        lines = [l.strip() for l in f if l.strip()]

    print("  Building %d models (%s, rf=%d)..." % (len(lines), source, args.rf))
    joblines, skipped = [], []
    for i, line in enumerate(lines):
        tag = tag_for(source, line)
        build_dir = os.path.join(build_root, tag)
        data_dir = os.path.join(data_root, tag)
        try:
            if source == "synth":
                build_synth(line, spec.n_layers, config_params, build_dir)
            else:
                build_archive(line, build_dir)
        except Exception as exc:
            print("  Warning: model build failed for %s: %s" % (tag, exc))
            skipped.append(tag)
            continue

        os.makedirs(data_dir, exist_ok=True)
        cfg_path = os.path.join(data_dir, "dataflow_config.json")
        base_cfg.override(output_dir=os.path.join(build_dir, "catapult_native")).save_json(cfg_path)
        joblines.append("\t".join([build_dir, SHELL_SCRIPT, FLOW_TCL, cfg_path]))

        if (i + 1) % 500 == 0:
            print("  ... %d/%d  ready=%d  skipped=%d"
                  % (i + 1, len(lines), len(joblines), len(skipped)))

    with open(joblist_path, "w") as f:
        f.write("\n".join(joblines) + ("\n" if joblines else ""))

    print("  Joblist: %d ready, %d skipped -> %s" % (len(joblines), len(skipped), joblist_path))
    for s in skipped[:10]:
        print("    %s" % s)
    if len(skipped) > 10:
        print("    ... and %d more" % (len(skipped) - 10))
    return 0 if joblines else 1


if __name__ == "__main__":
    sys.exit(main())
