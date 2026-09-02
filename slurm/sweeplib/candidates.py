#!/usr/bin/env python
"""Candidate-list generators for the sampled sweep groups.

A candidates file is the frozen design list of a group, one line per design:

    stem <TAB> input <TAB> l1 <TAB> .. <TAB> lN <TAB> bitwidth <TAB> a1 <TAB> .. <TAB> aN

The files already in the shared archive are the ground truth for every sampled
run that has been synthesised, so these generators exist to (a) reproduce them
exactly, which slurm/tests/check_design_space.py asserts by sha256, and (b)
extend a campaign with new samples.

The two Latin-hypercube variants are deliberately NOT unified. `lhs_nlayer`
takes a single seed=42 draw of exactly N samples and dedups what it gets;
`lhs_sz128` reseeds in batches until it has N *new* designs, rejecting anything
that fits inside the already-synthesised <=64 cartesian. They produce different
sequences, so merging them would change the archived candidate lists.

The fourth mode, `archive_lhs`, samples the 45nm archive for re-synthesis in
GF22 and lives in slurm/examples/sample_lhs_from_archive.py, which emits
(run_name, stem) pairs rather than architectures.

Usage:
    candidates.py --group 45nm_lhs_5l --out candidates.txt
    candidates.py --group 45nm_sz128_2l --out candidates.txt
"""

import argparse
import itertools
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sweep_spec import dense_sizes, load_catalog  # noqa: E402

# The samplers' own activation order, which is NOT the cartesian generator's
# mask order (relu, tanh, sigmoid). Both are load-bearing; neither may change.
SAMPLER_ACTS = ["relu", "sigmoid", "tanh"]


def _snappers(sizes, bws, acts):
    log2_sizes = [math.log2(s) for s in sizes]
    lo_sz, hi_sz = log2_sizes[0], log2_sizes[-1]

    def snap_size(x):
        v = lo_sz + x * (hi_sz - lo_sz)
        return sizes[min(range(len(sizes)), key=lambda i: abs(log2_sizes[i] - v))]

    def snap_bw(x):
        idx = round(x * (len(bws) - 1))
        return bws[max(0, min(len(bws) - 1, idx))]

    def snap_act(x):
        idx = round(x * (len(acts) - 1))
        return acts[max(0, min(len(acts) - 1, idx))]

    return snap_size, snap_bw, snap_act


def lhs_nlayer(n_layers, sizes, bws, acts, n_lhs, seed=42):
    """One seed=42 draw of n_lhs points, deduped in first-seen order.

    Mirrors submit_45nm_nlayer_lhs.sh. Fewer than n_lhs designs come out when
    the snapping collapses samples: the archived 4-layer file holds 2,493.
    """
    from scipy.stats.qmc import LatinHypercube

    dim = 2 + 2 * n_layers
    raw = LatinHypercube(d=dim, seed=seed).random(n=n_lhs)
    snap_size, snap_bw, snap_act = _snappers(sizes, bws, acts)

    seen, ordered = set(), []
    for row in raw:
        in_sz = snap_size(row[0])
        layers = tuple(snap_size(row[1 + i]) for i in range(n_layers))
        bw = snap_bw(row[1 + n_layers])
        activations = tuple(snap_act(row[2 + n_layers + i]) for i in range(n_layers))
        key = (in_sz,) + layers + (bw,) + activations
        if key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered


def cart_sz128(n_layers, sizes, bws, acts):
    """Full cartesian product keeping only designs with a dimension of 128.

    Mirrors submit_45nm_sz128.sh's N_LAYERS<=2 branch, including its loop order:
    sizes outermost, then bitwidth, then activations.
    """
    ordered = []
    for size_combo in itertools.product(*[sizes] * (1 + n_layers)):
        if not any(s == 128 for s in size_combo):
            continue  # already covered by the <=64 cartesian sweeps
        for bw in bws:
            for activations in itertools.product(*[acts] * n_layers):
                ordered.append(size_combo + (bw,) + activations)
    return ordered


