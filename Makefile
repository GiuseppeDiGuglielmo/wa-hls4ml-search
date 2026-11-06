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

## help           Show this message
help:
	@grep -E '^##[@ ]' $(MAKEFILE_LIST) | sed -e 's/^##@ /\n/' -e 's/^## /  make /'

##@ Tool chain: does Catapult work here?

## env-check      venv, container, Apptainer, Catapult install (purge damage), env script, license file, parallel
env-check:
	@$(PYTHON) slurm/examples/catapult_env.py env

## license-check  Is each license server reachable; with LMUTIL=<path to lmutil>, its features
license-check:
	@$(PYTHON) slurm/examples/catapult_env.py license $(if $(LMUTIL),--lmutil $(LMUTIL))

## catapult-probe Launcher dry run; PROBE=1 starts Catapult once in $SCRATCH/catapult_probe (one license, seconds)
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

##@ One design

## design-show    Report, QoR, every Catapult attempt (last step, peak memory) and joblog entries: RUN=<run_dir or name> STEM=<stem>
design-show:
	@test -n "$(RUN)" -a -n "$(STEM)" || { echo 'usage: make design-show RUN=<run_dir or run name> STEM=<stem>'; exit 2; }
	@$(PYTHON) slurm/examples/design_show.py $(RUN) $(STEM)

## design-synth   Synthesise one design again in $SCRATCH/catapult_debug (plan only; SUBMIT=1 submits): RUN= STEM= [QOS= MEM= TIME=]
design-synth:
	@test -n "$(RUN)" -a -n "$(STEM)" || { echo 'usage: make design-synth RUN=<scratch run_dir> STEM=<stem> [SUBMIT=1]'; exit 2; }
	@$(PYTHON) slurm/examples/design_synth.py $(RUN) $(STEM) $(JOB_OPTS) $(if $(SUBMIT),--submit)

##@ One run (a group at one RF)

## check-jobs     Your SLURM jobs, and use of each 32-node express pool by account [ACCOUNT=amsc011]
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

## check-list     List runs on scratch and in the archive, with group/RF [TECH=nangate45|gf22fdx] [WHERE=scratch|archive|both] [GREP=text]
check-list:
	@$(PYTHON) slurm/examples/list_runs.py $(if $(TECH),--tech $(TECH)) $(if $(WHERE),--where $(WHERE)) $(if $(GREP),--grep "$(GREP)")

## check-run      Designs expected / good / failed, scratch vs archive: RUN=<run_dir, catapult_* folder, or run name> [EXPECTED=N]
check-run:
	@test -n "$(RUN)" || { echo 'usage: make check-run RUN=<run_dir, catapult_* folder, or run name>'; exit 2; }
	@$(PYTHON) slurm/examples/run_status.py $(RUN) $(if $(EXPECTED),--expected $(EXPECTED))

## check-failed   Missing reports/tarballs and failed SLURM tasks: RUN=<run_dir>
check-failed:
	@test -n "$(RUN)" || { echo 'usage: make check-failed RUN=<run_dir>'; exit 2; }
	@test -d "$(RUN)/build" || { echo 'check-failed: $(RUN) is not a scratch run directory (needs build/); for archive-only runs use make check-run'; exit 2; }
	@bash slurm/examples/check_failures.sh $(RUN)

## why-failed     Causes of Catapult failures: exit codes, OOM kills, time limits, attempts vs peak memory: RUN=<run_dir> [FAST=1 skips memory]
why-failed:
	$(call need_run,)
	@$(PYTHON) slurm/examples/why_failed.py $(RUN) $(if $(FAST),--no-memory)

## reparse        Rewrite reports whose QoR sits in a retry folder (list only; APPLY=1 rewrites, old files backed up): RUN= [WORKERS=8]
reparse:
	$(call need_run, [APPLY=1])
	@set -o pipefail; $(NERSC_PY) slurm/examples/reparse.py $(RUN) $(if $(APPLY),--apply --workers $(WORKERS)) 2>&1 | { grep -v ' - INFO - ' || true; }

