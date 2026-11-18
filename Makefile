# Targets for the Catapult sweeps, grouped bottom-up: tool chain, one design,
# one run, archive, whole dataset, planning. The same commands back the agent
# skills in .claude/skills/ (run-catapult, check-runs, archive-run, dataset), so
# a person running `make` and an agent get the same answer.
#
# Read-only unless marked. Marked targets do nothing without their flag:
#   PROBE=1   catapult-probe takes one license for a few seconds
#   SUBMIT=1  design-synth, rerun-failed submit jobs (sweep always submits)
#   APPLY=1   reparse, archive-index, scratch-clean write or delete
# archive copies into the shared archive; run archive-dry first.
# scratch-clean is the only target that deletes, and only after archive-verify.

SHELL := /bin/bash
PYTHON ?= python3
# NERSC's Python (3.7+), for tools that import the sweep catalog or the pipeline.
NERSC_PY ?= /global/common/software/nersc/pe/conda-envs/latest/python-3.13/nersc-python/bin/python
RUN      ?=
STEM     ?=
EXPECTED ?=
TECH     ?=
WHERE    ?=
GREP     ?=
ACCOUNT  ?= amsc011
EXPRESS_QOS := express_amsc express_amsc_g
GROUP    ?=
RF       ?=
QOS      ?=
TIME     ?=
NODES    ?=
PARALLELISM ?=
MEM      ?=
MEMFREE  ?=
PROBE    ?=
SUBMIT   ?=
APPLY    ?=
FAST     ?=
ALL      ?=
WORKERS  ?= 8
LMUTIL   ?=
PROBE_DIR = $(SCRATCH)/catapult_probe
SWEEP_OPTS = $(if $(RF),--rf $(RF)) $(if $(QOS),--qos $(QOS)) $(if $(TIME),--time $(TIME)) \
             $(if $(NODES),--nodes $(NODES)) $(if $(PARALLELISM),--parallelism $(PARALLELISM)) \
             $(if $(MEM),--mem $(MEM)) $(if $(MEMFREE),--memfree $(MEMFREE))
JOB_OPTS = $(if $(QOS),--qos $(QOS)) $(if $(TIME),--time $(TIME)) $(if $(MEM),--mem $(MEM))
# Same license string sweep.sh builds from license_servers_perlmutter.json.
LICENSES = $$(python3 -c "import json; c=json.load(open('license_servers_perlmutter.json')); print(':'.join('%s@%s' % (s['port'], s['host']) for s in c['servers']))")
# The venv prints a harmless distutils-precedence.pth traceback on each python3 call.
VENV_NOISE = -e distutils -e add_shim -e 'site.py' -e 'exec(line)' -e 'File "<string>"' -e '^ *Traceback' -e 'Remainder of file' -e '^ *$$'
need_run  = @test -n "$(RUN)" || { echo 'usage: make $@ RUN=<scratch run_dir>$(1)'; exit 2; }

.PHONY: help env-check license-check catapult-probe \
        design-show design-synth \
        check-jobs check-list check-run check-failed why-failed reparse rerun-failed sweep-check sweep \
        archive-dry archive archive-verify scratch-clean archive-index \
        dataset-summary provenance-diff sweep-estimate

# help: each target's '## target | args | kind | skill | description' line,
# grouped by the agent skill that uses it (.claude/skills/README.md).
help:
	@echo 'Catapult sweeps on Perlmutter. Usage: make <target> [ARG=value ...]'
	@echo 'Unmarked targets only read.  flag: acts only with PROBE=1, SUBMIT=1 or APPLY=1.  acts: acts every time.'
	@awk -F' [|] ' '/^## [a-z-]+ [|]/ { sub(/^## /, "", $$1); \
	    row[$$1] = sprintf("  %-16s %-22s %-5s %s", $$1, $$2, ($$3 == "read" ? "" : $$3), $$5) } \
	  END { n = split("run-catapult:tool chain, sweeps, repairs:env-check license-check catapult-probe sweep-estimate sweep-check sweep reparse rerun-failed design-synth;" \
	                  "check-runs:status and failures:check-jobs check-list check-run check-failed why-failed design-show;" \
	                  "archive-run:archive and scratch:archive-dry archive archive-verify scratch-clean archive-index;" \
	                  "dataset:the archived dataset:dataset-summary provenance-diff", grp, ";"); \
	    for (i = 1; i <= n; i++) { split(grp[i], f, ":"); printf "\n%s: %s\n", f[1], f[2]; \
	      m = split(f[3], t, " "); for (k = 1; k <= m; k++) print (t[k] in row ? row[t[k]] : "  " t[k] "  (no help line)") } }' $(MAKEFILE_LIST)
	@echo
	@echo 'sweep opts: RF= QOS= TIME= NODES= PARALLELISM= MEM= MEMFREE='
	@echo 'rerun-failed and design-synth also take QOS= TIME= MEM=.  TECH=nangate45|gf22fdx'
	@echo 'RUN= is a scratch run folder; check-run and design-show also take a run name.'
	@echo 'More: .claude/skills/README.md'

