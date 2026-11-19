#!/usr/bin/env python3
"""Site facts for the Catapult sweeps: the reader of slurm/site.json (paths,
account, queues, seats, node memory, tech folders) and of the license server
file it names. Choices (QOS, time, memory, slots, Catapult version) are in
slurm/defaults.json, read by slurm/defaults_config.py.

Runs with the system python3 (3.6) and the standard library only.

Python:
    from slurm import site_config as site     (run as python3 -m from the repo root)
    site.ARCHIVE, site.TECH_DIRS, site.venv(), site.licenses(), site.seats()

Shell and make:
    site_config.py get KEY          one value from site.json (account, archive, ...)
    site_config.py techs            archive tech folders, space-separated
    site_config.py venv             venv activate script (WA_HLS4ML_VENV overrides)
    site_config.py licenses         port@host[:...] (WA_LICENSES overrides)
    site_config.py seats            license seats listed in the license file
    site_config.py archive-dir TECH archive folder for a catalog tech (gf22 -> gf22fdx)
    site_config.py tech RUN_DIR     archive folder for a run, or exit 1 with the reason
    site_config.py group FOLDER     catalog group and RF of a catapult_<group>_rf<N> folder

Named site_config, not site, so it never shadows Python's own site module.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

with open(os.path.join(HERE, "site.json")) as _f:
    SITE = json.load(_f)

ARCHIVE = SITE["archive"]
TECH_MAP = {k: v for k, v in SITE["archive_tech_dirs"].items() if not k.startswith("_")}
TECH_DIRS = tuple(TECH_MAP.values())
ACCOUNT = SITE["account"]
CATAPULT_ROOT = SITE["catapult_root"]
NODE_USABLE_GB = float(SITE["node_usable_gb"])
LICENSE_FILE = os.path.join(REPO, SITE["license_file"])
CATALOG = os.path.join(HERE, "sweeps.tsv")


def venv():
    """Activate script of the Python venv; WA_HLS4ML_VENV overrides it."""
    return os.environ.get("WA_HLS4ML_VENV") or SITE["venv"]


def license_servers():
    """Server entries of the license file ([] if it is missing)."""
    try:
        with open(LICENSE_FILE) as f:
            return json.load(f).get("servers", [])
    except (IOError, OSError, ValueError):
        return []


def licenses():
    """LM_LICENSE_FILE string: WA_LICENSES if set, else every server in the file."""
    if os.environ.get("WA_LICENSES"):
        return os.environ["WA_LICENSES"]
    return ":".join("%s@%s" % (s["port"], s["host"]) for s in license_servers())


def seats():
    """License seats the license file lists. Each running Catapult holds one."""
    return sum(int(s.get("licenses", 0)) for s in license_servers())


def catalog_techs():
    """{group: catalog tech} from slurm/sweeps.tsv."""
    out = {}
    with open(CATALOG) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            cols = [c.strip() for c in line.split("\t")]
            if len(cols) > 1:
                out[cols[0]] = cols[1]
    return out


def group_of_folder(folder):
    """(catalog group, RF) for a sweep folder named catapult_<group>_rf<N>, or
    (None, None) when the name does not follow that pattern or the group is not
    in the catalog. Every sweep writes its runs under such a folder."""
    m = re.match(r"catapult_(.+)_rf(\d+)$", os.path.basename(folder.rstrip("/")))
    if m and m.group(1) in catalog_techs():
        return m.group(1), int(m.group(2))
    return None, None


def tech_of_run(run_dir):
    """(archive folder, None) for a run, or (None, reason) when the facts do not say.

    A run already in the archive under one tech folder belongs there. Otherwise a
    scratch folder named catapult_<group>_rf<N> takes its group's catalog tech.
    Nothing is guessed from substrings of the path."""
    run_dir = run_dir.rstrip("/")
    name = os.path.basename(run_dir)
    found = [t for t in TECH_DIRS if os.path.isdir(os.path.join(ARCHIVE, t, name))]
    if len(found) == 1:
        return found[0], None
    if len(found) > 1:
        return None, "%s is archived under %s" % (name, " and ".join(found))
    folder = os.path.basename(os.path.dirname(run_dir))
    group, _ = group_of_folder(folder)
    tech = catalog_techs().get(group)
    if tech in TECH_MAP:
        return TECH_MAP[tech], None
    return None, "%s is not archived and %s is not a catalog group folder" % (name, folder)


def main(argv):
    if not argv:
        sys.exit(__doc__)
    cmd, args = argv[0], argv[1:]
    if cmd == "get" and len(args) == 1:
        v = SITE[args[0]]
        print(" ".join(v) if isinstance(v, list) else v)
    elif cmd == "techs":
        print(" ".join(TECH_DIRS))
    elif cmd == "venv":
        print(venv())
    elif cmd == "licenses":
        print(licenses())
    elif cmd == "seats":
        print(seats())
    elif cmd == "archive-dir" and len(args) == 1:
        if args[0] not in TECH_MAP:
            sys.exit("site_config: unknown tech %r (known: %s)" % (args[0], ", ".join(TECH_MAP)))
        print(TECH_MAP[args[0]])
    elif cmd == "group" and len(args) == 1:
        group, rf = group_of_folder(args[0])
        if not group:
            sys.exit("site_config: %s is not catapult_<catalog group>_rf<N>" % args[0])
        print(group, rf)
    elif cmd == "tech" and len(args) == 1:
        tech, why = tech_of_run(os.path.abspath(args[0]))
        if not tech:
            sys.exit("site_config: %s; pass TECH=%s" % (why, "|".join(TECH_DIRS)))
        print(tech)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
