#!/usr/bin/env python3
"""Read-only checks that the Catapult tool chain on Perlmutter is usable.

    catapult_env.py env       venv, container, Apptainer, Catapult install, env
                              script, license file, GNU parallel, launcher dry run
    catapult_env.py license   reachability of every license server we know of,
                              and their features if an lmutil binary is given

Each check prints OK, WARN or FAIL; the exit status is 1 if any check failed.
Nothing is written and no license is checked out. Whether a server actually
grants Catapult's feature is only known by starting Catapult once:
`make catapult-probe PROBE=1`.
"""

import argparse
import glob
import json
import os
import re
import socket
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOME = os.path.expanduser("~")
SCRATCH = os.environ.get("SCRATCH", "")
CATAPULT_ROOT = "/global/common/software/amsc011/public/Siemens/Catapult"
PURGE_DAYS = 56          # Perlmutter scratch: files unread for 8 weeks may be purged
LICENSE_JSON = os.path.join(REPO, "license_servers_perlmutter.json")
SERVER_RE = re.compile(r"\b(\d+)@([A-Za-z0-9.\-]+)")

failed = []


def report(status, what, detail=""):
    print("%-4s  %-22s %s" % (status, what, detail))
    if status == "FAIL":
        failed.append(what)


def run(cmd, timeout=60, **kw):
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           universal_newlines=True, timeout=timeout, **kw)
        return p.returncode, p.stdout
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, str(e)


def env_script():
    if os.environ.get("CAD_ENV_SCRIPT"):
        return os.environ["CAD_ENV_SCRIPT"]
    new, old = os.path.join(HOME, "bin", "cad_env_perlmutter.sh"), os.path.join(HOME, "bin", "siemens.sh")
    return new if os.path.isfile(new) or not os.path.isfile(old) else old


def json_servers():
    try:
        with open(LICENSE_JSON) as f:
            return ["%s@%s" % (s["port"], s["host"]) for s in json.load(f)["servers"]]
    except (IOError, OSError, ValueError, KeyError):
        return []


def script_servers(path):
    """port@host entries on non-comment lines of the env script."""
    found = []
    try:
        with open(path) as f:
            for line in f:
                if line.lstrip().startswith("#"):
                    continue
                found += ["%s@%s" % m for m in SERVER_RE.findall(line) if m[1] != "localhost"]
    except (IOError, OSError):
        pass
    return found


def tree_damage(root):
    """(files, dangling links, .py files, .pyc files) under root, not following links."""
    files = dangling = py = pyc = 0
    for d, dirs, names in os.walk(root):
        for n in names + [x for x in dirs if os.path.islink(os.path.join(d, x))]:
            p = os.path.join(d, n)
            if os.path.islink(p):
                if not os.path.exists(p):
                    dangling += 1
            else:
                files += 1
                py += n.endswith(".py")
                pyc += n.endswith(".pyc")
    return files, dangling, py, pyc


def check_install(inst, used):
    """Report one Catapult install: present, not purged, how recently read."""
    tag = "catapult %s%s" % (os.path.basename(inst), " (used)" if used else "")
    exe = os.path.join(inst, "Mgc_home", "bin", "catapult")
    if not os.path.isfile(exe):
        report("FAIL", tag, "%s not found" % exe)
        return
    files, dangling, _, _ = tree_damage(os.path.join(inst, "Mgc_home"))
    if dangling > files or files < 5000:
        report("FAIL", tag, "%d files, %d dangling links under Mgc_home: the install looks"
               " purged; reinstall it, outside $SCRATCH if possible" % (files, dangling))
        return
    days = (time.time() - os.stat(exe).st_atime) / 86400.0
    detail = "%s: %d files, %d dangling links, catapult last read %.0f days ago" % (inst, files, dangling, days)
    if inst.startswith("/pscratch/"):
        detail += "; on scratch, purged after %d days unread" % PURGE_DAYS
        if days > PURGE_DAYS - 14:
            report("WARN", tag, detail)
            return
    report("OK", tag, detail)


