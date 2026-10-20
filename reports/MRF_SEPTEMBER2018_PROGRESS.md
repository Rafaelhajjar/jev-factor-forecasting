# Qualified September 2018 MRF: full run launched

October 20, 2026 launch snapshot, not a live completion claim. The user explicitly
authorized this qualified reconstruction after the raw-RF criterion missed.
The failed RF diagnostic and missing original series/caller remain explicit.

## What is running?

- All 18 native author-engine fits: six two-year refits times seeds 101/202/303.
- 100 trees per fit, 48 target quarters, delta-log unemployment h=1.
- The same September archive, raw preparation, origin/target dates and AR(4)
  denominator as the completed RF run.
- A 1,037-column rich state and five-coefficient equation, not raw RF's feature
  set or ranger's 500-tree/min.node.size=3 settings.
- Six local workers, with no Jev or LLM forecasting calls.

At the initial input audit, **0/18 full fits were completed**. Full accuracy,
linear scores and source-cell comparisons are suppressed until every declared
case has completed and verified. This dated record must not be read as live
progress after the run finishes.

## What already passed?

The [two-tree native preflight](mrf-september2018-pilot-audit.json) completed
one seed/window and passed artifact checks. Its five coefficients reconstruct
the predictions within 9.1e-17. Its forecast accuracy is deliberately suppressed.
No parameter was changed using pilot losses.

The [initial full-input audit](mrf-september2018-initial-audit.json) rebuilds
all six states with **zero difference** and verifies exact raw-RF pairing.
Independent base-R QR versus Python forecast differences are below 1.5e-15;
the AR(4) predictions agree with those used for the frozen RF comparison.
All 477 local tests pass, including actual R MRF/TVP/ranger and optional neural
checks; 11 new checks cover the September MRF integration and report guard.

## What happens next?

The launched `execute` command automatically fits, checkpoints, audits the
complete grid and writes these local artifacts in `runs/mrf-september2018-v1/`:

- `result.md`: completed result only after the full audit succeeds.
- `audit.json`: complete verification and diagnostic outcome.
- `predictions.csv` and `metrics.csv`: 48 dates per method, matching comparators
  and each forest seed retained individually.

The local `result.md` initially displays a running placeholder. It is replaced
only after successful full verification. No additional chat turn is required
to trigger that audit. A failed native job/audit raises an error; do not treat
an old placeholder, partial output or absent error message as success.
Publication of the final research interpretation is separate; no automatic
external email, Git push or scheduled monitoring has been created.

The current state is in the local run's `manifest.json`. To resume after an
interruption, use the same declared `execute` command; existing completed jobs
must match their checksums. Do not alter frozen integration code mid-run.

Declaration commit: `561d00b52911e5ac5f7726d21c3ebb78ff1ae22d`, before the first
new-vintage native forecast outcome. [Full protocol](../docs/SEPTEMBER2018_MRF.md),
[configuration](../configs/mrf_september2018.json). Earlier results are unchanged.
