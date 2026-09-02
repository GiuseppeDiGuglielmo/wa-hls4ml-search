#!/bin/bash
# sz64 inp group: input=64, l1/l2/l3 ∈ {4,8,16,32,64}
# 8 batches: 4 RF values × 2 l1-size ranges
#   l1a: l1 ∈ {4,8,16,32} → 16,200 designs/batch
#   l1b: l1 = 64          →  4,050 designs/batch
#
# ── Two-level scheduling ──────────────────────────────────────────────────────
# This script is an ORCHESTRATOR: it loops over RF groups, submitting one
# synthesis batch job at a time (express_amsc, 5.5 h, 100 Catapult slots) and
# waiting for it to finish before moving to the next.  The orchestrator itself
# uses almost no CPU — it just polls squeue every 60 s.
#
# PREFERRED — submit the orchestrator as a shared batch job (2 CPUs, 48 h):
#
#   REPO=/global/u2/g/gdg/research/projects/genesis/wa-hls4ml-paper/wa-hls4ml-search
#   sbatch --job-name=orch_sz64_inp --account=amsc011 \
#     --ntasks=1 --cpus-per-task=2 --mem=16G --constraint=cpu \
#     --time=48:00:00 --qos=shared \
#     --output=$SCRATCH/orch_sz64_inp.out --error=$SCRATCH/orch_sz64_inp.err \
#     --wrap="source \$SCRATCH/venv_hls4ml/bin/activate && \
#             cd $REPO && bash slurm/examples/run_dense_3layers_sz64_inp.sh"
#
# ALTERNATIVE — run interactively (session must outlive all rounds, ~86 h):
#   salloc -N 1 -C cpu --qos=interactive -t 4:00:00 -A amsc011
#   source $SCRATCH/venv_hls4ml/bin/activate
#   bash slurm/examples/run_dense_3layers_sz64_inp.sh
#
# Crash recovery: re-submitting the same command always resumes from where it
# left off — existing run dirs and completed tarballs are reused automatically.
# Run ONE group at a time to stay within the 100-license limit.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

PARALLELISM=128
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

# RF=1 (configs/catapult_flow/config_catapult_flow_rf1.json)
run_group inp_rf1_l1a configs/model_sweeps/config_dense_3layers_sz64_inp_l1a.json configs/catapult_flow/config_catapult_flow_rf1.json
run_group inp_rf1_l1b configs/model_sweeps/config_dense_3layers_sz64_inp_l1b.json configs/catapult_flow/config_catapult_flow_rf1.json

# RF=4
run_group inp_rf4_l1a configs/model_sweeps/config_dense_3layers_sz64_inp_l1a.json configs/catapult_flow/config_catapult_flow_rf4.json
run_group inp_rf4_l1b configs/model_sweeps/config_dense_3layers_sz64_inp_l1b.json configs/catapult_flow/config_catapult_flow_rf4.json

# RF=8
run_group inp_rf8_l1a configs/model_sweeps/config_dense_3layers_sz64_inp_l1a.json configs/catapult_flow/config_catapult_flow_rf8.json
run_group inp_rf8_l1b configs/model_sweeps/config_dense_3layers_sz64_inp_l1b.json configs/catapult_flow/config_catapult_flow_rf8.json

# RF=16 (configs/catapult_flow/config_catapult_flow.json = default RF=16)
run_group inp_rf16_l1a configs/model_sweeps/config_dense_3layers_sz64_inp_l1a.json configs/catapult_flow/config_catapult_flow.json
run_group inp_rf16_l1b configs/model_sweeps/config_dense_3layers_sz64_inp_l1b.json configs/catapult_flow/config_catapult_flow.json

echo ""
echo "All inp batches done."
