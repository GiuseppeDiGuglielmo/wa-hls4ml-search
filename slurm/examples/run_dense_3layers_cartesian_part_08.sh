#!/bin/bash
# Part 08/10 — 3-layer cartesian, RF=1
# Array tasks 287-327 → designs 4592–5247 (656 designs)
#
# Run run_dense_3layers_cartesian_rf1.sh first to generate the build dirs.
# Usage: bash slurm/examples/run_dense_3layers_cartesian_part_08.sh

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${REPO_DIR}/slurm/examples/common/submit_cartesian_part.sh"

submit_cartesian_part 08 10 287-327 4592-5247
