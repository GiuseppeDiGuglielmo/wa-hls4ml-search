#!/usr/bin/env python3
"""Measure the whole archived dataset, and compare it with what the docs say.

    dataset.py summary  [--tech T] [--fast]   reports and good designs per run, by
                                              tech and catalog group (read-only)
    dataset.py provenance-diff [--fast]       runs where slurm/examples/PROVENANCE.md
                                              disagrees with the archive (read-only)
    dataset.py index [--apply]                archive runs missing from the archive
                                              README.md; --apply appends them there

"Good" is run_status.is_good (positive QoR). Counting good designs reads every
report JSON once; results are cached per run in ~/.cache/wa-hls4ml/run_counts.json,
keyed by the reports folder's file count and mtime, so later calls are fast.
--fast skips good counts (file counts only).

index --apply writes the shared archive README: it first copies it to
README.md.bak_<YYYYMMDD_HHMM> next to it, then appends one section.
"""

import argparse
import collections
import datetime
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run_status import ARCHIVE, TECH_DIRS, is_good  # noqa: E402
from list_runs import PROVENANCE, RUN_RE, provenance_groups  # noqa: E402

CACHE = os.path.join(os.path.expanduser("~"), ".cache", "wa-hls4ml", "run_counts.json")
README = os.path.join(ARCHIVE, "README.md")


def load_cache():
    try:
        with open(CACHE) as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return {}


def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    tmp = CACHE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cache, f, indent=0, sort_keys=True)
    os.rename(tmp, CACHE)


def archive_runs(tech=None):
    out = []
    for t in TECH_DIRS:
        if tech and t != tech:
            continue
        base = os.path.join(ARCHIVE, t)
        for n in sorted(os.listdir(base)):
            if RUN_RE.fullmatch(n) and os.path.isdir(os.path.join(base, n)):
                out.append((t, n, os.path.join(base, n)))
    return out


def measure(runs, fast):
    """{run: {"tech", "reports", "tarballs", "good" (None if fast)}}."""
    cache = load_cache()
    out, dirty = {}, False
    for i, (tech, name, path) in enumerate(runs):
        rep_dir, tar_dir = os.path.join(path, "reports"), os.path.join(path, "tarballs")
        reps = [n for n in os.listdir(rep_dir) if n.endswith(".json")] if os.path.isdir(rep_dir) else []
        tars = sum(1 for n in os.listdir(tar_dir) if n.endswith(".tar.gz")) if os.path.isdir(tar_dir) else 0
        key = "%s/%s" % (tech, name)
        stamp = [len(reps), os.stat(rep_dir).st_mtime if os.path.isdir(rep_dir) else 0]
        good = None
        if not fast:
            hit = cache.get(key)
            if hit and hit.get("stamp") == stamp:
                good = hit["good"]
            else:
                sys.stderr.write("  reading %d reports of %s (%d/%d)\n" % (len(reps), key, i + 1, len(runs)))
                sys.stderr.flush()
                good = sum(1 for n in reps if is_good(os.path.join(rep_dir, n)))
                cache[key] = {"stamp": stamp, "good": good}
                dirty = True
                if i % 10 == 9:  # keep progress if the scan is interrupted
                    save_cache(cache)
        out[name] = {"tech": tech, "reports": len(reps), "tarballs": tars, "good": good}
    if dirty:
        save_cache(cache)
    return out


