#!/bin/bash
# Part 07/10 — 3-layer cartesian, RF=1
# Array tasks 246-286 → designs 3936–4591 (656 designs)
#
# Run run_dense_3layers_cartesian_rf1.sh first to generate the build dirs.
# Usage: bash slurm/examples/run_dense_3layers_cartesian_part_07.sh

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${REPO_DIR}/slurm/examples/common/submit_cartesian_part.sh"

submit_cartesian_part 07 10 246-286 3936-4591
