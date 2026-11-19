# `slurm/repairs/` — one-off repairs

Tools that fix runs made under conditions that no longer hold. A healthy sweep
does not need them. Each one plans by default and writes only with `--apply`.

| Tool | make target | Why it exists | When it can go |
|---|---|---|---|
| `reparse.py` | `make reparse RUN= [APPLY=1]` | Before deea396b, `catapult_report.py` read only the first Catapult attempt, so designs whose QoR came from a `Catapult_N` retry folder were reported as failed. It rewrites those reports and tarballs from the retry folder, without new synthesis. | When no scratch or archived run predates deea396b with unreparsed designs (`make reparse` lists none). |
| `rebuild_from_archive.py` | `make rebuild-archived RUN=<name> [APPLY=1]` | The archive keeps reports and tarballs, not the model or flow config a rerun needs. For a run whose scratch folder was purged it rebuilds both for the failed designs, so `rerun-failed` works on it. | When no archived run has failed designs worth rerunning. |

`rerun-failed` and `design-synth` are not repairs: they are part of normal
operation and stay in `slurm/tools/`.

Removed 2026-11-18: `run_rerun_from_archive.sh` (superseded by
`rebuild-archived` + `rerun-failed`; it deleted the scratch run's files unless
`KEEP_SCRATCH=1`) and `populate_failed_designs.py` (wrote `failed_designs.txt`
into the shared archive; `make check-run`, `dataset-summary` and the archive's
`check_dataset.py` report the same facts). Both are in git history.