# --- Tool chain: does Catapult work here? ---

## env-check |  | read | run-catapult | Check venv, container, Catapult install and licenses
env-check:
	@$(PYTHON) slurm/examples/catapult_env.py env

## license-check | [LMUTIL=] | read | run-catapult | Check each license server answers
license-check:
	@$(PYTHON) slurm/examples/catapult_env.py license $(if $(LMUTIL),--lmutil $(LMUTIL))

## catapult-probe | [PROBE=1] | flag | run-catapult | Launcher dry run; PROBE=1 starts Catapult once (1 license)
catapult-probe:
	@mkdir -p $(PROBE_DIR)
	@if [ -n "$(PROBE)" ]; then \
	  LM_LICENSE_FILE=$(LICENSES) bash Perlmutter_scripts/catapult_shell.sh --work-dir $(PROBE_DIR) \
	    --cmd 'puts "catapult-probe: OK in [pwd]"; exit' 2>&1 | grep -E 'catapult-probe: OK|rror' \
	    || { echo 'catapult-probe: no OK line; run the launcher by hand to see its output'; exit 1; }; \
	else \
	  bash Perlmutter_scripts/catapult_shell.sh --dry-run --work-dir $(PROBE_DIR) | tr ' ' '\n' | grep -E 'apptainer$$|\.sif$$|cad_env|siemens\.sh'; \
	  echo "(dry run; PROBE=1 starts Catapult once to check the license)"; \
	fi

# --- One design ---

## design-show | RUN= STEM= | read | check-runs | One design's report and every Catapult attempt
design-show:
	@test -n "$(RUN)" -a -n "$(STEM)" || { echo 'usage: make design-show RUN=<run_dir or run name> STEM=<stem>'; exit 2; }
	@$(PYTHON) slurm/examples/design_show.py $(RUN) $(STEM)

## design-synth | RUN= STEM= [SUBMIT=1] | flag | run-catapult | Rerun one design in $SCRATCH/catapult_debug
design-synth:
	@test -n "$(RUN)" -a -n "$(STEM)" || { echo 'usage: make design-synth RUN=<scratch run_dir> STEM=<stem> [SUBMIT=1]'; exit 2; }
	@$(PYTHON) slurm/examples/design_synth.py $(RUN) $(STEM) $(JOB_OPTS) $(if $(SUBMIT),--submit)

# --- One run (a group at one RF) ---

## check-jobs | [ACCOUNT=] | read | check-runs | Your jobs and the express node pools
check-jobs:
	@squeue -u $$USER -o '%.10i %.12P %.14q %.24j %.2t %.10M %.6D %R'
	@for q in $(EXPRESS_QOS); do \
	  echo; \
	  scontrol show assoc_mgr flags=qos qos=$$q \
	    | grep -o -m1 'node=32([0-9]*)' \
	    | sed -E "s/node=32\(([0-9]+)\)/$$q pool: \1 of 32 nodes in use (all AmSC + Genesis users)/"; \
	  squeue -h -q $$q -t R -o '%a %u %D' \
	    | awk -v me='$(ACCOUNT)' ' \
	        { n[$$1] += $$3; if (index("," u[$$1] ",", "," $$2 ",") == 0) u[$$1] = u[$$1] (u[$$1] == "" ? "" : ",") $$2 } \
	        END { if (!(me in n)) n[me] = 0; \
	              for (a in n) printf "  %-12s %3d nodes  %s%s\n", a, n[a], (u[a] == "" ? "-" : "(" u[a] ")"), (a == me ? "  <- your account" : "") }' \
	    | sort -k2,2nr -k1,1; \
	done

## check-list | [TECH= WHERE= GREP=] | read | check-runs | Every run on scratch and in the archive
check-list:
	@$(PYTHON) slurm/examples/list_runs.py $(if $(TECH),--tech $(TECH)) $(if $(WHERE),--where $(WHERE)) $(if $(GREP),--grep "$(GREP)")

## check-run | RUN= | read | check-runs | Expected, good, failed and missing designs of a run
check-run:
	@test -n "$(RUN)" || { echo 'usage: make check-run RUN=<run_dir, catapult_* folder, or run name>'; exit 2; }
	@$(PYTHON) slurm/examples/run_status.py $(RUN) $(if $(EXPECTED),--expected $(EXPECTED))

## check-failed | RUN= | read | check-runs | Missing reports and tarballs, reports without QoR
check-failed:
	@test -n "$(RUN)" || { echo 'usage: make check-failed RUN=<run_dir>'; exit 2; }
	@test -d "$(RUN)/build" || { echo 'check-failed: $(RUN) is not a scratch run directory (needs build/); for archive-only runs use make check-run'; exit 2; }
	@bash slurm/examples/check_failures.sh $(RUN)

