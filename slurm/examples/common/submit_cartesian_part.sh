#!/bin/bash
# Shared submission logic for run_dense_3layers_cartesian_part_{01..10}.sh —
# sourced by all of them, do not invoke this file directly.
#
# submit_cartesian_part <part> <total> <task_range> <design_range>
#   part          e.g. "01" (also used in the array %-limit sbatch call)
#   total         e.g. "10"
#   task_range    e.g. "0-40" (array task indices, %12 concurrency applied here)
#   design_range  e.g. "0-655" (for logging only)
#
# Looks up the most recent run dir under
# $SCRATCH/catapult_dense_3layers_cartesian_rf1/, submits the given array
# task range against its job_array.sh, and appends to slurm_job_ids.txt.

submit_cartesian_part() {
    local part="$1" total="$2" task_range="$3" design_range="$4"

    RUN_DIR=$(ls -dt "$SCRATCH"/catapult_dense_3layers_cartesian_rf1/run_*/ 2>/dev/null | head -1)
    RUN_DIR="${RUN_DIR%/}"

    [ -n "$RUN_DIR" ] || { echo "ERROR: no run directory found under $SCRATCH/catapult_dense_3layers_cartesian_rf1/"; exit 1; }
    [ -f "$RUN_DIR/job_array.sh" ] || { echo "ERROR: $RUN_DIR/job_array.sh not found — run the RF=1 init script first"; exit 1; }

    echo "Submitting Part ${part}/${total}: array tasks ${task_range} (designs ${design_range})..."
    JOB_ID=$(sbatch --array="${task_range}%12" --parsable "$RUN_DIR/job_array.sh")
    echo "Part ${part} submitted: job $JOB_ID"
    echo "part=${part} job=$JOB_ID tasks=${task_range} designs=${design_range}" >> "$RUN_DIR/slurm_job_ids.txt"
}
