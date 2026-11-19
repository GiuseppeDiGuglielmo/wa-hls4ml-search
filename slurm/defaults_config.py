#!/usr/bin/env python3
"""Job defaults for the Catapult sweeps: the reader of slurm/defaults.json.

Every value is a starting point that a run may override (a flag, a make
variable or an environment variable); pick per run from the facts the tools
report. Site facts are in slurm/site.json, read by slurm/site_config.py.

Runs with the system python3 (3.6) and the standard library only.

Python:
    from slurm import defaults_config as defaults   (python3 -m from the repo root)
    defaults.get("sweep", "qos"), defaults.catapult_ver()

Shell and make:
    defaults_config.py SECTION KEY       one default (sweep qos, orchestrate max_rounds, ...)
    defaults_config.py catapult-ver      Catapult install (CATAPULT_VER overrides)
    defaults_config.py catapult-product  Catapult product (CATAPULT_PRODUCT overrides)
"""

import json
import os
import sys

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "defaults.json")) as _f:
    DEFAULTS = json.load(_f)


def get(section, key):
    """One starting point; callers let each run override it."""
    return DEFAULTS[section][key]


def catapult_ver():
    """Catapult install to use: CATAPULT_VER, else the default."""
    return os.environ.get("CATAPULT_VER") or get("catapult", "version")


def catapult_product():
    """Catapult product (license) to ask for: CATAPULT_PRODUCT, else the default."""
    return os.environ.get("CATAPULT_PRODUCT") or get("catapult", "product")


def main(argv):
    if argv == ["catapult-ver"]:
        print(catapult_ver())
    elif argv == ["catapult-product"]:
        print(catapult_product())
    elif len(argv) == 2 and not argv[0].startswith("-"):
        try:
            print(get(*argv))
        except KeyError:
            sys.exit("defaults_config: no default %s %s in defaults.json" % tuple(argv))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