## why-failed | RUN= [FAST=1] | read | check-runs | Why designs failed: exit codes, OOM kills, time limits
why-failed:
	$(call need_run,)
	@$(PYTHON) slurm/examples/why_failed.py $(RUN) $(if $(FAST),--no-memory)

## reparse | RUN= [APPLY=1] | flag | run-catapult | Fix reports whose QoR is in a retry folder
reparse:
	$(call need_run, [APPLY=1])
	@set -o pipefail; $(NERSC_PY) slurm/examples/reparse.py $(RUN) $(if $(APPLY),--apply --workers $(WORKERS)) 2>&1 | { grep -v ' - INFO - ' || true; }

## rerun-failed | RUN= [SUBMIT=1] | flag | run-catapult | Resubmit designs with no QoR anywhere
rerun-failed:
	$(call need_run, [SUBMIT=1])
	@$(PYTHON) slurm/examples/rerun_failed.py $(RUN) $(JOB_OPTS) $(if $(PARALLELISM),--parallelism $(PARALLELISM)) $(if $(MEMFREE),--memfree $(MEMFREE)) $(if $(SUBMIT),--submit)

## sweep-check | GROUP= [sweep opts] | read | run-catapult | Sweep plan and sbatch --test-only; submits nothing
sweep-check:
	@test -n "$(GROUP)" || { echo 'usage: make sweep-check GROUP=<group from slurm/sweeps.tsv> [RF=1,4 ...]'; exit 2; }
	@bash slurm/sweep.sh $(GROUP) $(SWEEP_OPTS) --check 2>&1 | grep -v $(VENV_NOISE)
	@mkdir -p logs; echo "Sweep driver job:"; sbatch --test-only slurm/sweep.sh $(GROUP) $(SWEEP_OPTS) 2>&1 | sed 's/^/  /'

## sweep | GROUP= [sweep opts] | acts | run-catapult | Submit a sweep (nodes, licenses); run sweep-check first
sweep:
	@test -n "$(GROUP)" || { echo 'usage: make sweep GROUP=<group> [RF=...]  (run make sweep-check first)'; exit 2; }
	@mkdir -p logs; sbatch slurm/sweep.sh $(GROUP) $(SWEEP_OPTS)

# --- Archive ---

## archive-dry | RUN= | read | archive-run | What archive would copy
archive-dry:
	$(call need_run,)
	@$(PYTHON) slurm/examples/archive_sync.py $(RUN) $(if $(TECH),--tech $(TECH))

## archive | RUN= | acts | archive-run | Copy a run into the shared archive; never deletes
archive:
	$(call need_run,  (run make archive-dry first))
	@$(PYTHON) slurm/examples/archive_sync.py $(RUN) $(if $(TECH),--tech $(TECH)) --apply

## archive-verify | RUN= [ALL=1] | read | archive-run | Check the archive holds everything of a run
archive-verify:
	$(call need_run,)
	@$(PYTHON) slurm/examples/archive_verify.py $(RUN) $(if $(TECH),--tech $(TECH)) $(if $(ALL),--all)

## scratch-clean | RUN= [APPLY=1] | flag | archive-run | Delete a scratch run once verified
scratch-clean:
	$(call need_run, [APPLY=1])
	@$(PYTHON) slurm/examples/scratch_clean.py $(RUN) $(if $(TECH),--tech $(TECH)) $(if $(APPLY),--apply)

## archive-index | [APPLY=1] | flag | archive-run | Runs missing from the archive README
archive-index:
	@$(PYTHON) slurm/examples/dataset.py index $(if $(APPLY),--apply)

# --- Whole dataset ---

## dataset-summary | [TECH= FAST=1] | read | dataset | Reports and good designs per run and tech
dataset-summary:
	@$(PYTHON) slurm/examples/dataset.py summary $(if $(TECH),--tech $(TECH)) $(if $(FAST),--fast)

## provenance-diff | [FAST=1] | read | dataset | Where PROVENANCE.md disagrees with the archive
provenance-diff:
	@$(PYTHON) slurm/examples/dataset.py provenance-diff $(if $(FAST),--fast)

# --- Planning ---

## sweep-estimate | GROUP= [RF=] | read | run-catapult | Designs, runtime, memory and node-hours from past runs
sweep-estimate:
	@test -n "$(GROUP)" || { echo 'usage: make sweep-estimate GROUP=<group from slurm/sweeps.tsv> [RF=1,4]'; exit 2; }
	@$(NERSC_PY) slurm/examples/sweep_estimate.py $(GROUP) $(if $(RF),--rf $(RF)) $(if $(NODES),--nodes $(NODES))
