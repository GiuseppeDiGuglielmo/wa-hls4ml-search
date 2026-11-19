#!/bin/bash
# Submit, poll, retry and archive one reuse-factor group. Sourced by
# slurm/sweep.sh — do not invoke directly.
#
# This is the single copy of the loop that previously existed three times:
# common/nlayer_lhs_group.sh, common/dense_group_batch.sh (one node instead of
# three) and verbatim inside submit_45nm_sz128.sh.
#
# Variables the caller must set:
#   REPO_DIR VENV LM_LICENSE_FILE
#   GROUP RF BASE RUN_DIR JOBLIST TECH (catalog tech: nangate45 or gf22)
#   N_NODES PARALLELISM MEM_PER_NODE (0 = whole node)
#   MEMFREE      GNU parallel --memfree per node, e.g. 64G (empty or 0: off)
#   SLURM_ACCOUNT SLURM_QOS SLURM_TIME SLURM_CONSTRAINT
#   MAX_ROUNDS   retry rounds before giving up (default: slurm/defaults.json)
#
# DRY_RUN=1 builds the joblist, the node split and the sbatch scripts but
# submits nothing and archives nothing.
#
# Archiving copies into the shared archive with archive_sync.py, which never
# deletes: the scratch run stays until someone removes it by hand after
# `make check-run` shows it is fully archived.
#
# The loop only retries while rounds add tarballs; it does not judge why designs
# are missing. It ends by writing ${RUN_DIR}/sweep_summary.tsv (facts: rounds,
# counts, why it stopped, job ids, archive exit code), which make check-run
# shows; what to do next is decided from there (check-run, why-failed).

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

# Split the joblist into N_NODES parts, remainder onto the last one.
# Fills the parallel arrays SPLIT_LABELS / SPLIT_PATHS / SPLIT_COUNTS.
split_joblist() {
    local total="$1"
    SPLIT_LABELS=(); SPLIT_PATHS=(); SPLIT_COUNTS=()
    local per=$(( total / N_NODES ))
    local start=1 part count label out
    for (( part = 1; part <= N_NODES; part++ )); do
        count=$per
        (( part == N_NODES )) && count=$(( total - per * (N_NODES - 1) ))
        label=$(printf "\\$(printf '%03o' $(( 96 + part )))")   # a, b, c, ...
        out="${RUN_DIR}/joblist_${label}.txt"
        sed -n "${start},$(( start + count - 1 ))p" "$JOBLIST" > "$out"
        SPLIT_LABELS+=("$label"); SPLIT_PATHS+=("$out"); SPLIT_COUNTS+=("$count")
        start=$(( start + count ))
    done
}

make_synth_script() {
    local label="$1" jl="$2"
    local script="${RUN_DIR}/parallel_synth_${label}.sh"
    # Gate job starts on free memory: below MEMFREE no new design starts, below
    # half of it parallel kills its youngest job (retried in the next round).
    local memfree_opt=""
    [[ -n "${MEMFREE:-}" && "${MEMFREE}" != 0 ]] && memfree_opt="--memfree ${MEMFREE} "
    cat > "$script" <<SBATCH_EOF
#!/bin/bash
#SBATCH --job-name=${GROUP}_rf${RF}_${label}
#SBATCH --account=${SLURM_ACCOUNT}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=$(( PARALLELISM * 2 ))
#SBATCH --mem=${MEM_PER_NODE}
#SBATCH --constraint=${SLURM_CONSTRAINT}
#SBATCH --time=${SLURM_TIME}
#SBATCH --qos=${SLURM_QOS}
#SBATCH --output=${RUN_DIR}/slurm_logs/parallel_${label}.out
#SBATCH --error=${RUN_DIR}/slurm_logs/parallel_${label}.err

set -euo pipefail
source "${VENV}"
export LM_LICENSE_FILE="${LM_LICENSE_FILE}"
cd "${REPO_DIR}"

parallel \\
    --joblog "${RUN_DIR}/parallel_${label}.log" \\
    --resume-failed \\
    ${memfree_opt}--line-buffer \\
    -j ${PARALLELISM} \\
    python "${REPO_DIR}/iter_manager_catapult.py" -o "${BASE}" --run-single-job {} \\
    < "${jl}"
SBATCH_EOF
    chmod +x "$script"
    echo "$script"
}

