#!/bin/bash
# Part 06/10 — 3-layer cartesian, RF=1
# Array tasks 205-245 → designs 3280–3935 (656 designs)
#
# Run run_dense_3layers_cartesian_rf1.sh first to generate the build dirs.
# Usage: bash slurm/examples/run_dense_3layers_cartesian_part_06.sh

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${REPO_DIR}/slurm/examples/common/submit_cartesian_part.sh"

submit_cartesian_part 06 10 205-245 3280-3935
