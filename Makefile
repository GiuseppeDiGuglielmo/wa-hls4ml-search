# Targets for the Catapult sweeps, grouped bottom-up: tool chain, one design,
# one run, archive, whole dataset, planning. The same commands back the agent
# skills in .claude/skills/ (run-catapult, check-runs, archive-run, dataset), so
# a person running `make` and an agent get the same answer.
#
# Read-only unless marked. Marked targets do nothing without their flag:
#   PROBE=1   catapult-probe takes one license for a few seconds
#   SUBMIT=1  design-synth, rerun-failed submit jobs (sweep always submits)
#   APPLY=1   reparse, rebuild-archived, archive-index write; scratch-clean deletes
# archive copies into the shared archive; run archive-dry first.
# scratch-clean is the only target that deletes, and only after archive-verify.

SHELL := /bin/bash
PYTHON ?= python3
# NERSC's Python (3.7+), for tools that import the sweep catalog or the pipeline.
NERSC_PY ?= /global/common/software/nersc/pe/conda-envs/latest/python-3.13/nersc-python/bin/python
RUN      ?=
RUNS     ?=
OUT      ?=
STEMS    ?=
FIRST_ONLY ?=
STEM     ?=
EXPECTED ?=
TECH     ?=
WHERE    ?=
GREP     ?=
SITE     := python3 slurm/site_config.py
DEFAULTS := python3 slurm/defaults_config.py
ACCOUNT  ?= $(shell $(SITE) get account)
# The sweep driver job; defaults in slurm/defaults.json (sweep_driver).
DRIVER_QOS  ?= $(shell $(DEFAULTS) sweep_driver qos)
DRIVER_TIME ?= $(shell $(DEFAULTS) sweep_driver time)
DRIVER_MEM  ?= $(shell $(DEFAULTS) sweep_driver mem)
EXPRESS_QOS := $(shell $(SITE) get express_qos)
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
DETAILS  ?=
EVERY    ?= 10
ONCE     ?=
DROP_BACKUPS ?=
WORKERS  ?= 8
LMUTIL   ?=
PROBE_DIR = $(SCRATCH)/catapult_probe
SWEEP_OPTS = $(if $(RF),--rf $(RF)) $(if $(QOS),--qos $(QOS)) $(if $(TIME),--time $(TIME)) \
             $(if $(NODES),--nodes $(NODES)) $(if $(PARALLELISM),--parallelism $(PARALLELISM)) \
             $(if $(MEM),--mem $(MEM)) $(if $(MEMFREE),--memfree $(MEMFREE))
JOB_OPTS = $(if $(QOS),--qos $(QOS)) $(if $(TIME),--time $(TIME)) $(if $(MEM),--mem $(MEM))
# Same license string sweep.sh uses (slurm/site_config.py licenses).
# WA_LICENSES=port@host overrides it, as for rerun-failed and design-synth.
LICENSES = $$($(SITE) licenses)
# The venv prints a harmless distutils-precedence.pth traceback on each python3 call.
VENV_NOISE = -e distutils -e add_shim -e 'site.py' -e 'exec(line)' -e 'File "<string>"' -e '^ *Traceback' -e 'Remainder of file' -e '^ *$$'
need_run  = @test -n "$(RUN)" || { echo 'usage: make $@ RUN=<scratch run_dir>$(1)'; exit 2; }

.PHONY: help env-check license-check catapult-probe \
        design-show design-synth \
        check-jobs check-list check-run sweep-watch why-failed reparse rebuild-archived rerun-failed sweep-check sweep \
        archive-dry archive archive-verify scratch-clean archive-index \
        dataset-summary provenance-diff design-cost sweep-estimate

