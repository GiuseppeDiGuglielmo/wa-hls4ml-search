#!/usr/bin/env python
"""Freeze the design-space contract before the sweep-catalog migration.

Writes slurm/tests/golden_design_space.tsv with two kinds of row:

  sweep       one per cartesian model-sweep group: design count + sha256 over the
              ordered stem -> (input, sizes, bitwidth, activations) listing
  candidates  one per LHS / sz128 candidates file already in the shared archive:
              line count + sha256 of the file itself

Together these pin every design that has ever been synthesised and archived. The
migration is only correct if check_design_space.py reproduces this file exactly
from the new slurm/sweeps.tsv catalog.

The sweep rows were originally derived from the per-group JSON configs, before
those were replaced by slurm/sweeps.tsv (see commit 393a6994). They now come
from the catalog. Regenerating is for ADDING groups only: if an existing row's
hash changes, that is the migration breaking, not the contract being stale.

Run from the repo root, with the venv active:
    python slurm/tests/make_golden.py
"""

import hashlib
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "slurm", "sweeplib"))

from enumerate_space import digest  # noqa: E402
from sweep_spec import load_catalog, spec_from_json  # noqa: E402

ARCHIVE = "/global/cfs/cdirs/amsc011/shared/wa-hls4ml-catapult"
GOLDEN = os.path.join(REPO, "slurm", "tests", "golden_design_space.tsv")

# Referenced by no script and superseded by the catalog — deliberately excluded
# so they don't become part of the contract.
DEAD = {"config_dense_1layer_gf22_test.json", "config_dense_4layers.json"}

# Random-sampling schema, kept but never part of the cartesian contract.
KEPT_LEGACY_SCHEMA = {"config_dense_1to3layers.json", "config_dense_latency_fast.json",
                      "config_dense_latency_fast_toy.json"}

# The candidates files are the ground truth for the sampled groups: the samplers
# must reproduce them bit-for-bit, not merely produce "a valid LHS".
CANDIDATES = [
    ("nangate45", "nangate45_lhs_4layer_2500.txt"),
    ("nangate45", "nangate45_lhs_5layer_2500.txt"),
    ("nangate45", "nangate45_lhs_6layer_2500.txt"),
    ("nangate45", "nangate45_lhs_8layer_2500.txt"),
    ("nangate45", "nangate45_lhs_10layer_2500.txt"),
    ("nangate45", "nangate45_1layer_sz128_cartesian.txt"),
    ("nangate45", "nangate45_2layer_sz128_cartesian.txt"),
    ("gf22fdx", "gf22_lhs_2layer_1350.txt"),
    ("gf22fdx", "gf22_lhs_3layer_500.txt"),
    ("gf22fdx", "gf22_lhs_3layer_10000.txt"),
]


def collect():
    rows = []
    sweeps_dir = os.path.join(REPO, "configs", "model_sweeps")
    if os.path.isdir(sweeps_dir) and any(
            f.startswith("config_dense_") and f not in DEAD
            and f not in KEPT_LEGACY_SCHEMA
            for f in os.listdir(sweeps_dir)):
        source = "legacy configs/model_sweeps/*.json"
        for fn in sorted(os.listdir(sweeps_dir)):
            if fn in DEAD or not fn.endswith(".json"):
                continue
            try:
                spec = spec_from_json(os.path.join(sweeps_dir, fn))
            except (ValueError, KeyError):
                continue  # legacy random-sampling schema: no cartesian space to pin
            count, sha = digest(spec)
            rows.append(("sweep", fn[len("config_"): -len(".json")], count, sha))
    else:
        source = "slurm/sweeps.tsv"
        for spec in load_catalog(os.path.join(REPO, "slurm", "sweeps.tsv")).values():
            if not spec.legacy or spec.mode != "cartesian":
                continue
            count, sha = digest(spec)
            rows.append(("sweep", spec.legacy, count, sha))
        rows.sort(key=lambda r: r[1])
    print("  sweep rows from: %s" % source)

    for tech, fn in CANDIDATES:
        with open(os.path.join(ARCHIVE, tech, fn), "rb") as f:
            data = f.read()
        rows.append(("candidates", tech + "/" + fn, data.count(b"\n"),
                     hashlib.sha256(data).hexdigest()))
    return rows


def main():
    rows = collect()
    with open(GOLDEN, "w") as f:
        f.write("# Design-space contract for the sweep-catalog migration.\n")
        f.write("# Regenerate:  python slurm/tests/make_golden.py\n")
        f.write("# Verify:      python slurm/tests/check_design_space.py\n")
        f.write("#\n")
        f.write("# kind\tname\tdesigns\tsha256\n")
        for kind, name, count, sha in rows:
            f.write("%s\t%s\t%d\t%s\n" % (kind, name, count, sha))

    n_sweep = sum(1 for r in rows if r[0] == "sweep")
    n_cand = len(rows) - n_sweep
    total = sum(r[2] for r in rows if r[0] == "sweep")
    print("Wrote %s" % GOLDEN)
    print("  %d sweep groups (%d designs), %d candidates files" % (n_sweep, total, n_cand))
    return 0


if __name__ == "__main__":
    sys.exit(main())
