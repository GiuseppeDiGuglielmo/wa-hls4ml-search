#!/bin/bash
# Shared orchestration for the sz64 3-layer dense batch scripts
# (run_dense_3layers_sz64_l1/l2/l3.sh, their node_a/b/c splits, and
# run_dense_3layers_sz64_inp.sh with its node_d/e splits) — sourced by all
# of them, do not invoke this file directly.
#
# Variables the caller must set before calling run_group:
#   REPO_DIR, VENV, LM_LICENSE_FILE, PARALLELISM,
#   SLURM_TIME, SLURM_ACCOUNT, SLURM_QOS, SLURM_CONSTRAINT
# (SBATCH --cpus-per-task is derived as 2 * PARALLELISM, matching every
# call site: 100->200, 128->256.)
#
# Pre-dedup, sz64_inp_node_d.sh / sz64_inp_node_e.sh had already picked up
# two fixes the other 7 call sites lacked:
#   - tarball counting via `find -maxdepth 1 -name` instead of a bare `ls
#     *.tar.gz` glob, which breaks once a directory holds thousands of
#     files (same fix already used in nlayer_lhs_group.sh)
#   - REPO_DIR falling back through SLURM_SUBMIT_DIR, which is more
#     reliable than BASH_SOURCE-relative lookup when this script is itself
#     the #SBATCH entry point
# Both are applied here for all 9 call sites.

wait_for_job() {
    local jid="$1"
    echo "  Waiting for SLURM job $jid (squeue, every 60s)..."
    sleep 30
    while squeue -j "$jid" -h 2>/dev/null | grep -q .; do
        sleep 60
    done
    local states
    states=$(sacct -j "$jid" --format=State --noheader -P 2>/dev/null | sort | uniq -c)
    echo "  Job $jid final states: $states"
}

resume_if_incomplete() {
    local run_dir="$1"
    local joblist="${run_dir}/joblist.txt"
    local tar_dir="${run_dir}/tarballs"
    local total done max_rounds=20 round=0

    total=$(wc -l < "$joblist")
    done=$(find "${tar_dir}" -maxdepth 1 -name "*.tar.gz" 2>/dev/null | wc -l)

    while (( done < total && round < max_rounds )); do
        round=$(( round + 1 ))
        echo "  Incomplete: $done/$total — re-submitting (round $round/$max_rounds)..."
        local jid
        jid=$(sbatch --parsable "${run_dir}/parallel_synth.sh")
        echo "  Submitted: $jid"
        wait_for_job "$jid"
        done=$(find "${tar_dir}" -maxdepth 1 -name "*.tar.gz" 2>/dev/null | wc -l)
    done

    if (( done >= total )); then
        echo "  Complete ($done/$total)."
        return 0
    fi
    echo "  ERROR: still incomplete after $max_rounds rounds ($done/$total)" >&2
    return 1
}

run_group() {
    local label="$1" model_cfg="$2" flow_cfg="$3"
    local base="${SCRATCH}/catapult_dense_3layers_sz64_${label}"

    echo ""
    echo "=== sz64 ${label} ==="

    local run_dir
    run_dir=$(ls -d "${base}"/run_*/ 2>/dev/null | sort | tail -1 || true)
    run_dir="${run_dir%/}"

    if [[ -z "$run_dir" || ! -f "${run_dir}/joblist.txt" ]]; then
        python iter_manager_catapult.py \
            -o "$base" \
            --gen_model_config_json "$model_cfg" \
            --flow_config_json "$flow_cfg" \
            --catapult_shell Perlmutter_scripts/catapult_shell.sh \
            --flow_tcl util/catapult_hls4ml_flow.tcl \
            --cartesian \
            --prepare-only

        run_dir=$(ls -d "${base}"/run_*/ 2>/dev/null | sort | tail -1 || true)
        run_dir="${run_dir%/}"
    else
        echo "  Reusing: $run_dir"
    fi

    [[ -n "$run_dir" ]] || { echo "ERROR: no run dir created under $base" >&2; return 1; }

    local joblist="${run_dir}/joblist.txt"
    local joblog="${run_dir}/parallel.log"
    local slurm_logs="${run_dir}/slurm_logs"
    local parallel_script="${run_dir}/parallel_synth.sh"
    mkdir -p "$slurm_logs"

    cat > "$parallel_script" <<SBATCH_EOF
#!/bin/bash
#SBATCH --job-name=catapult_sz64_${label}
#SBATCH --account=${SLURM_ACCOUNT}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=$(( PARALLELISM * 2 ))
#SBATCH --mem=400G
#SBATCH --constraint=${SLURM_CONSTRAINT}
#SBATCH --time=${SLURM_TIME}
#SBATCH --qos=${SLURM_QOS}
#SBATCH --output=${slurm_logs}/parallel.out
#SBATCH --error=${slurm_logs}/parallel.err

set -euo pipefail
source "${VENV}"
export LM_LICENSE_FILE="${LM_LICENSE_FILE}"
cd "${REPO_DIR}"

parallel \\
    --joblog "${joblog}" \\
    --resume-failed \\
    --line-buffer \\
    -j ${PARALLELISM} \\
    python "${REPO_DIR}/iter_manager_catapult.py" -o "${base}" --run-single-job {} \\
    < "${joblist}"
SBATCH_EOF
    chmod +x "$parallel_script"

    local jid
    jid=$(sbatch --parsable "$parallel_script")
    echo "  Submitted: $jid ($(wc -l < "$joblist") designs, $PARALLELISM parallel slots)"
    wait_for_job "$jid"

    resume_if_incomplete "${run_dir}" || return 1

    echo "  Archiving ${label}..."
    bash slurm/examples/archive_run.sh "${run_dir}" --yes
    echo "  Done: ${label}."
}