# help: each target's '## target | args | description' line,
# grouped by the agent skill that uses it (.claude/skills/README.md).
help:
	@echo 'Catapult sweeps on Perlmutter. Usage: make <target> [ARG=value ...]'
	@echo 'Targets only read or show a plan, unless you add the setting their line names'
	@echo '(PROBE=1, SUBMIT=1, APPLY=1). Only sweep and archive act every time.'
	@awk -F' [|] ' '/^## [a-z-]+ [|]/ { sub(/^## /, "", $$1); \
	    row[$$1] = sprintf("  %-16s %-22s %s", $$1, $$2, $$3) } \
	  END { n = split("run-catapult:tool chain, sweeps, repairs:env-check license-check catapult-probe sweep-estimate sweep-check sweep reparse rebuild-archived rerun-failed design-synth;" \
	                  "check-runs:status and failures:check-jobs check-list check-run sweep-watch why-failed design-show;" \
	                  "archive-run:archive and scratch:archive-dry archive archive-verify scratch-clean archive-index;" \
	                  "dataset:the archived dataset:dataset-summary provenance-diff design-cost", grp, ";"); \
	    for (i = 1; i <= n; i++) { split(grp[i], f, ":"); printf "\n%s: %s\n", f[1], f[2]; \
	      m = split(f[3], t, " "); for (k = 1; k <= m; k++) print (t[k] in row ? row[t[k]] : "  " t[k] "  (no help line)") } }' $(MAKEFILE_LIST)
	@echo
	@echo 'sweep opts: RF= QOS= TIME= NODES= PARALLELISM= MEM= MEMFREE=; driver job: DRIVER_QOS= DRIVER_TIME= DRIVER_MEM='
	@echo 'Unset QOS/TIME/MEM/... use slurm/defaults.json: starting points to choose per run, not decisions.'
	@echo 'rerun-failed and design-synth also take QOS= TIME= MEM=; rerun-failed also PARALLELISM= MEMFREE='
	@echo 'archive-dry, archive, archive-verify, scratch-clean take TECH=nangate45|gf22fdx (default: where the run is archived, else its catalog group)'
	@echo 'scratch-clean takes DROP_BACKUPS=1 (with APPLY=1, also deletes scratch-only *_stale_* backups)'
	@echo 'RUN= is a scratch run folder; check-run and design-show also take a run name, rebuild-archived only a name.'
	@echo 'More: .claude/skills/README.md; one printable page: .claude/skills/cheatsheet.txt'

# --- Tool chain: does Catapult work here? ---

## env-check |  | Check venv, container, Catapult install and licenses
env-check:
	@$(PYTHON) -m slurm.tools.catapult_env env

## license-check | [LMUTIL=] | Check each license server answers and list its Catapult features
license-check:
	@$(PYTHON) -m slurm.tools.catapult_env license $(if $(LMUTIL),--lmutil $(LMUTIL))

## catapult-probe | [PROBE=1] | Launcher dry run. PROBE=1 starts Catapult once (1 license)
catapult-probe:
	@mkdir -p $(PROBE_DIR)
	@if [ -n "$(PROBE)" ]; then \
	  LM_LICENSE_FILE=$(LICENSES) bash Perlmutter_scripts/catapult_shell.sh --work-dir $(PROBE_DIR) \
	    --cmd 'puts "catapult-probe: OK in [pwd]"; exit' 2>&1 | grep -E 'catapult-probe: OK|rror' \
	    || { echo 'catapult-probe: no OK line; run the launcher by hand to see its output'; exit 1; }; \
	else \
	  LM_LICENSE_FILE=$(LICENSES) bash Perlmutter_scripts/catapult_shell.sh --dry-run --work-dir $(PROBE_DIR) \
	    | tr ' ' '\n' | sed -n -e 's|.*/apptainer$$|apptainer   &|p' -e 's|.*\.sif$$|container   &|p' \
	      -e 's|^CATAPULT_PATH_OVERRIDE=|catapult    |p' -e 's|^LM_LICENSE_FILE=\([0-9][^"\\]*\)$$|license     \1|p' \
	      -e 's#^\(/[^ ]*/\(cad_env_perlmutter\|siemens\)\.sh\).*#env script  \1#p'; \
	  echo "product     $$($(DEFAULTS) catapult-product) (CATAPULT_PRODUCT=ultra|genesis)"; \
	  echo "(dry run; PROBE=1 starts Catapult once to check the license)"; \
	fi

# --- One design ---

## design-show | RUN= STEM= | One design's report and every Catapult attempt
design-show:
	@test -n "$(RUN)" -a -n "$(STEM)" || { echo 'usage: make design-show RUN=<run_dir or run name> STEM=<stem>'; exit 2; }
	@$(PYTHON) -m slurm.tools.design_show $(RUN) $(STEM)

