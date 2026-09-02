#!/usr/bin/env python3
"""Equivalence oracle for the sweep-catalog migration.

Prints the ordered design list of a cartesian sweep group, one line per design:

    stem <TAB> input <TAB> l1,l2,..,lN <TAB> bitwidth <TAB> act1,act2,..,actN

The enumeration is a faithful copy of gen_models.cartesian_exec()'s general
mode (gen_models.py:512) with the Keras model building removed, so it runs in
seconds over a 405k-design space. Because the stem `dense_{N}l_{idx}` is just
the index into that product, an identical sha256 over this listing proves that
every archived stem still denotes exactly the same circuit.

Usage:
    enumerate_space.py --from-json configs/model_sweeps/config_dense_3layers.json
    enumerate_space.py --from-tsv 3l_base [--catalog slurm/sweeps.tsv]
    enumerate_space.py --from-json ... --digest      # count + sha256 only
"""

import argparse
import hashlib
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sweep_spec import Spec, dense_sizes, load_catalog, spec_from_json  # noqa: E402


def enumerate_designs(spec: Spec):
    """Yield (stem, input_size, layer_sizes, bitwidth, activations) in gen_models order."""
    input_sizes = dense_sizes(*spec.input_range)
    layer_options = [
        list(itertools.product(dense_sizes(lb, ub), spec.activations))
        for lb, ub in spec.layers
    ]
    n_layers = len(spec.layers)

    for idx, combo in enumerate(
        itertools.product(input_sizes, *layer_options, spec.bitwidths)
    ):
        in_size = combo[0]
        layer_configs = combo[1:-1]
        bitwidth = combo[-1]
        yield (
            f"dense_{n_layers}l_{idx}",
            in_size,
            [s for s, _ in layer_configs],
            bitwidth,
            [a for _, a in layer_configs],
        )


def format_line(stem, in_size, sizes, bitwidth, acts) -> str:
    return "\t".join(
        [
            stem,
            str(in_size),
            ",".join(str(s) for s in sizes),
            str(bitwidth),
            ",".join(acts),
        ]
    )


def digest(spec: Spec):
    """Return (design_count, sha256) over the formatted listing."""
    h = hashlib.sha256()
    count = 0
    for design in enumerate_designs(spec):
        h.update(format_line(*design).encode())
        h.update(b"\n")
        count += 1
    return count, h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-json", metavar="PATH", help="legacy model-sweep JSON")
    src.add_argument("--from-tsv", metavar="GROUP", help="group name in the sweep catalog")
    ap.add_argument("--catalog", default="slurm/sweeps.tsv", help="catalog path for --from-tsv")
    ap.add_argument("--digest", action="store_true", help="print '<count> <sha256>' only")
    args = ap.parse_args()

    if args.from_json:
        spec = spec_from_json(args.from_json)
    else:
        catalog = load_catalog(args.catalog)
        if args.from_tsv not in catalog:
            ap.error(f"group '{args.from_tsv}' not in {args.catalog}")
        spec = catalog[args.from_tsv]

    if args.digest:
        count, sha = digest(spec)
        print(f"{count}\t{sha}")
        return 0

    out = sys.stdout
    for design in enumerate_designs(spec):
        out.write(format_line(*design) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
