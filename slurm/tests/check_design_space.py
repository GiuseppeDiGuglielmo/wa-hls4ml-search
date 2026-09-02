#!/usr/bin/env python
"""Verify that the sweep catalog still describes exactly the archived design space.

Re-derives every row of slurm/tests/golden_design_space.tsv and compares:

  sweep       design count + sha256 over the ordered stem -> architecture listing,
              taken from slurm/sweeps.tsv when a row exists for that group
              (matched via the catalog's `legacy` column), else from the legacy
              configs/model_sweeps/*.json
  candidates  sha256 of the LHS / sz128 candidates file in the shared archive

A pass means every archived `dense_{N}l_{idx}` stem still denotes the same
circuit, so the archive's join keys stay valid.

Run from the repo root, with the venv active:
    python slurm/tests/check_design_space.py [--source auto|tsv|json]
"""

import argparse
import hashlib
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "slurm", "sweeplib"))

from enumerate_space import digest  # noqa: E402
from sweep_spec import load_catalog, spec_from_json  # noqa: E402

ARCHIVE = "/global/cfs/cdirs/amsc011/shared/wa-hls4ml-catapult"
GOLDEN = os.path.join(REPO, "slurm", "tests", "golden_design_space.tsv")
CATALOG = os.path.join(REPO, "slurm", "sweeps.tsv")


def _normalize(cfg):
    """Compare generator configs by meaning: the legacy files spell the bitwidth
    list either explicitly or as bitwidth_lb/ub, and carry no other optional keys."""
    out = dict(cfg)
    if "bitwidths" not in out and "bitwidth_lb" in out:
        out["bitwidths"] = list(range(out.pop("bitwidth_lb"),
                                      out.pop("bitwidth_ub") + 1, 2))
    return json.loads(json.dumps(out, sort_keys=True))


def read_golden():
    rows = []
    with open(GOLDEN) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            kind, name, count, sha = line.rstrip("\n").split("\t")
            rows.append((kind, name, int(count), sha))
    return rows


def catalog_by_legacy(source):
    """{legacy config basename without 'config_'/'.json' -> Spec}, or {} if unused."""
    if source == "json" or not os.path.exists(CATALOG):
        return {}
    by_legacy = {}
    for spec in load_catalog(CATALOG).values():
        legacy = getattr(spec, "legacy", None)
        if legacy and legacy != "-":
            by_legacy[legacy] = spec
    return by_legacy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["auto", "tsv", "json"], default="auto",
                    help="where sweep specs come from (default: catalog if present)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    by_legacy = catalog_by_legacy(args.source)
    if args.source == "tsv" and not by_legacy:
        print("ERROR: --source tsv but %s has no usable rows" % CATALOG, file=sys.stderr)
        return 2

    failures = []
    used = {"tsv": 0, "json": 0, "file": 0}

    for kind, name, exp_count, exp_sha in read_golden():
        if kind == "sweep":
            if name in by_legacy:
                spec, src = by_legacy[name], "tsv"
            else:
                if args.source == "tsv":
                    failures.append((name, "no catalog row with legacy=%s" % name))
                    continue
                path = os.path.join(REPO, "configs", "model_sweeps", "config_%s.json" % name)
                if not os.path.exists(path):
                    failures.append((name, "neither a catalog row nor %s" % path))
                    continue
                spec, src = spec_from_json(path), "json"
            got_count, got_sha = digest(spec)

            # The stem digest pins the architecture enumeration, but not the
            # quantizer widths that _build_dense_model reads. Compare the whole
            # rendered generator config against the file it replaces.
            legacy_path = os.path.join(REPO, "configs", "model_sweeps",
                                       "config_%s.json" % name)
            if src == "tsv" and os.path.exists(legacy_path):
                with open(legacy_path) as f:
                    want = json.load(f)
                have = spec.to_gen_model_config()
                if _normalize(have) != _normalize(want):
                    failures.append((name, "rendered gen_model config differs from %s: "
                                           "%s vs %s" % (legacy_path, have, want)))
        else:
            src = "file"
            path = os.path.join(ARCHIVE, name)
            if not os.path.exists(path):
                failures.append((name, "missing candidates file %s" % path))
                continue
            with open(path, "rb") as f:
                data = f.read()
            got_count, got_sha = data.count(b"\n"), hashlib.sha256(data).hexdigest()

        used[src] += 1
        if (got_count, got_sha) != (exp_count, exp_sha):
            failures.append((name, "expected %d/%s got %d/%s"
                             % (exp_count, exp_sha[:12], got_count, got_sha[:12])))
        elif args.verbose:
            print("  ok  [%-4s] %-44s %8d" % (src, name, got_count))

    print("checked %d sweep groups (%d from catalog, %d from legacy JSON) "
          "and %d candidates files"
          % (used["tsv"] + used["json"], used["tsv"], used["json"], used["file"]))
    if failures:
        print("\nFAILED (%d):" % len(failures))
        for name, why in failures:
            print("  %-44s %s" % (name, why))
        return 1
    print("design space unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