def json_seats():
    """License seats listed in the license file; sweeps run at most this many designs at once."""
    try:
        with open(LICENSE_JSON) as f:
            return sum(int(s.get("licenses", 0)) for s in json.load(f)["servers"])
    except (OSError, ValueError, KeyError):
        return 0


PRODUCT_FEATURE = {"ultra": "CatapultUltra_c", "genesis": "Genesis"}


def check_env():
    venv = os.environ.get("WA_HLS4ML_VENV", "/global/common/software/amsc011/public/venv_hls4ml/bin/activate")
    py = os.path.join(os.path.dirname(venv), "python")
    if not os.path.isfile(venv):
        report("FAIL", "venv", "%s not found" % venv)
    else:
        site = glob.glob(os.path.join(os.path.dirname(os.path.dirname(venv)), "lib", "python*", "site-packages"))
        if site:
            _, _, py_n, pyc_n = tree_damage(site[0])
            if pyc_n > 5 * max(py_n, 1):
                report("FAIL", "venv files", "%d .py vs %d .pyc in %s: sources look purged from scratch;"
                       " rebuild the venv (outside $SCRATCH if possible)" % (py_n, pyc_n, site[0]))
            else:
                report("OK", "venv files", "%d .py, %d .pyc" % (py_n, pyc_n))
        t0 = time.time()
        rc, out = run([py, "-c", "import tensorflow, qkeras, hls4ml; print('imports ok')"], timeout=300)
        if rc == 0:
            report("OK", "venv", "%s (tensorflow, qkeras, hls4ml import in %.0fs)" % (venv, time.time() - t0))
        else:
            last = [l for l in (out or "").splitlines() if l.strip()][-1:] or ["timed out"]
            report("FAIL", "venv", "imports fail: %s" % last[0][:120])

    sif = os.path.join(HOME, "work", "tool-containers", "catapult_rocky.sif")
    if os.path.isfile(sif):
        report("OK", "container", "%s -> %s" % (sif, os.path.realpath(sif)))
    else:
        report("FAIL", "container", "%s not found (or dangling link)" % sif)

    app = None
    for cand in (subprocess.run(["bash", "-c", "command -v apptainer"], stdout=subprocess.PIPE,
                                universal_newlines=True).stdout.strip(),
                 "/cvmfs/oasis.opensciencegrid.org/mis/apptainer/current/bin/apptainer"):
        if cand and os.access(cand, os.X_OK):
            app = cand
            break
    report("OK" if app else "FAIL", "apptainer", app or "not on PATH or CVMFS (try module load apptainer)")

    ver = os.environ.get("CATAPULT_VER", "2026.1_1")
    if os.environ.get("CATAPULT_PATH_OVERRIDE"):
        installs = [os.environ["CATAPULT_PATH_OVERRIDE"]]
    else:
        root = os.environ.get("CATAPULT_ROOT", CATAPULT_ROOT)
        installs = sorted(d for d in glob.glob(os.path.join(root, "*")) if os.path.isdir(os.path.join(d, "Mgc_home")))
        if os.path.join(root, ver) not in installs:
            installs.append(os.path.join(root, ver))   # reported as missing
    for inst in installs:
        check_install(inst, os.path.basename(inst) == ver or len(installs) == 1)
    if not os.environ.get("CATAPULT_PATH_OVERRIDE"):
        report("OK", "catapult version", "CATAPULT_VER=%s is used (set CATAPULT_VER to pick another)" % ver)

    script = env_script()
    report("OK" if os.path.isfile(script) else "FAIL", "env script", script)

    servers = json_servers()
    report("OK" if servers else "FAIL", "license file",
           "%s: %s" % (LICENSE_JSON, ", ".join(servers) or "missing or no servers"))
    report("OK", "product", "%s (CATAPULT_PRODUCT=ultra|genesis), %d license seat(s) in the file"
           % (os.environ.get("CATAPULT_PRODUCT", "ultra"), json_seats()))

    rc, out = run(["parallel", "--version"])
    if rc != 0:
        report("FAIL", "GNU parallel", "not found")
    else:
        rc2, _ = run(["parallel", "--memfree", "1M", "true", ":::", "x"])
        report("OK" if rc2 == 0 else "WARN", "GNU parallel",
               out.splitlines()[0] + ("" if rc2 == 0 else " (--memfree not accepted)"))

    rc, out = run(["bash", os.path.join(REPO, "Perlmutter_scripts", "catapult_shell.sh"),
                   "--dry-run", "--work-dir", REPO])
    report("OK" if rc == 0 else "FAIL", "launcher dry run",
           "ok" if rc == 0 else (out or "").strip().splitlines()[0][:120])


