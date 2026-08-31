#!/bin/bash
# Shared orchestration for the Nangate45 / GF22FDX N-layer LHS sweeps.
# Sourced by submit_45nm_nlayer_lhs.sh and submit_gf22_nlayer_lhs.sh — do not
# invoke this file directly.
#
# Contract for the caller (both are re-declared per RF group, so they may
# reference $RUN_DIR / $JOBLIST / $rf_label / $flow_cfg_name, which
# run_lhs_group sets as locals before calling them):
#
#   build_candidates_if_missing()   Called once, before the RF loop. Writes
#                                    $CANDIDATES if it doesn't exist yet.
#   build_joblist()                 Called once per RF group, after run_lhs_group
#                                    has created $RUN_DIR and set $JOBLIST.
#                                    Must build models (or extract them) and
#                                    write $JOBLIST (tab-separated job lines).
#
# Variables the caller must set before calling run_lhs_group:
#   REPO_DIR, VENV, N_LAYERS, CANDIDATES, PARALLELISM, SLURM_TIME,
#   SLURM_ACCOUNT, SLURM_QOS, SLURM_CONSTRAINT, LM_LICENSE_FILE,
#   TECH_LABEL   e.g. "Nangate 45nm" / "GF22nm" — used in log messages
#   JOB_PREFIX   e.g. "45nm" / "gf22" — used in generated SBATCH job names
#   BASE_PREFIX  e.g. "${SCRATCH}/catapult_45nm" — run_lhs_group appends
#                "_${N_LAYERS}layer_lhs_${rf_label}"
#   ARCHIVE_LABEL  e.g. "nangate45/" / "gf22fdx/" — used in log messages only
#                  (the actual archive destination is decided by archive_run.sh)
#
# DRY_RUN=1 skips sbatch submission and the retry loop entirely, but still
# builds candidates, the joblist, the 3-way split, and the 3
# parallel_synth_*.sh scripts — useful for verifying script changes without
# touching SLURM or the shared CFS archive.

wait_for_jobs() {
    local tar_dir="$1"; shift
    local jids=("$@")
    echo "  Waiting for SLURM jobs: ${jids[*]}..."
    sleep 30
    local elapsed=0
    while true; do
        local any_running=0
        for jid in "${jids[@]}"; do
            squeue -j "$jid" -h 2>/dev/null | grep -q . && { any_running=1; break; }
        done
        [ "$any_running" -eq 0 ] && break
        sleep 60
        elapsed=$(( elapsed + 60 ))
        if (( elapsed % 300 == 0 )) && [ -n "$tar_dir" ]; then
            local n; n=$(find "$tar_dir" -maxdepth 1 -name "*.tar.gz" 2>/dev/null | wc -l)
            echo "  [$(date '+%H:%M')] tarballs so far: $n"
        fi
    done
    for jid in "${jids[@]}"; do
        local states
        states=$(sacct -j "$jid" --format=State --noheader -P 2>/dev/null | sort | uniq -c)
        echo "  Job $jid final states: $states"
    done
}

_make_synth_script() {
    # Reads $BASE, $RUN_DIR, $rf_label from the caller's (run_lhs_group's)
    # local scope via bash dynamic scoping.
    local part="$1" jl="$2"
    local script="${RUN_DIR}/parallel_synth_${part}.sh"
    local jlog="${RUN_DIR}/parallel_${part}.log"
    cat > "$script" <<SBATCH_EOF
#!/bin/bash
#SBATCH --job-name=${JOB_PREFIX}_${N_LAYERS}l_${rf_label}_${part}
#SBATCH --account=${SLURM_ACCOUNT}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=100
#SBATCH --mem=200G
#SBATCH --constraint=${SLURM_CONSTRAINT}
#SBATCH --time=${SLURM_TIME}
#SBATCH --qos=${SLURM_QOS}
#SBATCH --output=${RUN_DIR}/slurm_logs/parallel_${part}.out
#SBATCH --error=${RUN_DIR}/slurm_logs/parallel_${part}.err

set -euo pipefail
source "${VENV}"
export LM_LICENSE_FILE="${LM_LICENSE_FILE}"
cd "${REPO_DIR}"

parallel \\
    --joblog "${jlog}" \\
    --resume-failed \\
    --line-buffer \\
    -j ${PARALLELISM} \\
    python "${REPO_DIR}/iter_manager_catapult.py" -o "${BASE}" --run-single-job {} \\
    < "${jl}"
SBATCH_EOF
    chmod +x "$script"
    echo "$script"
}

