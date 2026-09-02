#!/bin/bash
#SBATCH --job-name=sweep
#SBATCH --account=amsc011
#SBATCH --qos=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --constraint=cpu
#SBATCH --time=2-00:00:00
#SBATCH --output=logs/%x_%j.out
#SBATCH --error=logs/%x_%j.err
#
# The entry point for every design-space sweep. One group per invocation; the
# group's parameters come from slurm/sweeps.tsv, never from a per-group script.
#
#   sbatch slurm/sweep.sh 3l_sz64_l3              # all reuse factors in the row
#   sbatch slurm/sweep.sh 3l_sz64_l3 --rf 1,4     # a subset
#   sbatch slurm/sweep.sh gf22_lhs_3l --n-lhs 10000 \
#          --exclude gf22fdx/gf22_lhs_3layer_500.txt
#   sbatch slurm/sweep.sh 45nm_sz128_2l --rf 1 --qos regular --time 1-22:00:00
#   bash   slurm/sweep.sh 1l_base --list          # show the row and exit
#   DRY_RUN=1 bash slurm/sweep.sh 1l_base         # build everything, submit nothing
#
# Options:
#   --rf LIST       reuse factors to run (default: the row's rf column)
#   --nodes N       synthesis nodes per group (default 3, i.e. 300 license slots)
#   --parallelism N synthesis slots per node (default 100)
#   --mem SIZE      memory per node (default 200G; the sz64 groups used 400G)
#   --qos NAME      SLURM QOS for the synthesis nodes (default express_amsc)
#   --time HH:MM:SS wall time per synthesis node (default 05:30:00)
#   --n-lhs N       LHS sample count for the sampled modes
#   --exclude PATH  archive-relative candidates file to exclude (archive_lhs only)
#   --candidates P  use this candidates file instead of the row's
#   --list          print the resolved row and exit

set -euo pipefail

REPO_DIR="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
CATALOG="${REPO_DIR}/slurm/sweeps.tsv"
ARCHIVE_BASE="/global/cfs/cdirs/amsc011/shared/wa-hls4ml-catapult"
BASE_FLOW_CFG="${REPO_DIR}/configs/catapult_flow/config_catapult_flow.json"
VENV="${WA_HLS4ML_VENV:-${SCRATCH}/venv_hls4ml/bin/activate}"

GROUP="${1:-}"
[[ -n "$GROUP" && "$GROUP" != -* ]] || {
    echo "usage: sweep.sh <group> [options]   (groups: $(awk -F'\t' '!/^#/ && NF{print $1}' "$CATALOG" | tr -d ' ' | paste -sd, -))" >&2
    exit 2
}
shift

RF_LIST=""; N_NODES=3; PARALLELISM=100; MEM_PER_NODE=200G
SLURM_QOS_SYNTH=express_amsc; SLURM_TIME=05:30:00
N_LHS=""; EXCLUDE=""; CANDIDATES_OVERRIDE=""; LIST_ONLY=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --rf)          RF_LIST="$2"; shift 2 ;;
        --nodes)       N_NODES="$2"; shift 2 ;;
        --parallelism) PARALLELISM="$2"; shift 2 ;;
        --mem)         MEM_PER_NODE="$2"; shift 2 ;;
        --qos)         SLURM_QOS_SYNTH="$2"; shift 2 ;;
        --time)        SLURM_TIME="$2"; shift 2 ;;
        --n-lhs)       N_LHS="$2"; shift 2 ;;
        --exclude)     EXCLUDE="$2"; shift 2 ;;
        --candidates)  CANDIDATES_OVERRIDE="$2"; shift 2 ;;
        --list)        LIST_ONLY=1; shift ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

source "$VENV"
cd "$REPO_DIR"

# ── Resolve the catalog row ───────────────────────────────────────────────────
read_field() {
    python3 - "$1" <<'PYEOF'
import os, sys
sys.path.insert(0, os.path.join(os.environ["REPO_DIR"], "slurm", "sweeplib"))
from sweep_spec import load_catalog
spec = load_catalog(os.path.join(os.environ["REPO_DIR"], "slurm", "sweeps.tsv"))[os.environ["GROUP"]]
field = sys.argv[1]
if field == "rf":
    print(",".join(str(x) for x in spec.rf))
elif field == "candidates":
    print(spec.candidates or "")
elif field == "summary":
    print("%s  tech=%s  input=%d-%d  layers=%s  bw=%s  acts=%s  rf=%s  mode=%s" % (
        spec.group, spec.tech, spec.input_range[0], spec.input_range[1],
        ",".join("%d-%d" % r for r in spec.layers),
        ",".join(str(b) for b in spec.bitwidths),
        ",".join(spec.activations),
        ",".join(str(x) for x in spec.rf), spec.mode))
else:
    print(getattr(spec, field))
PYEOF
}
export REPO_DIR GROUP

