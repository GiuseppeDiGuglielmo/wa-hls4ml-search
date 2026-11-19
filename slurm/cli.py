"""Argparse group for the SLURM job array submission flags.

Used by iter_manager_catapult.py to add --slurm and friends to its parser.
Defaults come from slurm/defaults.json (job_array); every one is a flag.
"""

from slurm import site_config


def _d(key):
    return site_config.default("job_array", key)


def add_slurm_args(parser):
    """Add --slurm* + --collect-slurm flags to an argparse parser.

    Args:
        parser: argparse.ArgumentParser instance to extend.
    """
    parser.add_argument(
        '--slurm', action='store_true', default=False,
        help='Use SLURM job array instead of GNU parallel',
    )
    parser.add_argument(
        '--slurm-account', type=str, default=site_config.ACCOUNT,
        help='NERSC project account (default: %s, from slurm/site.json)' % site_config.ACCOUNT,
    )
    parser.add_argument(
        '--slurm-time', type=str, default=_d('time'),
        help='Walltime per task (default: %(default)s)',
    )
    parser.add_argument(
        '--slurm-qos', type=str, default=_d('qos'),
        help='SLURM QOS (default: %(default)s; '
             'options: debug, regular, shared, premium, express_amsc)',
    )
    parser.add_argument(
        '--slurm-constraint', type=str, default=_d('constraint'),
        help='Node constraint (default: %(default)s)',
    )
    parser.add_argument(
        '--collect-slurm', type=str, default=None, metavar='RUN_DIR',
        help='Skip synthesis, collect reports from a completed SLURM run',
    )
    parser.add_argument(
        '--slurm-parallelism', type=int, default=_d('parallelism'),
        help='Syntheses to run in parallel per node (default: %(default)s)',
    )
    parser.add_argument(
        '--slurm-mem-per-job', type=str, default=_d('mem_per_job'),
        help='RAM to reserve per synthesis (default: %(default)s)',
    )
    parser.add_argument(
        '--slurm-cpus-per-job', type=int, default=_d('cpus_per_job'),
        help='CPUs to reserve per synthesis (default: %(default)s)',
    )