# Submit every part, wait, and retry the whole set until the tarball count stops
# rising. GNU parallel's --resume-failed means a resubmission only re-runs what
# is still missing.
run_group() {
    local total
    total=$(wc -l < "$JOBLIST" 2>/dev/null || echo 0)
    [[ "$total" -gt 0 ]] || { echo "ERROR: no designs to synthesize" >&2; return 1; }
    # Never ask for more nodes than there are designs; the small profiling
    # groups are a single design and would otherwise submit empty joblists.
    (( N_NODES > total )) && N_NODES=$total
    echo "  Ready: $total synthesis jobs (${N_NODES} nodes x ${PARALLELISM} = $(( N_NODES * PARALLELISM )) parallel)"

    split_joblist "$total"

    local scripts=() summary=() i
    for i in "${!SPLIT_LABELS[@]}"; do
        scripts+=("$(make_synth_script "${SPLIT_LABELS[$i]}" "${SPLIT_PATHS[$i]}")")
        summary+=("${SPLIT_LABELS[$i]}=${SPLIT_COUNTS[$i]}")
    done
    echo "  Split: ${summary[*]}"

    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        echo "  DRY_RUN=1 - built ${#scripts[@]} sbatch script(s), submitting nothing."
        return 0
    fi

    local tar_dir="${RUN_DIR}/tarballs"
    local max_rounds="${MAX_ROUNDS:-$(python3 "${REPO_DIR}/slurm/site_config.py" default orchestrate max_rounds)}"
    local round=0 done_count prev jids=() all_jids=() stop=complete

    for script in "${scripts[@]}"; do jids+=("$(sbatch --parsable "$script")"); done
    all_jids+=("${jids[@]}")
    echo "  [round 0] Submitted: ${jids[*]}"
    wait_for_jobs "$tar_dir" "${jids[@]}"
    done_count=$(find "$tar_dir" -maxdepth 1 -name "*.tar.gz" 2>/dev/null | wc -l)
    echo "  [round 0] done: $done_count / $total"

    while (( done_count < total && round < max_rounds )); do
        round=$(( round + 1 ))
        echo "  [round $round] $done_count/$total - $(( total - done_count )) remaining - re-submitting..."
        jids=()
        for script in "${scripts[@]}"; do jids+=("$(sbatch --parsable "$script")"); done
        all_jids+=("${jids[@]}")
        echo "  [round $round] Submitted: ${jids[*]}"
        wait_for_jobs "$tar_dir" "${jids[@]}"
        prev=$done_count
        done_count=$(find "$tar_dir" -maxdepth 1 -name "*.tar.gz" 2>/dev/null | wc -l)
        echo "  [round $round] done: $done_count / $total  (+$(( done_count - prev )) new)"
        (( done_count == prev )) && { stop=no_progress; echo "  [round $round] no new tarballs - stopping retries" >&2; break; }
    done
    if (( done_count < total )) && [[ "$stop" == complete ]]; then stop=max_rounds; fi

    if (( done_count < total )); then
        echo "  STOPPED ($stop): $done_count/$total designs have a tarball after $round retry round(s);"
        echo "  $(( total - done_count )) without one. Next: make check-run / make why-failed RUN=${RUN_DIR}"
    else
        echo "  Synthesis complete ($done_count/$total)"
    fi

    local archive_tech
    archive_tech=$(python3 "${REPO_DIR}/slurm/site_config.py" archive-dir "${TECH:-}") || {
        echo "ERROR: unknown TECH '${TECH:-}', not archiving ${RUN_DIR}" >&2
        write_summary "$total" "$done_count" "$round" "$max_rounds" "$stop" not_run "${all_jids[@]}"
        return 1; }
    echo "  Archiving ${GROUP} rf${RF} to ${archive_tech} (copy only; scratch is kept) ..."
    local archive_rc=0
    python3 "${REPO_DIR}/slurm/examples/archive_sync.py" "${RUN_DIR}" --tech "${archive_tech}" --apply \
        || archive_rc=$?
    write_summary "$total" "$done_count" "$round" "$max_rounds" "$stop" "$archive_rc" "${all_jids[@]}"
    echo "  Done: ${GROUP} rf${RF} (summary: ${RUN_DIR}/sweep_summary.tsv)."
}

# Facts about how the loop ended, for make check-run and whoever decides next.
write_summary() {
    local total="$1" done_count="$2" rounds="$3" max_rounds="$4" stop="$5" archive_rc="$6"
    shift 6
    {
        printf 'finished\t%s\n' "$(date '+%Y-%m-%d %H:%M:%S')"
        printf 'group\t%s\nrf\t%s\n' "$GROUP" "$RF"
        printf 'designs\t%s\nwith_tarball\t%s\n' "$total" "$done_count"
        printf 'retry_rounds\t%s\nmax_rounds\t%s\n' "$rounds" "$max_rounds"
        printf 'stopped\t%s\n' "$stop"
        printf 'nodes\t%s\nslots_per_node\t%s\nqos\t%s\ntime\t%s\nmem\t%s\nmemfree\t%s\n' \
            "$N_NODES" "$PARALLELISM" "$SLURM_QOS" "$SLURM_TIME" "$MEM_PER_NODE" "${MEMFREE:-}"
        printf 'jobs\t%s\n' "$*"
        printf 'archive_sync_exit\t%s\n' "$archive_rc"
    } > "${RUN_DIR}/sweep_summary.tsv"
}
