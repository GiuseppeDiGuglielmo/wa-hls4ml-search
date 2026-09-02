#!/bin/bash
# Shared iter_manager_catapult.py invocation for the run_dense_2layers_cartesian*.sh
# family (plain / _bw6_10_14 / _rf_sweep / _bw6_10_14_rf_sweep, x normal and
# _size64) — sourced by all of them, do not invoke this file directly.
# Generalizes the COMMON_ARGS array idiom already used ad hoc in several of
# those scripts.
#
# run_2layer_config <out_dir> <model_cfg> <flow_cfg>

run_2layer_config() {
    local out_dir="$1" model_cfg="$2" flow_cfg="$3"
    python iter_manager_catapult.py \
        -o "$out_dir" \
        --catapult_shell Perlmutter_scripts/catapult_shell.sh \
        --flow_tcl util/catapult_hls4ml_flow.tcl \
        --license_config license_servers_perlmutter.json \
        --flow_config_json "$flow_cfg" \
        --gen_model_config_json "$model_cfg" \
        --cartesian \
        --slurm --slurm-qos express_amsc --slurm-time 06:00:00 \
        --slurm-parallelism 16 --slurm-mem-per-job 16G
}