run_lhs_group() {
    local rf_label="$1"
    local flow_cfg_name="$2"
    local BASE="${BASE_PREFIX}_${N_LAYERS}layer_lhs_${rf_label}"

    echo ""
    echo "=== ${TECH_LABEL} ${N_LAYERS}-layer LHS  RF=${rf_label} ==="

    local ts run_id RUN_DIR
    ts=$(date '+%Y%m%d_%H%M%S')
    run_id=$(python3 -c "import uuid; print(uuid.uuid4().hex[:8])")
    RUN_DIR="${BASE}/run_${ts}_${run_id}"
    mkdir -p "${RUN_DIR}/tarballs" "${RUN_DIR}/slurm_logs"
    echo "  Run dir: $RUN_DIR"

    local JOBLIST="${RUN_DIR}/joblist.txt"

    build_joblist

    local n_jobs
    n_jobs=$(wc -l < "$JOBLIST" 2>/dev/null || echo 0)
    [[ "$n_jobs" -gt 0 ]] || { echo "ERROR: no designs to synthesize" >&2; return 1; }
    echo "  Ready: $n_jobs synthesis jobs  (3 nodes × $PARALLELISM = $(( PARALLELISM * 3 )) parallel)"

    local n_a=$(( n_jobs / 3 ))
    local n_b=$(( n_jobs / 3 ))
    local n_c=$(( n_jobs - n_a - n_b ))
    local JOBLIST_A="${RUN_DIR}/joblist_a.txt"
    local JOBLIST_B="${RUN_DIR}/joblist_b.txt"
    local JOBLIST_C="${RUN_DIR}/joblist_c.txt"
    head -n "$n_a"                        "$JOBLIST" > "$JOBLIST_A"
    sed -n "$((n_a+1)),$((n_a+n_b))p"     "$JOBLIST" > "$JOBLIST_B"
    tail -n "+$((n_a + n_b + 1))"         "$JOBLIST" > "$JOBLIST_C"
    echo "  Split: node-a=$n_a  node-b=$n_b  node-c=$n_c"

    local SCRIPT_A SCRIPT_B SCRIPT_C
    SCRIPT_A=$(_make_synth_script a "$JOBLIST_A")
    SCRIPT_B=$(_make_synth_script b "$JOBLIST_B")
    SCRIPT_C=$(_make_synth_script c "$JOBLIST_C")

    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        echo "  DRY_RUN=1 — skipping sbatch submission for ${rf_label}."
        return 0
    fi

    local total="$n_jobs"
    local done_count max_rounds=20 round=0
    local TAR_DIR="${RUN_DIR}/tarballs"

    local jid_a jid_b jid_c
    jid_a=$(sbatch --parsable "$SCRIPT_A")
    jid_b=$(sbatch --parsable "$SCRIPT_B")
    jid_c=$(sbatch --parsable "$SCRIPT_C")
    echo "  [round 0] Submitted: $jid_a (a, $n_a) + $jid_b (b, $n_b) + $jid_c (c, $n_c)"
    wait_for_jobs "$TAR_DIR" "$jid_a" "$jid_b" "$jid_c"
    done_count=$(find "$TAR_DIR" -maxdepth 1 -name "*.tar.gz" 2>/dev/null | wc -l)
    echo "  [round 0] done: $done_count / $total"

    while (( done_count < total && round < max_rounds )); do
        round=$(( round + 1 ))
        echo "  [round $round] $done_count/$total — $(( total - done_count )) remaining — re-submitting..."
        jid_a=$(sbatch --parsable "$SCRIPT_A")
        jid_b=$(sbatch --parsable "$SCRIPT_B")
        jid_c=$(sbatch --parsable "$SCRIPT_C")
        echo "  [round $round] Submitted: $jid_a + $jid_b + $jid_c"
        wait_for_jobs "$TAR_DIR" "$jid_a" "$jid_b" "$jid_c"
        local prev=$done_count
        done_count=$(find "$TAR_DIR" -maxdepth 1 -name "*.tar.gz" 2>/dev/null | wc -l)
        echo "  [round $round] done: $done_count / $total  (+$(( done_count - prev )) new)"
        (( done_count == prev )) && { echo "  [round $round] no progress — aborting retries" >&2; break; }
    done

    if (( done_count < total )); then
        echo "  WARNING: $done_count/$total completed after $round rounds ($(( total - done_count )) hard failures)"
    else
        echo "  Synthesis complete ($done_count/$total)"
    fi

    echo "  Archiving ${rf_label} → ${ARCHIVE_LABEL} ..."
    bash "${REPO_DIR}/slurm/examples/archive_run.sh" "${RUN_DIR}" --yes
    echo "  Done: ${TECH_LABEL} ${N_LAYERS}-layer LHS ${rf_label}."
}
