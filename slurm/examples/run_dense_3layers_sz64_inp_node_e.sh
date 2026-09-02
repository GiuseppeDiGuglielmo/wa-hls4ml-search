#!/bin/bash
#SBATCH --job-name=orch_sz64_inp_e
#SBATCH --account=amsc011
#SBATCH --qos=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=10
#SBATCH --mem=16G
#SBATCH --time=2-00:00:00
#SBATCH --constraint=cpu
# sz64 inp — Node E: RF=4 (l1a+l1b) + RF=8 (l1a+l1b)
# Part of 2-node parallel run (D: RF=1+16, E: RF=4+8).
# Submit alongside node_d to use 200 licenses simultaneously.

set -euo pipefail

PARALLELISM=100
SLURM_TIME=05:30:00
SLURM_ACCOUNT=amsc011
SLURM_QOS=express_amsc
SLURM_CONSTRAINT=cpu

REPO_DIR="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
VENV="${WA_HLS4ML_VENV:-${SCRATCH}/venv_hls4ml/bin/activate}"
source "$VENV"

LM_LICENSE_FILE=$(python3 -c "
import json
with open('${REPO_DIR}/license_servers_perlmutter.json') as f:
    cfg = json.load(f)
print(':'.join(f\"{s['port']}@{s['host']}\" for s in cfg['servers']))
")

source "${REPO_DIR}/slurm/examples/common/dense_group_batch.sh"

# ── Main ──────────────────────────────────────────────────────────────────────

run_group inp_rf4_l1a configs/model_sweeps/config_dense_3layers_sz64_inp_l1a.json configs/catapult_flow/config_catapult_flow_rf4.json
run_group inp_rf4_l1b configs/model_sweeps/config_dense_3layers_sz64_inp_l1b.json configs/catapult_flow/config_catapult_flow_rf4.json

run_group inp_rf8_l1a configs/model_sweeps/config_dense_3layers_sz64_inp_l1a.json configs/catapult_flow/config_catapult_flow_rf8.json
run_group inp_rf8_l1b configs/model_sweeps/config_dense_3layers_sz64_inp_l1b.json configs/catapult_flow/config_catapult_flow_rf8.json

echo ""
echo "Node E done (RF=4 + RF=8)."
