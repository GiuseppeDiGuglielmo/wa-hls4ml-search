#!/bin/bash
# Step 1 — RF sweep for bitwidths 6, 10, 14 on the 2-layer 4-32 grid.
# Completes the RF×bitwidth coverage: RF=1,4,8 were already done for bw=4,8,12;
# this adds bw=6,10,14 for the same RF values.
# 1728 designs per RF value = 5184 new designs total.
#
# Run from repo root: bash slurm/examples/run_dense_2layers_cartesian_bw6_10_14_rf_sweep.sh
source $SCRATCH/venv_hls4ml/bin/activate

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${REPO_DIR}/slurm/examples/common/dense2layer_cartesian.sh"

for RF in 1 4 8; do
  echo "=== RF=${RF}, bw=6,10,14, sizes 4-32 (1728 designs) ==="
  run_2layer_config \
    $SCRATCH/catapult_dense_2layers_cartesian_bw6_10_14_rf${RF} \
    configs/model_sweeps/config_dense_2layers_bw6_10_14.json \
    configs/catapult_flow/config_catapult_flow_rf${RF}.json
done