## rerun-failed   Synthesise again only designs with no QoR anywhere (plan only; SUBMIT=1 submits): RUN= [QOS= TIME= MEM= PARALLELISM=]
rerun-failed:
	$(call need_run, [SUBMIT=1])
	@$(PYTHON) slurm/examples/rerun_failed.py $(RUN) $(JOB_OPTS) $(if $(PARALLELISM),--parallelism $(PARALLELISM)) $(if $(MEMFREE),--memfree $(MEMFREE)) $(if $(SUBMIT),--submit)

## sweep-check    Plan + sbatch --test-only for a sweep, builds and submits nothing: GROUP=<group> [RF= QOS= TIME= NODES= PARALLELISM= MEM= MEMFREE=]
sweep-check:
	@test -n "$(GROUP)" || { echo 'usage: make sweep-check GROUP=<group from slurm/sweeps.tsv> [RF=1,4 ...]'; exit 2; }
	@bash slurm/sweep.sh $(GROUP) $(SWEEP_OPTS) --check 2>&1 | grep -v $(VENV_NOISE)
	@mkdir -p logs; echo "Sweep driver job:"; sbatch --test-only slurm/sweep.sh $(GROUP) $(SWEEP_OPTS) 2>&1 | sed 's/^/  /'

## sweep          Submit a sweep (uses licenses and nodes; run sweep-check first): GROUP=<group> [same options]
sweep:
	@test -n "$(GROUP)" || { echo 'usage: make sweep GROUP=<group> [RF=...]  (run make sweep-check first)'; exit 2; }
	@mkdir -p logs; sbatch slurm/sweep.sh $(GROUP) $(SWEEP_OPTS)

##@ Archive

## archive-dry    What archive would copy or replace for a scratch run (writes nothing): RUN=<run_dir> [TECH=nangate45|gf22fdx]
archive-dry:
	$(call need_run,)
	@$(PYTHON) slurm/examples/archive_sync.py $(RUN) $(if $(TECH),--tech $(TECH))

## archive        Copy a scratch run into the shared archive; backs up stale reports, never deletes: RUN=<run_dir> [TECH=...]
archive:
	$(call need_run,  (run make archive-dry first))
	@$(PYTHON) slurm/examples/archive_sync.py $(RUN) $(if $(TECH),--tech $(TECH)) --apply

## archive-verify Does the archive hold everything of a scratch run (content, sizes, MD5 sample)? RUN= [ALL=1: MD5 of every tarball]
archive-verify:
	$(call need_run,)
	@$(PYTHON) slurm/examples/archive_verify.py $(RUN) $(if $(TECH),--tech $(TECH)) $(if $(ALL),--all)

## scratch-clean  Remove a scratch run after archive-verify passes (report only; APPLY=1 deletes): RUN=<run_dir>
scratch-clean:
	$(call need_run, [APPLY=1])
	@$(PYTHON) slurm/examples/scratch_clean.py $(RUN) $(if $(TECH),--tech $(TECH)) $(if $(APPLY),--apply)

## archive-index  Archive runs not mentioned in the archive README (list only; APPLY=1 appends them, after a backup)
archive-index:
	@$(PYTHON) slurm/examples/dataset.py index $(if $(APPLY),--apply)

##@ Whole dataset

## dataset-summary Reports and good designs per archive run, by tech and group [TECH=] [FAST=1: counts only] (cached in ~/.cache/wa-hls4ml)
dataset-summary:
	@$(PYTHON) slurm/examples/dataset.py summary $(if $(TECH),--tech $(TECH)) $(if $(FAST),--fast)

## provenance-diff Where slurm/examples/PROVENANCE.md disagrees with the archive [FAST=1: counts only]
provenance-diff:
	@$(PYTHON) slurm/examples/dataset.py provenance-diff $(if $(FAST),--fast)

##@ Planning

## sweep-estimate Designs, runtime, peak memory, slots per node and node-hours from past runs: GROUP=<group> [RF= NODES=]
sweep-estimate:
	@test -n "$(GROUP)" || { echo 'usage: make sweep-estimate GROUP=<group from slurm/sweeps.tsv> [RF=1,4]'; exit 2; }
	@$(NERSC_PY) slurm/examples/sweep_estimate.py $(GROUP) $(if $(RF),--rf $(RF)) $(if $(NODES),--nodes $(NODES))