## design-synth | RUN= STEM= [SUBMIT=1] | Plans a rerun of one design. SUBMIT=1 submits it
design-synth:
	@test -n "$(RUN)" -a -n "$(STEM)" || { echo 'usage: make design-synth RUN=<scratch run_dir> STEM=<stem> [SUBMIT=1]'; exit 2; }
	@$(PYTHON) -m slurm.tools.design_synth $(RUN) $(STEM) $(JOB_OPTS) $(if $(SUBMIT),--submit)

# --- One run (a group at one RF) ---

## check-jobs | [ACCOUNT=] | Your jobs and the express node pools
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
	              for (a in n) printf "  %-12s %3d nodes  %s\n", a, n[a], (u[a] == "" ? "-" : "(" u[a] ")") }' \
	    | sort -k2,2nr -k1,1; \
	done

## check-list | [TECH= WHERE= GREP=] | Every run on scratch and in the archive
check-list:
	@$(PYTHON) -m slurm.tools.list_runs $(if $(TECH),--tech $(TECH)) $(if $(WHERE),--where $(WHERE)) $(if $(GREP),--grep "$(GREP)")

## sweep-watch | RUN=|GROUP= [RF= ONCE=1] | Live view of a sweep: progress bar, running designs, jobs, ETA. EVERY=10 s
sweep-watch:
	@test -n "$(RUN)$(GROUP)" || { echo 'usage: make sweep-watch RUN=<scratch run dir or run name> | GROUP=<group> [RF=N] [EVERY=10] [ONCE=1]'; exit 2; }
	@$(PYTHON) -m slurm.tools.sweep_watch $(RUN) $(if $(GROUP),--group $(GROUP)) $(if $(RF),--rf $(RF)) --every $(EVERY) $(if $(ONCE),--once)

## check-run | RUN= [EXPECTED= DETAILS=1] | Expected, good, failed and missing designs of a run. DETAILS=1 lists them
check-run:
	@test -n "$(RUN)" || { echo 'usage: make check-run RUN=<run_dir, catapult_* folder, or run name> [EXPECTED=N] [DETAILS=1]'; exit 2; }
	@$(PYTHON) -m slurm.tools.run_status $(RUN) $(if $(EXPECTED),--expected $(EXPECTED)) $(if $(DETAILS),--details)

## why-failed | RUN= [FAST=1] | Why designs failed: exit codes, OOM kills, time limits. FAST=1 skips memory
why-failed:
	$(call need_run,)
	@$(PYTHON) -m slurm.tools.why_failed $(RUN) $(if $(FAST),--no-memory)

## reparse | RUN= [APPLY=1] | Lists reports whose QoR is in a retry folder. APPLY=1 rewrites them
reparse:
	$(call need_run, [APPLY=1])
	@set -o pipefail; $(NERSC_PY) -m slurm.repairs.reparse $(RUN) $(if $(APPLY),--apply --workers $(WORKERS)) 2>&1 | { grep -v ' - INFO - ' || true; }

## rebuild-archived | RUN=<name> [APPLY=1] | Plans a scratch folder for an archive-only run's failed designs. APPLY=1 builds it
rebuild-archived:
	@test -n "$(RUN)" || { echo 'usage: make rebuild-archived RUN=<archive run name> [APPLY=1]'; exit 2; }
	@source "$$($(SITE) venv)" && \
	  TF_CPP_MIN_LOG_LEVEL=3 python -m slurm.repairs.rebuild_from_archive $(RUN) $(if $(APPLY),--apply) 2>&1 \
	  | grep -v -E 'distutils|Instructions for updating|Lambda fuctions'

## rerun-failed | RUN= [SUBMIT=1] | Plans a rerun of designs with no QoR. SUBMIT=1 submits it
rerun-failed:
	$(call need_run, [SUBMIT=1])
	@$(PYTHON) -m slurm.tools.rerun_failed $(RUN) $(JOB_OPTS) $(if $(PARALLELISM),--parallelism $(PARALLELISM)) $(if $(MEMFREE),--memfree $(MEMFREE)) $(if $(SUBMIT),--submit)

