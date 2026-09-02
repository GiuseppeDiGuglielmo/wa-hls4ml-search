#!/bin/bash
# Full Cartesian product run — all 2,880 unique 2-layer dense NN configs
# (input 4-32, hidden 4-32, output 4-32, independent activations per layer,
# relu/tanh/sigmoid, bitwidth 4-12 even). No random sampling.
#
# Run from repo root: bash slurm/examples/run_dense_2layers_cartesian.sh
source $SCRATCH/venv_hls4ml/bin/activate

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${REPO_DIR}/slurm/examples/common/dense2layer_cartesian.sh"

run_2layer_config \
  $SCRATCH/catapult_dense_2layers_cartesian \
  configs/model_sweeps/config_dense_2layers.json \
  configs/catapult_flow/config_catapult_flow.json
