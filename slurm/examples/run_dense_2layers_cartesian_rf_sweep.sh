#!/bin/bash
# ReuseFactor sweep — 2-layer dense NN configs with RF=1, 4, 8
# (input 4-32, hidden 4-32, output 4-32, relu/tanh/sigmoid, bitwidth 4/8/12).
# Complements run_dense_2layers_cartesian.sh (same grid, RF=16).
# 1728 designs per RF value = 5184 new designs total.
#
# Run from repo root: bash slurm/examples/run_dense_2layers_cartesian_rf_sweep.sh
source $SCRATCH/venv_hls4ml/bin/activate

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${REPO_DIR}/slurm/examples/common/dense2layer_cartesian.sh"

for RF in 1 4 8; do
  echo "=== RF=${RF}: 1728 designs ==="
  run_2layer_config \
    $SCRATCH/catapult_dense_2layers_cartesian_rf${RF} \
    configs/model_sweeps/config_dense_2layers.json \
    configs/catapult_flow/config_catapult_flow_rf${RF}.json
done