## sweep-check | GROUP= [sweep opts] | Sweep plan and sbatch --test-only; submits nothing
sweep-check:
	@test -n "$(GROUP)" || { echo 'usage: make sweep-check GROUP=<group from slurm/sweeps.tsv> [RF=1,4 ...]'; exit 2; }
	@bash slurm/sweep.sh $(GROUP) $(SWEEP_OPTS) --check 2>&1 | grep -v $(VENV_NOISE)
	@mkdir -p logs; echo "Sweep driver job:"; sbatch --test-only --account=$(ACCOUNT) --qos=$(DRIVER_QOS) --time=$(DRIVER_TIME) --mem=$(DRIVER_MEM) slurm/sweep.sh $(GROUP) $(SWEEP_OPTS) 2>&1 | sed 's/^/  /'

## sweep | GROUP= [sweep opts] | SUBMITS a sweep (nodes, licenses). Run sweep-check first
sweep:
	@test -n "$(GROUP)" || { echo 'usage: make sweep GROUP=<group> [RF=...]  (run make sweep-check first)'; exit 2; }
	@mkdir -p logs; sbatch --account=$(ACCOUNT) --qos=$(DRIVER_QOS) --time=$(DRIVER_TIME) --mem=$(DRIVER_MEM) slurm/sweep.sh $(GROUP) $(SWEEP_OPTS)

# --- Archive ---

## archive-dry | RUN= | What archive would copy
archive-dry:
	$(call need_run,)
	@$(PYTHON) -m slurm.tools.archive_sync $(RUN) $(if $(TECH),--tech $(TECH))

## archive | RUN= | COPIES a run into the shared archive (never deletes). Run archive-dry first
archive:
	$(call need_run,  (run make archive-dry first))
	@$(PYTHON) -m slurm.tools.archive_sync $(RUN) $(if $(TECH),--tech $(TECH)) --apply

## archive-verify | RUN= [ALL=1] | Check the archive holds everything of a run
archive-verify:
	$(call need_run,)
	@$(PYTHON) -m slurm.tools.archive_verify $(RUN) $(if $(TECH),--tech $(TECH)) $(if $(ALL),--all)

## scratch-clean | RUN= [APPLY=1] | Checks a scratch run can be deleted. APPLY=1 deletes it
scratch-clean:
	$(call need_run, [APPLY=1])
	@$(PYTHON) -m slurm.tools.scratch_clean $(RUN) $(if $(TECH),--tech $(TECH)) $(if $(APPLY),--apply) $(if $(DROP_BACKUPS),--drop-backups)

## archive-index | [APPLY=1] | Lists runs missing from the archive README. APPLY=1 adds them
archive-index:
	@$(PYTHON) -m slurm.tools.dataset index $(if $(APPLY),--apply)

# --- Whole dataset ---

## dataset-summary | [TECH= FAST=1] | Reports and good designs per run and tech
dataset-summary:
	@$(PYTHON) -m slurm.tools.dataset summary $(if $(TECH),--tech $(TECH)) $(if $(FAST),--fast)

## provenance-diff | [FAST=1] | Where PROVENANCE.md disagrees with the archive
provenance-diff:
	@$(PYTHON) -m slurm.tools.dataset provenance-diff $(if $(FAST),--fast)

## design-cost | RUNS= [OUT= TECH= STEMS= FIRST_ONLY=1] | Catapult time and peak memory per design, from archived tarballs
design-cost:
	@test -n "$(RUNS)" || { echo 'usage: make design-cost RUNS="<run name|run dir|mlp-<N>layer dir> ..." [OUT=file.tsv] [WORKERS=8]'; exit 2; }
	@$(PYTHON) -m slurm.tools.design_cost $(RUNS) --workers $(WORKERS) $(if $(TECH),--tech $(TECH)) $(if $(OUT),--out $(OUT)) $(if $(STEMS),--stems $(STEMS)) $(if $(FIRST_ONLY),--first-only)

# --- Planning ---

## sweep-estimate | GROUP= [RF= NODES=] | Designs, runtime, memory and node-hours from past runs
sweep-estimate:
	@test -n "$(GROUP)" || { echo 'usage: make sweep-estimate GROUP=<group from slurm/sweeps.tsv> [RF=1,4]'; exit 2; }
	@$(NERSC_PY) -m slurm.tools.sweep_estimate $(GROUP) $(if $(RF),--rf $(RF)) $(if $(NODES),--nodes $(NODES))