def lhs_sz128(n_layers, sizes, bws, acts, n_target, seed=42):
    """Reseeded batches until n_target designs with a dimension of 128 are found.

    Mirrors submit_45nm_sz128.sh's N_LAYERS>=3 branch.
    """
    from scipy.stats.qmc import LatinHypercube

    dim = 2 + 2 * n_layers
    snap_size, snap_bw, snap_act = _snappers(sizes, bws, acts)

    seen, ordered, batch = set(), [], 0
    while len(ordered) < n_target:
        n_raw = max((n_target - len(ordered)) * 3, 500)
        raw = LatinHypercube(d=dim, seed=seed + batch).random(n=n_raw)
        batch += 1
        for row in raw:
            in_sz = snap_size(row[0])
            layers = tuple(snap_size(row[1 + i]) for i in range(n_layers))
            bw = snap_bw(row[1 + n_layers])
            activations = tuple(snap_act(row[2 + n_layers + i]) for i in range(n_layers))
            all_sizes = (in_sz,) + layers
            if all(s <= 64 for s in all_sizes):
                continue
            key = all_sizes + (bw,) + activations
            if key not in seen:
                seen.add(key)
                ordered.append(key)
                if len(ordered) >= n_target:
                    break
    return ordered


def format_candidates(ordered, n_layers, stem_prefix):
    """Render design tuples as candidates-file lines."""
    lines = []
    for idx, cfg in enumerate(ordered):
        in_sz = cfg[0]
        layers = cfg[1:1 + n_layers]
        bw = cfg[1 + n_layers]
        activations = cfg[2 + n_layers:]
        stem = "%s_%d" % (stem_prefix % n_layers, idx)
        parts = [stem, str(in_sz)] + [str(s) for s in layers] + [str(bw)] + list(activations)
        lines.append("\t".join(parts))
    return lines


def generate(spec, n_lhs=None):
    """Produce the candidates lines for a catalog Spec."""
    n_layers = spec.n_layers
    # The samplers walk one flat size ladder, so every layer shares a range.
    ranges = set([spec.input_range] + spec.layers)
    if len(ranges) != 1:
        raise ValueError("%s: sampled groups need one shared size range, got %s"
                         % (spec.group, sorted(ranges)))
    sizes = dense_sizes(*spec.input_range)
    bws = list(spec.bitwidths)
    acts = list(spec.activations)

    if spec.mode == "lhs_nlayer":
        ordered = lhs_nlayer(n_layers, sizes, bws, acts, n_lhs or 2500)
        return format_candidates(ordered, n_layers, "dense_%dl")
    if spec.mode == "cart_sz128":
        ordered = cart_sz128(n_layers, sizes, bws, acts)
        return format_candidates(ordered, n_layers, "dense_%dl_sz128")
    if spec.mode == "lhs_sz128":
        ordered = lhs_sz128(n_layers, sizes, bws, acts, n_lhs or 2500)
        return format_candidates(ordered, n_layers, "dense_%dl_sz128")
    if spec.mode == "archive_lhs":
        raise SystemExit(
            "%s: archive_lhs candidates come from slurm/examples/sample_lhs_from_archive.py "
            "(they are (run, stem) pairs, not architectures)" % spec.group)
    raise ValueError("%s: mode %r has no candidates generator" % (spec.group, spec.mode))


def main():
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--group", required=True)
    ap.add_argument("--catalog", default=os.path.join(repo, "slurm", "sweeps.tsv"))
    ap.add_argument("--n-lhs", type=int, default=None,
                    help="LHS sample count (default 2500; ignored by cartesian modes)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    catalog = load_catalog(args.catalog)
    if args.group not in catalog:
        ap.error("group %r not in %s" % (args.group, args.catalog))

    lines = generate(catalog[args.group], n_lhs=args.n_lhs)
    out_dir = os.path.dirname(os.path.abspath(args.out))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))
    print("%s: %d designs -> %s" % (args.group, len(lines), args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
