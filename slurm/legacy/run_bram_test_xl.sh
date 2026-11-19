#!/bin/bash
# BramFactor smoke test — one XL model (2 layers, 256 neurons, relu, 8-bit).
# Runs synthesis directly (no SLURM) to avoid queue wait.
# After completion, check BramFactor made it into the generated project:
#   grep -r BramFactor $SCRATCH/catapult_runs_bramtest/
#
# Run from repo root: bash slurm/legacy/run_bram_test_xl.sh
source "$(python3 slurm/site_config.py venv)"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${REPO_DIR}/slurm/legacy/common/bram_test.sh"

run_bram_test xl 256
