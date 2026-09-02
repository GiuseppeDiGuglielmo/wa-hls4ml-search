#!/bin/bash
# Cartesian product run — 1728 2-layer dense NN configs with bitwidths 6, 10, 14
# (input 4-32, hidden 4-32, output 4-32, independent activations per layer,
# relu/tanh/sigmoid). Complements run_dense_2layers_cartesian.sh (bw 4,8,12).
#
# Run from repo root: bash slurm/examples/run_dense_2layers_cartesian_bw6_10_14.sh
source $SCRATCH/venv_hls4ml/bin/activate

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${REPO_DIR}/slurm/examples/common/dense2layer_cartesian.sh"

run_2layer_config \
  $SCRATCH/catapult_dense_2layers_cartesian_bw6_10_14 \
  configs/model_sweeps/config_dense_2layers_bw6_10_14.json \
  configs/catapult_flow/config_catapult_flow.json
