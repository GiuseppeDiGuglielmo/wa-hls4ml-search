#!/bin/bash
# sz64 l1 — Node A: RF=1 (resume) then RF=16
# Part of 3-node parallel run (nodes A/B/C cover RF=1+16, RF=4, RF=8).
# Submit alongside node_b and node_c to use 300 licenses simultaneously.

set -euo pipefail

PARALLELISM=100
SLURM_TIME=05:30:00
SLURM_ACCOUNT=amsc011
SLURM_QOS=express_amsc
SLURM_CONSTRAINT=cpu

REPO_DIR="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
VENV="${WA_HLS4ML_VENV:-${SCRATCH}/venv_hls4ml/bin/activate}"

LM_LICENSE_FILE=$(python3 -c "
import json
with open('${REPO_DIR}/license_servers_perlmutter.json') as f:
    cfg = json.load(f)
print(':'.join(f\"{s['port']}@{s['host']}\" for s in cfg['servers']))
")

source "${REPO_DIR}/slurm/examples/common/dense_group_batch.sh"

# ── Main ──────────────────────────────────────────────────────────────────────

run_group l1_rf1  configs/model_sweeps/config_dense_3layers_sz64_l1.json configs/catapult_flow/config_catapult_flow_rf1.json
run_group l1_rf16 configs/model_sweeps/config_dense_3layers_sz64_l1.json configs/catapult_flow/config_catapult_flow.json

echo ""
echo "Node A done (RF=1, RF=16)."
