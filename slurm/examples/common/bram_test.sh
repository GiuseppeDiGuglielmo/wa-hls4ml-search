#!/bin/bash
# Shared BramFactor smoke-test invocation for run_bram_test_{small,medium,
# large,xl,xxl}.sh — sourced by all of them, do not invoke this file directly.
#
# run_bram_test <label> <neurons>
#   label    matches configs/model_sweeps/config_bram_test_<label>.json
#   neurons  neuron count per layer, only used for the log message

run_bram_test() {
    local label="$1" neurons="$2"
    echo "=== BramFactor smoke test: 2 layers, ${neurons} neurons, relu, 8-bit (${label}) ==="
    python iter_manager_catapult.py \
        -o "$SCRATCH/catapult_runs_bramtest" \
        --catapult_shell Perlmutter_scripts/catapult_shell.sh \
        --flow_tcl util/catapult_hls4ml_flow.tcl \
        --license_config license_servers_perlmutter.json \
        --flow_config_json configs/catapult_flow/config_catapult_flow.json \
        --gen_model_config_json "configs/model_sweeps/config_bram_test_${label}.json" \
        --batch_range 1 --batch_size 1
}
