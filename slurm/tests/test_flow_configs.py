#!/usr/bin/env python
"""Prove the 7 derived flow-config JSONs are reproducible from the base file.

Each of the deleted configs differed from configs/catapult_flow/config_catapult_flow.json
in at most 3 keys: default_reuse_factor, asiclibs and startup. This asserts that
applying Spec.flow_overrides(rf) to the base config yields exactly what each
deleted file contained, using dataclass equality rather than a textual diff.

The expected contents are read from git (the commit before the deletion), so the
test keeps working after the files are gone.

Run from the repo root, with the venv active:
    python slurm/tests/test_flow_configs.py
"""

import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "slurm", "sweeplib"))

from sweep_spec import TECHS  # noqa: E402
from util.catapult_dataflow_config import CatapultDataflowConfig  # noqa: E402

BASE = "configs/catapult_flow/config_catapult_flow.json"

# deleted file -> (tech, reuse factor) it encoded
DERIVED = {
    "configs/catapult_flow/config_catapult_flow_rf1.json": ("nangate45", 1),
    "configs/catapult_flow/config_catapult_flow_rf4.json": ("nangate45", 4),
    "configs/catapult_flow/config_catapult_flow_rf8.json": ("nangate45", 8),
    "configs/catapult_flow/config_catapult_flow_gf22_rf1.json": ("gf22", 1),
    "configs/catapult_flow/config_catapult_flow_gf22_rf4.json": ("gf22", 4),
    "configs/catapult_flow/config_catapult_flow_gf22_rf8.json": ("gf22", 8),
    "configs/catapult_flow/config_catapult_flow_gf22_rf16.json": ("gf22", 16),
}

# The base file is itself the nangate45 RF=16 config.
BASE_KNOBS = ("nangate45", 16)

# Commit that still contains all 8 files, so the expected contents survive deletion.
PRE_DELETION_REF = "393a6994"


def load_expected(path):
    """Read a config from the working tree, or from git if it has been deleted."""
    full = os.path.join(REPO, path)
    if os.path.exists(full):
        with open(full) as f:
            return CatapultDataflowConfig(**json.load(f)), "worktree"
    blob = subprocess.check_output(
        ["git", "-C", REPO, "show", "%s:%s" % (PRE_DELETION_REF, path)]
    )
    return CatapultDataflowConfig(**json.loads(blob.decode())), "git"


def overrides_for(tech, rf):
    return dict(default_reuse_factor=int(rf), **TECHS[tech])


def main():
    base = CatapultDataflowConfig.load_json(os.path.join(REPO, BASE))
    failures = []

    tech, rf = BASE_KNOBS
    if base.override(**overrides_for(tech, rf)) != base:
        failures.append((BASE, "base file is not %s RF=%d as assumed" % (tech, rf)))
    else:
        print("  ok  [base    ] %-52s %s rf=%d" % (BASE, tech, rf))

    for path, (tech, rf) in sorted(DERIVED.items()):
        expected, src = load_expected(path)
        got = base.override(**overrides_for(tech, rf))
        if got == expected:
            print("  ok  [%-8s] %-52s %s rf=%-2d" % (src, path, tech, rf))
        else:
            diff = {
                k: (getattr(expected, k), getattr(got, k))
                for k in vars(expected)
                if getattr(expected, k) != getattr(got, k)
            }
            failures.append((path, "expected vs generated differ: %s" % diff))

    print("\nchecked %d derived configs against %s" % (len(DERIVED), BASE))
    if failures:
        print("FAILED (%d):" % len(failures))
        for path, why in failures:
            print("  %-56s %s" % (path, why))
        return 1
    print("all derived flow configs reproducible from the base file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