def check_license(lmutil):
    script = env_script()
    sources = {}
    for s in json_servers():
        sources.setdefault(s, []).append("license_servers_perlmutter.json")
    for s in script_servers(script):
        sources.setdefault(s, []).append(os.path.basename(script))
    if not sources:
        report("FAIL", "license servers", "none in %s or %s" % (LICENSE_JSON, script))
        return
    for srv, where in sorted(sources.items()):
        port, host = srv.split("@", 1)
        t0 = time.time()
        try:
            socket.create_connection((host, int(port)), timeout=5).close()
            report("OK", srv, "reachable in %.2fs (from %s)" % (time.time() - t0, ", ".join(where)))
        except (OSError, socket.timeout) as e:
            report("FAIL", srv, "not reachable: %s (from %s)" % (e, ", ".join(where)))
            continue
        if lmutil:
            rc, out = run([lmutil, "lmstat", "-a", "-c", srv], timeout=120)
            users = [l.strip() for l in (out or "").splitlines()
                     if re.match(r"Users of (cat|\S*genesis)", l, re.I)]
            if rc != 0 and not users:
                report("WARN", "  lmstat", ((out or "").strip().splitlines() or ["no output"])[-1][:120])
            for l in users:
                print("      %s" % l)
            prod = os.environ.get("CATAPULT_PRODUCT", "ultra")
            need = PRODUCT_FEATURE.get(prod, prod)
            hit = [l for l in users if need.lower() in l.lower()]
            m = re.search(r"Total of (\d+) licenses? issued;\s*Total of (\d+)", hit[0]) if hit else None
            if m:
                report("OK", "  product", "%s needs %s: %s issued, %s in use" % (prod, need, m.group(1), m.group(2)))
            else:
                report("WARN" if not hit else "OK", "  product",
                       "%s needs %s: %s" % (prod, need, "not on this server" if not hit else hit[0][:80]))
    if lmutil:
        print("note: features from %s lmstat. 'unsupported by licensed server' means FlexLM cannot"
              " count a feature; make catapult-probe PROBE=1 tests a real checkout." % os.path.basename(lmutil))
    else:
        print("note: no lmutil found; pass LMUTIL=<path> to list features.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=("env", "license"))
    ap.add_argument("--lmutil", default=os.environ.get("LMUTIL") or None,
                    help="path to a FlexNet lmutil binary, to list server features")
    args = ap.parse_args()
    if args.what == "env":
        check_env()
    else:
        if args.lmutil and not os.access(args.lmutil, os.X_OK):
            sys.exit("catapult_env: lmutil %s is not executable" % args.lmutil)
        lmutil = args.lmutil
        if not lmutil:   # the lmutil of the install the launcher would use
            inst = os.environ.get("CATAPULT_PATH_OVERRIDE") or os.path.join(
                os.environ.get("CATAPULT_ROOT", CATAPULT_ROOT), os.environ.get("CATAPULT_VER", "2026.1_1"))
            cand = os.path.join(inst, "Mgc_home", "bin", "lmutil")
            lmutil = cand if os.access(cand, os.X_OK) else None
        check_license(lmutil)
    if failed:
        print("\n%d check(s) failed: %s" % (len(failed), ", ".join(failed)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
