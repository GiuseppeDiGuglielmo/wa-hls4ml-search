import os
import re
import csv
import json
import logging

import yaml

logger = logging.getLogger(__name__)


def parse_catapult_report(output_dir):
    if not os.path.exists(output_dir):
        logger.error(f'Output directory {output_dir} does not exist.')
        return None

    config = _load_config(output_dir)
    if config is None:
        logger.error(f'No config file found in {output_dir}.')
        return None

    project_dir = config.get('ProjectDir') or (config.get('ProjectName', 'myproject') + '_prj')
    project_name = config.get('ProjectName', 'myproject')

    report = {}
    report['Config'] = config

    sln_dir, attempts = _find_project_attempt(output_dir, project_dir, project_name)
    if sln_dir is None:
        logger.error(f'Project directory {os.path.join(output_dir, project_dir)} does not exist.')
        return report
    if len(attempts) > 1:
        # Retries leave earlier, often interrupted, attempts next to the one used.
        report['ProjectAttempts'] = {'used': os.path.basename(sln_dir),
                                     'found': [os.path.basename(a) for a in attempts]}

    ver_dir = _find_latest_solution(sln_dir, project_name)
    if ver_dir is None:
        logger.error(f'No solution versions found in {sln_dir}.')
        return report

    csim_file = os.path.join(output_dir, 'tb_data', 'csim_results.log')
    if os.path.isfile(csim_file):
        with open(csim_file) as f:
            report['CSimResults'] = [line.split() for line in f]

    qofr_file = os.path.join(ver_dir, 'nnet_qofr.csv')
    if os.path.isfile(qofr_file):
        report['QOFRSummary'] = _parse_qofr_csv(qofr_file)

    rtl_rpt_file = os.path.join(ver_dir, 'rtl.rpt')
    if os.path.isfile(rtl_rpt_file):
        report['AreaReport'] = _parse_rtl_rpt_area(rtl_rpt_file)
        report['DesignSummary'] = _parse_rtl_rpt_design_summary(rtl_rpt_file)

    layer_csv = os.path.join(ver_dir, 'nnet_layer_results.csv')
    if os.path.isfile(layer_csv):
        report['LayerResults'] = _parse_layer_results_csv(layer_csv)

    layer_summary_csv = os.path.join(output_dir, 'firmware', 'layer_summary.csv')
    if os.path.isfile(layer_summary_csv):
        report['LayerSummary'] = _parse_layer_summary_csv(layer_summary_csv)

    # Vivado RTL synth reports (only present when RTLSynth=1)
    util_rpt = os.path.join(ver_dir, 'vivado_concat_v', 'utilization_synth.rpt')
    if os.path.isfile(util_rpt):
        report['UtilizationReport'] = _parse_utilization_report(util_rpt)

    timing_rpt = os.path.join(ver_dir, 'vivado_concat_v', 'timing_summary_synth.rpt')
    if os.path.isfile(timing_rpt):
        report['TimingReport'] = _parse_timing_report(timing_rpt)

    return report


def read_catapult_report(output_dir, full_report=False):
    report = parse_catapult_report(output_dir)
    if report is None:
        return


def _load_config(output_dir):
    """Try cat_ai_nn_config_final.json first, fall back to hls4ml_config.yml."""
    json_path = os.path.join(output_dir, 'cat_ai_nn_config_final.json')
    if os.path.isfile(json_path):
        with open(json_path) as f:
            return json.load(f)

    yml_path = os.path.join(output_dir, 'hls4ml_config.yml')
    # print("Looking for config in", yml_path)
    if os.path.isfile(yml_path):
        with open(yml_path) as f:
            return yaml.safe_load(f)

    return None


def _find_project_attempt(output_dir, project_dir, project_name):
    """Pick the Catapult project folder to report from.

    Each rerun of a design in the same output_dir makes a new project folder next
    to the old one (Catapult, Catapult_1, Catapult_2, ...). The first one is often
    an attempt cut off by the job time limit, so reading only `project_dir` reports
    a finished design as failed. Return the newest attempt whose latest solution
    has QoR results (nnet_qofr.csv), else the newest attempt with any solution,
    else the newest folder; plus all attempt folders, oldest first.
    """
    pattern = re.compile(re.escape(project_dir) + r'(?:_(\d+))?$')
    attempts = []
    if os.path.isdir(output_dir):
        for d in os.listdir(output_dir):
            m = pattern.match(d)
            if m and os.path.isdir(os.path.join(output_dir, d)):
                attempts.append((int(m.group(1) or 0), os.path.join(output_dir, d)))
    attempts = [path for _, path in sorted(attempts)]
    if not attempts:
        return None, []

    with_solution = []
    for path in reversed(attempts):
        ver_dir = _find_latest_solution(path, project_name)
        if ver_dir is None:
            continue
        if os.path.isfile(os.path.join(ver_dir, 'nnet_qofr.csv')):
            return path, attempts
        with_solution.append(path)
    return (with_solution[0] if with_solution else attempts[-1]), attempts


