#!/bin/bash
# Part 05/10 — 3-layer cartesian, RF=1
# Array tasks 164-204 → designs 2624–3279 (656 designs)
#
# Run run_dense_3layers_cartesian_rf1.sh first to generate the build dirs.
# Usage: bash slurm/examples/run_dense_3layers_cartesian_part_05.sh

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${REPO_DIR}/slurm/examples/common/submit_cartesian_part.sh"

submit_cartesian_part 05 10 164-204 2624-3279