python3 -c "
import os, sys
sys.path.insert(0, os.path.join('$REPO_DIR', 'slurm', 'sweeplib'))
from sweep_spec import load_catalog
c = load_catalog('$CATALOG')
if '$GROUP' not in c:
    sys.exit(\"unknown group '$GROUP'; known: \" + ', '.join(sorted(c)))
"

MODE=$(read_field mode)
TECH=$(read_field tech)
[[ -n "$RF_LIST" ]] || RF_LIST=$(read_field rf)
ROW_CANDIDATES=$(read_field candidates)

echo "=== $(read_field summary)"
if (( LIST_ONLY )); then exit 0; fi

LM_LICENSE_FILE=$(python3 -c "
import json
with open('${REPO_DIR}/license_servers_perlmutter.json') as f:
    cfg = json.load(f)
print(':'.join(f\"{s['port']}@{s['host']}\" for s in cfg['servers']))
")
export LM_LICENSE_FILE

SLURM_ACCOUNT=amsc011
SLURM_CONSTRAINT=cpu
SLURM_QOS="$SLURM_QOS_SYNTH"
export REPO_DIR VENV LM_LICENSE_FILE N_NODES PARALLELISM MEM_PER_NODE \
       SLURM_ACCOUNT SLURM_QOS SLURM_TIME SLURM_CONSTRAINT

source "${REPO_DIR}/slurm/sweeplib/orchestrate.sh"

# ── Candidates, for the sampled modes ─────────────────────────────────────────
CANDIDATES=""
if [[ "$MODE" != "cartesian" ]]; then
    if [[ -n "$CANDIDATES_OVERRIDE" ]]; then
        CANDIDATES="$CANDIDATES_OVERRIDE"
    else
        CANDIDATES="${ARCHIVE_BASE}/${ROW_CANDIDATES}"
    fi
    if [[ ! -f "$CANDIDATES" ]]; then
        echo "=== Generating candidates for ${GROUP} ==="
        if [[ "$MODE" == "archive_lhs" ]]; then
            exclude_arg=()
            [[ -n "$EXCLUDE" ]] && exclude_arg=(--exclude "${ARCHIVE_BASE}/${EXCLUDE}")
            python3 "${REPO_DIR}/slurm/examples/sample_lhs_from_archive.py" \
                --layers "$(read_field n_layers)" --n "${N_LHS:-5000}" \
                "${exclude_arg[@]}" --out "$CANDIDATES"
        else
            python3 "${REPO_DIR}/slurm/sweeplib/candidates.py" \
                --group "$GROUP" ${N_LHS:+--n-lhs "$N_LHS"} --out "$CANDIDATES"
        fi
    fi
    echo "Candidates: $(wc -l < "$CANDIDATES") designs at $CANDIDATES"
fi

# ── One run per reuse factor ──────────────────────────────────────────────────
for RF in ${RF_LIST//,/ }; do
    echo ""
    echo "=== ${GROUP}  RF=${RF} ==="
    BASE="${SCRATCH}/catapult_${GROUP}_rf${RF}"
    export GROUP RF BASE

    if [[ "$MODE" == "cartesian" ]]; then
        # iter_manager creates the run directory itself, so don't pre-create one
        # here: a second, empty run_* would confuse the newest-run lookup below
        # and the archiving tools. Stage the model space next to it instead.
        mkdir -p "$BASE"
        GEN_CFG="${BASE}/.gen_model_config_pending.json"
        python3 -c "
import json, os, sys
sys.path.insert(0, os.path.join('$REPO_DIR', 'slurm', 'sweeplib'))
from sweep_spec import load_catalog
spec = load_catalog('$CATALOG')['$GROUP']
json.dump(spec.to_gen_model_config(), open('$GEN_CFG', 'w'), indent=4)
"
        FLOW_SETS=$(python3 -c "
import os, sys
sys.path.insert(0, os.path.join('$REPO_DIR', 'slurm', 'sweeplib'))
from sweep_spec import load_catalog
spec = load_catalog('$CATALOG')['$GROUP']
print(' '.join('--flow-set %s=%s' % kv for kv in spec.flow_overrides($RF).items()))
")
        python iter_manager_catapult.py \
            -o "$BASE" \
            --gen_model_config_json "$GEN_CFG" \
            --flow_config_json "$BASE_FLOW_CFG" \
            $FLOW_SETS \
            --catapult_shell Perlmutter_scripts/catapult_shell.sh \
            --flow_tcl util/catapult_hls4ml_flow.tcl \
            --cartesian \
            --prepare-only

        # Adopt the run directory iter_manager just created.
        RUN_DIR=$(ls -dt "${BASE}"/run_*/ 2>/dev/null | head -1)
        RUN_DIR="${RUN_DIR%/}"
        [[ -n "$RUN_DIR" && -f "${RUN_DIR}/joblist.txt" ]] \
            || { echo "ERROR: no joblist under $BASE" >&2; exit 1; }
        mv "$GEN_CFG" "${RUN_DIR}/gen_model_config.json"
        mkdir -p "${RUN_DIR}/tarballs" "${RUN_DIR}/slurm_logs"
        JOBLIST="${RUN_DIR}/joblist.txt"
        echo "  Run dir: $RUN_DIR"
    else
        RUN_DIR="${BASE}/run_$(date '+%Y%m%d_%H%M%S')_$(python3 -c 'import uuid; print(uuid.uuid4().hex[:8])')"
        mkdir -p "${RUN_DIR}/tarballs" "${RUN_DIR}/slurm_logs"
        JOBLIST="${RUN_DIR}/joblist.txt"
        echo "  Run dir: $RUN_DIR"
        python3 "${REPO_DIR}/slurm/sweeplib/build_joblist.py" \
            --group "$GROUP" --candidates "$CANDIDATES" \
            --run-dir "$RUN_DIR" --rf "$RF" --flow-config "$BASE_FLOW_CFG"
    fi
    export RUN_DIR JOBLIST

    run_group
done

echo ""
echo "${GROUP}: sweep complete (rf ${RF_LIST})."