def _find_latest_solution(sln_dir, project_name):
    """Return full path to the highest-numbered {project_name}.vN dir, or None."""
    if not os.path.isdir(sln_dir):
        return None

    prefix = project_name + '.v'
    versions = []
    for d in os.listdir(sln_dir):
        if d.startswith(prefix) and os.path.isdir(os.path.join(sln_dir, d)):
            suffix = d[len(prefix):]
            try:
                versions.append((int(suffix), d))
            except ValueError:
                continue

    if not versions:
        return None

    versions.sort(key=lambda x: x[0])
    return os.path.join(sln_dir, versions[-1][1])


def _parse_qofr_csv(csv_path):
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        row = next(reader)
        return {
            'total_area': float(row['total_area']),
            'latency_cycles': int(row['latency_cycles']),
            'thruput_cycles': int(row['thruput_cycles']),
        }


def _parse_layer_results_csv(csv_path):
    layers = []
    with open(csv_path) as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            layer = {}
            layer['Layer'] = row.get('Layer', '').strip()
            if not layer['Layer']:
                continue
            layer['Unroll'] = row.get('Unroll', '').strip()
            for field in ['II', 'Latency', 'Thruput']:
                val = (row.get(field) or '').strip()
                if val:
                    try:
                        layer[field] = int(val)
                    except ValueError:
                        layer[field] = val
            for field in ['Area', 'TotalPwr', 'DynPwr', 'LeakPwr']:
                val = (row.get(field) or '').strip()
                if val:
                    try:
                        layer[field] = float(val)
                    except ValueError:
                        layer[field] = val
            layers.append(layer)
    return layers


def _parse_layer_summary_csv(csv_path):
    layers = []
    with open(csv_path) as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            layer = {k: v.strip() if isinstance(v, str) else v for k, v in row.items()}
            if layer.get('Layer Name'):
                layers.append(layer)
    return layers


def _parse_rtl_rpt_area(rtl_rpt_file):
    """Extract Post-Assignment area scores from the 'Area Scores' section of rtl.rpt."""
    area = {}
    labels = {
        'Total Area Score:': 'TotalAreaScore',
        'Total Reg:': 'TotalReg',
        'DataPath:': 'DataPath',
        'MUX:': 'MUX',
        'FUNC:': 'FUNC',
        'LOGIC:': 'LOGIC',
        'BUFFER:': 'BUFFER',
        'MEM:': 'MEM',
        'ROM:': 'ROM',
        'REG:': 'REG',
        'FSM:': 'FSM',
    }

    try:
        in_area_section = False
        with open(rtl_rpt_file) as f:
            for line in f:
                if 'Area Scores' in line and 'Post' not in line:
                    in_area_section = True
                    continue
                if not in_area_section:
                    continue
                if 'Register-to-Variable' in line:
                    break

                stripped = line.strip()
                for label, key in labels.items():
                    if stripped.startswith(label):
                        nums = re.findall(r'[\d]+\.[\d]+', line)
                        if nums:
                            area[key] = float(nums[-1])
                        break
    except Exception as e:
        logger.warning(f'Failed to parse area from rtl.rpt: {e}')

    return area


def _parse_rtl_rpt_design_summary(rtl_rpt_file):
    summary = {}
    try:
        with open(rtl_rpt_file) as f:
            for line in f:
                if 'Design Total:' in line:
                    parts = line.split('Design Total:')[1].split()
                    if len(parts) >= 4:
                        summary['real_ops'] = int(parts[0])
                        summary['latency'] = int(parts[1])
                        summary['throughput'] = int(parts[2])
                        summary['reset_length'] = int(parts[3])
                    if len(parts) >= 5:
                        summary['ii'] = int(parts[4])
                    break
    except Exception as e:
        logger.warning(f'Failed to parse design summary from rtl.rpt: {e}')

    return summary


def _parse_utilization_report(util_rpt_file):
    util = {}
    idx = 0
    with open(util_rpt_file) as f:
        for line in f:
            if '|' in line:
                if ('CLB LUTs' in line) and (idx == 0):
                    idx += 1
                    util['LUT'] = line.split('|')[2].strip()
                elif ('CLB Registers' in line) and (idx == 1):
                    idx += 1
                    util['FF'] = line.split('|')[2].strip()
                elif ('RAMB18 ' in line) and (idx == 2):
                    idx += 1
                    util['BRAM_18K'] = line.split('|')[2].strip()
                elif ('DSPs' in line) and (idx == 3):
                    idx += 1
                    util['DSP48E'] = line.split('|')[2].strip()
                elif ('URAM' in line) and (idx == 4):
                    idx += 1
                    util['URAM'] = line.split('|')[2].strip()
    return util


def _parse_timing_report(timing_rpt_file):
    timing = {}
    try:
        with open(timing_rpt_file) as f:
            for line in f:
                if re.search('WNS', line):
                    next(f)  # skip header separator
                    result = next(f).split()
                    timing['WNS'] = float(result[0])
                    timing['TNS'] = float(result[1])
                    timing['WHS'] = float(result[4])
                    timing['THS'] = float(result[5])
                    timing['WPWS'] = float(result[8])
                    timing['TPWS'] = float(result[9])
                    break
    except Exception as e:
        logger.warning(f'Failed to parse timing report: {e}')

    return timing
