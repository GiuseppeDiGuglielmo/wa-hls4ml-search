# Read-only status targets for the Catapult sweeps. The same commands back the
# check-runs agent skill (.claude/skills/check-runs/), so a person running
# `make` and an agent get the same answer. Nothing here submits, cancels,
# deletes or archives anything.

PYTHON ?= python3
RUN      ?=
EXPECTED ?=
TECH     ?=
WHERE    ?=
GREP     ?=
ACCOUNT  ?= amsc011
EXPRESS_QOS := express_amsc express_amsc_g

.PHONY: help check-jobs check-list check-run check-failed

## help         Show this message
help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/^## /  make /'

## check-jobs   Your SLURM jobs, and use of each 32-node express pool by account [ACCOUNT=amsc011]
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

## check-list   List runs on scratch and in the archive, with group/RF [TECH=nangate45|gf22fdx] [WHERE=scratch|archive|both] [GREP=text]
check-list:
	@$(PYTHON) slurm/examples/list_runs.py $(if $(TECH),--tech $(TECH)) $(if $(WHERE),--where $(WHERE)) $(if $(GREP),--grep "$(GREP)")

## check-run    Designs expected / good / failed, scratch vs archive: RUN=<run_dir, catapult_* folder, or run name> [EXPECTED=N]
check-run:
	@test -n "$(RUN)" || { echo 'usage: make check-run RUN=<run_dir, catapult_* folder, or run name>'; exit 2; }
	@$(PYTHON) slurm/examples/run_status.py $(RUN) $(if $(EXPECTED),--expected $(EXPECTED))

## check-failed Missing reports/tarballs and failed SLURM tasks: RUN=<run_dir>
check-failed:
	@test -n "$(RUN)" || { echo 'usage: make check-failed RUN=<run_dir>'; exit 2; }
	@test -d "$(RUN)/build" || { echo 'check-failed: $(RUN) is not a scratch run directory (needs build/); for archive-only runs use make check-run'; exit 2; }
	@bash slurm/examples/check_failures.sh $(RUN)
