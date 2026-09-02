#!/bin/bash
# Part 10/10 — 3-layer cartesian, RF=1
# Array tasks 369-410 → designs 5904–6560 (657 designs)
#
# Run run_dense_3layers_cartesian_rf1.sh first to generate the build dirs.
# Usage: bash slurm/examples/run_dense_3layers_cartesian_part_10.sh

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${REPO_DIR}/slurm/examples/common/submit_cartesian_part.sh"

submit_cartesian_part 10 10 369-410 5904-6560