def provenance_counts(path):
    """{run: (designs, target or None)} from the Designs column of PROVENANCE tables."""
    counts = {}
    if not os.path.isfile(path):
        return counts
    for row in open(path):
        if not row.startswith("|"):
            continue
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        runs = RUN_RE.findall(cells[2])
        nums = [int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", cells[3])]
        if not runs or not nums:
            continue
        target = nums[1] if "/" in cells[3] and len(nums) > 1 else None
        for r in runs:
            counts[r] = (nums[0], target)
    return counts


def cmd_summary(args):
    runs = archive_runs(args.tech)
    data = measure(runs, args.fast)
    groups = provenance_groups(PROVENANCE)
    fmt = "%-10s %-30s %-24s %8s %8s %8s"
    print(fmt % ("TECH", "RUN", "GROUP (PROVENANCE)", "REPORTS", "GOOD", "TARBALLS"))
    tot = collections.defaultdict(lambda: [0, 0, 0])
    for tech, name, _ in runs:
        d = data[name]
        print(fmt % (tech, name, groups.get(name, "-"), d["reports"],
                     "-" if d["good"] is None else d["good"], d["tarballs"]))
        t = tot[tech]
        t[0] += d["reports"]
        t[1] += d["good"] or 0
        t[2] += d["tarballs"]
    print()
    for tech, (r, g, tb) in sorted(tot.items()):
        print("%-10s %d runs, %d reports, %s good, %d tarballs" % (
            tech, sum(1 for x in runs if x[0] == tech), r, "-" if args.fast else g, tb))
    return 0


def cmd_provenance_diff(args):
    runs = archive_runs()
    data = measure(runs, args.fast)
    prov = provenance_counts(PROVENANCE)
    groups = provenance_groups(PROVENANCE)
    issues = 0
    print("Comparing %s with the archive (%s)" % (os.path.relpath(PROVENANCE), ARCHIVE))
    for run, (designs, target) in sorted(prov.items()):
        d = data.get(run)
        if d is None:
            print("  %-30s listed (%d designs) but not in the archive" % (run, designs))
            issues += 1
            continue
        notes = []
        if d["reports"] != designs:
            notes.append("PROVENANCE %d, archive has %d reports" % (designs, d["reports"]))
        if d["good"] is not None and d["good"] != d["reports"]:
            notes.append("%d without valid QoR" % (d["reports"] - d["good"]))
        if d["tarballs"] != d["reports"]:
            notes.append("%d tarballs vs %d reports" % (d["tarballs"], d["reports"]))
        if target and d["reports"] >= target:
            notes.append("marked partial (%d / %d) but complete" % (designs, target))
        if notes:
            print("  %-30s %-22s %s" % (run, groups.get(run, ""), "; ".join(notes)))
            issues += 1
    # Runs named only in PROVENANCE's prose notes (legacy, ghost, partial) have
    # no design count to compare, but can still lack QoR or tarballs.
    noted = [(t, n) for t, n, _ in runs if n in groups and n not in prov]
    if noted:
        print("  only in PROVENANCE notes (no design count to compare): %d run(s)" % len(noted))
        for t, n in noted:
            d = data[n]
            notes = []
            if d["good"] is not None and d["good"] != d["reports"]:
                notes.append("%d without valid QoR" % (d["reports"] - d["good"]))
            if d["tarballs"] != d["reports"]:
                notes.append("%d tarballs vs %d reports" % (d["tarballs"], d["reports"]))
            if notes:
                print("    %-30s %s" % (n, "; ".join(notes)))
                issues += 1
    unlisted = [(t, n) for t, n, _ in runs if n not in groups]
    if unlisted:
        print("  in the archive, not in PROVENANCE: %d run(s)" % len(unlisted))
        for t, n in unlisted:
            print("    %s/%s  %d reports" % (t, n, data[n]["reports"]))
        issues += len(unlisted)
    print("%d difference(s)." % issues if issues else "No differences.")
    return 0


def cmd_index(args):
    text = open(README).read()
    mentioned = set(RUN_RE.findall(text))
    runs = [(t, n, p) for t, n, p in archive_runs() if n not in mentioned]
    print("Archive README: %s" % README)
    if not runs:
        print("Every archive run is mentioned.")
        return 0
    data = measure(runs, False)
    groups = provenance_groups(PROVENANCE)
    lines = ["", "## Runs not yet described (listed by make archive-index, %s)" % datetime.date.today(),
             "", "Counts measured from the run folders; good = positive QoR in the report.", "",
             "| Tech | Run directory | Catalog group (PROVENANCE.md) | Designs | Good |",
             "|---|---|---|---|---|"]
    for t, n, _ in runs:
        d = data[n]
        lines.append("| %s | `%s` | %s | %d | %d |" % (t, n, groups.get(n, "-"), d["reports"], d["good"]))
    section = "\n".join(lines) + "\n"
    print("%d run(s) not mentioned. Section to append:" % len(runs))
    print(section)
    if not args.apply:
        print("Dry run: README not changed. APPLY=1 appends this after a backup copy.")
        return 0
    backup = README + ".bak_" + datetime.datetime.now().strftime("%Y%m%d_%H%M")
    shutil.copy2(README, backup)
    with open(README, "a") as f:
        f.write(section)
    print("Appended. Backup: %s" % backup)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("summary")
    s.add_argument("--tech", choices=TECH_DIRS)
    s.add_argument("--fast", action="store_true")
    p = sub.add_parser("provenance-diff")
    p.add_argument("--fast", action="store_true")
    i = sub.add_parser("index")
    i.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if not args.cmd:
        ap.error("choose summary, provenance-diff or index")
    return {"summary": cmd_summary, "provenance-diff": cmd_provenance_diff, "index": cmd_index}[args.cmd](args)


if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped to head
    sys.exit(main())
