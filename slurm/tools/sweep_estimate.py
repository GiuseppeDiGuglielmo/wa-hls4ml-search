#!/usr/bin/env python3
"""Rough cost of a sweep group before running it, read-only.

    sweep_estimate.py <group> [--rf 1,4] [--nodes 1] [--licenses N] [--sample 300]

Design count comes from the catalog (slurm/sweeps.tsv): enumerated for cartesian
groups, the candidates file or generator for the sampled ones. Runtime and peak
Catapult memory come from past runs of the same group that are still on
scratch (GNU parallel joblogs, messages.txt of up to --sample designs per run).

Prints per RF: designs, past p50/p90 runtime and p90/max peak memory, the slots
per node that fit both the p90 memory in a node's ~460 GB and the license seats
(default: the seats in license_servers_perlmutter.json, as sweep.sh uses), and
node-hours. With no
past run on scratch it says so; numbers from another RF of the group are used
when the same RF has none (marked). These are estimates, not promises.
"""

import argparse
import glob
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
from slurm import defaults_config as defaults  # noqa: E402
from slurm.tools.list_runs import PROVENANCE, collect, provenance_groups  # noqa: E402
from slurm.tools.design_show import attempts, attempt_facts  # noqa: E402

from slurm import site_config as site  # noqa: E402
NODE_GB = site.NODE_USABLE_GB   # usable per CPU node (slurm/site.json)
SLOTS_MAX = defaults.get("sweep", "slots_per_node_max")  # sweep.sh's default cap per node


def license_seats():
    """Seats in license_servers_perlmutter.json, the same count sweep.sh caps at."""
    return site.seats()


def design_count(group):
    from slurm.sweeplib.sweep_spec import load_catalog
    spec = load_catalog(os.path.join(REPO, "slurm", "sweeps.tsv"))[group]
    mode = getattr(spec, "mode", "cartesian")
    if mode == "cartesian":
        from enumerate_space import enumerate_designs
        return sum(1 for _ in enumerate_designs(spec)), mode, list(spec.rf)
    cand = getattr(spec, "candidates", None)
    if cand:
        path = os.path.join(site.ARCHIVE, cand)
        if os.path.isfile(path):
            return sum(1 for l in open(path) if l.strip() and not l.startswith("#")), mode, list(spec.rf)
    try:
        from candidates import generate
        return len(list(generate(spec))), mode, list(spec.rf)
    except Exception as e:  # sampled modes may need --n-lhs
        return None, "%s (%s)" % (mode, e.__class__.__name__), list(spec.rf)


def pct(values, q):
    v = sorted(values)
    return v[min(len(v) - 1, int(len(v) * q / 100.0))] if v else None


def past_stats(run_dir, sample):
    runtimes = []
    for log in glob.glob(os.path.join(run_dir, "parallel_*.log")):
        for line in open(log, errors="replace"):
            c = line.split("\t")
            if len(c) > 7 and c[6] == "0":
                try:
                    runtimes.append(float(c[3]) / 60.0)
                except ValueError:
                    pass
    builds = sorted(os.listdir(os.path.join(run_dir, "build"))) if os.path.isdir(os.path.join(run_dir, "build")) else []
    peaks = []
    for stem in random.Random(1).sample(builds, min(sample, len(builds))):
        tries = attempts(os.path.join(run_dir, "build", stem, "catapult_native"))
        qor = [p for _, p in tries if attempt_facts(p)[2]]
        if qor:
            peak = attempt_facts(qor[-1])[1]
            if peak:
                peaks.append(peak)
    return runtimes, peaks


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("group")
    ap.add_argument("--rf", help="comma list (default: the row's rf)")
    ap.add_argument("--nodes", type=int, default=1)
    ap.add_argument("--licenses", type=int, default=None,
                    help="license seats (default: license_servers_perlmutter.json)")
    ap.add_argument("--sample", type=int, default=300, help="designs per past run read for peak memory")
    args = ap.parse_args()
    if args.licenses is None:
        args.licenses = license_seats()

    try:
        n, mode, rfs = design_count(args.group)
    except KeyError:
        sys.exit("sweep_estimate: unknown group %s (see slurm/sweeps.tsv)" % args.group)
    if args.rf:
        rfs = [int(x) for x in args.rf.split(",")]
    print("Group    %s  mode %s  designs per RF: %s" % (args.group, mode, n if n is not None else "unknown"))

    groups = provenance_groups(PROVENANCE)
    scratch = collect()
    past = {}
    for run, e in scratch.items():
        g = groups.get(run, "")
        m = re.match(r"(\S+) rf(\d+)$", g)
        if e.get("scratch") and m and m.group(1) == args.group:
            dirs = glob.glob(os.path.join(os.environ.get("SCRATCH", ""), "catapult_*", run))
            if dirs:
                past.setdefault(int(m.group(2)), []).append(dirs[0])
    if not past:
        print("Past     no run of this group on scratch; runtime and memory unknown"
              " (the archive keeps no joblogs)")

    stats = {}
    for rf, dirs in sorted(past.items()):
        rt, pk = [], []
        for d in dirs:
            a, b = past_stats(d, args.sample)
            rt += a
            pk += b
        stats[rf] = (rt, pk, dirs)

    print("%-4s %-9s %-19s %-19s %-11s %-11s %s" % ("RF", "designs", "runtime p50/p90", "peak mem p90/max",
                                                    "slots/node", "node-hours", "wall (nodes)"))
    for rf in rfs:
        src, mark = (rf, "") if rf in stats else ((min(stats, key=lambda r: abs(r - rf)), "*") if stats else (None, ""))
        if src is None:
            print("%-4s %-9s %s" % (rf, n if n is not None else "?", "no past data"))
            continue
        rt, pk, _ = stats[src]
        p50, p90 = pct(rt, 50), pct(rt, 90)
        m90, mmax = pct(pk, 90), (max(pk) if pk else None)
        cap = min(SLOTS_MAX, args.licenses // args.nodes)
        slots = int(min(cap, NODE_GB // m90)) if m90 else cap
        mean = sum(rt) / len(rt) if rt else None
        node_h = (n * mean / 60.0 / slots) if (n and mean) else None
        print("%-4s %-9s %-19s %-19s %-11s %-11s %s" % (
            "%d%s" % (rf, mark), n if n is not None else "?",
            "%.0f / %.0f min" % (p50, p90) if rt else "-",
            "%.1f / %.1f GB" % (m90, mmax) if pk else "-",
            slots, "%.0f" % node_h if node_h else "-",
            "%.1f h (%d)" % (node_h / args.nodes, args.nodes) if node_h else "-"))
    if any(rf not in stats for rf in rfs) and stats:
        print("* no past run at this RF; numbers from the nearest RF on scratch")
    for rf, (_, _, dirs) in sorted(stats.items()):
        print("Past rf%-3d %s" % (rf, ", ".join(dirs)))
    print("Runtime is per design as GNU parallel saw it (in-process retries included);"
          " node-hours = designs x mean runtime / slots.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
