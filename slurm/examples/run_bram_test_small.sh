#!/bin/bash
# BramFactor smoke test — one small model (2 layers, 4 neurons, relu, 8-bit).
# Runs synthesis directly (no SLURM) to avoid queue wait.
# After completion, check BramFactor made it into the generated project:
#   grep -r BramFactor $SCRATCH/catapult_runs_bramtest/
#
# Run from repo root: bash slurm/examples/run_bram_test_small.sh
source $SCRATCH/venv_hls4ml/bin/activate

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${REPO_DIR}/slurm/examples/common/bram_test.sh"

run_bram_test small 4
