# Native TV-FAAR completed: source cell missed, optimizer warnings retained

Completed and independently audited October 19, 2026. The native author estimator produces an unemployment h=1 RMSE/AR(4) ratio of **0.942195 versus the printed 1.19**. It misses the declared tolerance. **All six GARCH fits report non-convergence code 1.** Complete execution and matching arithmetic do not establish a converged TVP benchmark or exact replication.

## What did we get?

All methods use the same 48 target dates, 2003Q1–2014Q4, in delta-log unemployment units. This is the fixed archived vintage, not reconstructed historical release availability.

| Method | RMSE | RMSE / AR(4) | Printed source ratio |
| --- | ---: | ---: | ---: |
| AR(4), unchanged denominator | 0.0334997102 | 1.000000 | 1.00 |
| Fixed FA-AR, unchanged | 0.0272211055 | 0.812577 | 0.83 |
| Original FA-ARRF mean prediction, separately labeled | 0.0268552416 | 0.801656 | Not a source ensemble |
| Native TV-FAAR, six refits | 0.0315632545 | 0.942195 | 1.19 |

The printed TV-FAAR cell is unemployment h=1 in appendix Table 4 of [Goulet Coulombe (2024)](https://doi.org/10.1002/jae.3030). The difference is -0.247805, outside the absolute-ratio tolerance of 0.03. That tolerance is our predeclared diagnostic, not an author standard or statistical test. Lower error than the printed cell does not count as reproducing it, and no source significance stars are transferred.

In this reconstruction, the TVP forecast improves modestly on AR(4), but is worse than both its matching fixed-factor comparator and every original FA-ARRF seed. This is descriptive evidence only. The optimizer warnings further limit interpretation; a future Jev comparison must not claim an advantage by relying only on a non-converged conventional baseline.

## What exactly ran?

The [declaration](../docs/TVP_FAAR_CONTROL.md), [configuration](../configs/mrf_tvp_faar.json) and complete runner were committed and pushed in **4ac7d315c3f63a17c9bd30ebe03d7f6ca14fc3db before the actual-data pilot or full outcomes**. Earlier primary and control losses were already public. This is a post-primary independent reconstruction, not a blind confirmation or a test-loss-selected replacement.

Main Table 2 specifies nine coefficients: intercept, four target lags and two lags of each of two factors. Reuse those exact eight regressor columns from the original all-248 primary matrices. Pass only training outcomes to the external TVP estimator. Retain all six expanding two-year refits and freeze each estimated endpoint coefficient within its eight-quarter forecast block. This follows the forecasting section's cadence, not a single 2007Q2 fit or full-sample smoothing. The interpretation footnote and missing historical table caller remain qualified.

Run the author's external GPL-3 TVP source at commit d2d52bb9e0126fb580fb8301f305035d3047b4b2 with its declared defaults: two-step ridge, five random folds, 15 exp(-6) to exp(20) candidates, initial-level penalty 0.1, weight exponents 0.75, zero-level prior and second-stage retuning. The native functions fix their CV seed to 1071; we do not fabricate a three-seed ensemble from this deterministic procedure. Random within-training CV is not the chronological validation required for our later extension.

Both actual tuning stages were captured, rather than assuming the public lambda return described the final fit:

| Refit endpoints | First-stage lambda | Final-stage lambda | GARCH code |
| --- | ---: | ---: | ---: |
| 2002Q4, 2004Q4 | 171.204225 | 171.204225 | 1 in both |
| 2006Q4, 2008Q4 | 7,024.384377 | 7,024.384377 | 1 in both |
| 2010Q4, 2012Q4 | 44,994.057941 | 7,024.384377 | 1 in both |

For the final two refits, the public lambda field still reports 44,994.057941 even though the final model uses 7,024.384377. Logging only that field would misdescribe the forecast. Read-only instrumentation records the actual selections without editing the source or changing its calculations.

The native code continues after the GARCH optimizer warning; our adapter preserves that behavior and exposes every code. No retry, fallback optimizer, replacement weights, seed search or setting change was used to repair the score. Reproducing a returned fit does not prove that likelihood optimization converged. Nor can these warnings be asserted to explain the published-cell discrepancy or the separate FA-ARRF gap: original invocation, preprocessing and historical dependency versions remain unknown.

## What is verified?

The [full audit](mrf-tvp-faar-audit.json) repeats the entire primary artifact audit and verifies all six unchanged original inputs, equation-row equality, target/origin timing, source/configuration/runtime hashes and all 48 dates. Independent integrated-random-walk covariance calculations reconstruct both coefficient paths, fitted values and forecasts; separate time-covariance calculations reproduce both native CV score tables, minima, weight updates and the GARCH variance recursion.

Maximum standardized coefficient discrepancy is 1.4e-13, maximum recorded CV-score discrepancy 3.5e-12 and maximum standardized forecast discrepancy 3.7e-13. Those checks establish arithmetic agreement, not optimizer convergence. The final auditor then **reruns every full native fit** in isolated scratch directories: all saved numerical artifacts, folds, CV tables and tuning metadata reproduce identically. It independently recalculates aggregates, metrics and the failed source-cell flag.

Final manifest SHA-256: 05b5683998426073ba421d14f62bb0ac6e6a2c66412e09f7e5dd64d5d59ac69f.

- [Metrics](mrf-tvp-faar-metrics.csv): all seven unchanged-reference/new-control methods.
- [Predictions](mrf-tvp-faar-predictions.csv): 336 rows, 48 per method, with target/origin dates and actual outcomes.
- [Result record](mrf-tvp-faar-result.json): both tuning stages, every optimizer code, runtime versions and numerical checks.
- [Pilot audit](mrf-tvp-faar-pilot-audit.json): one refit/eight dates, with accuracy scores suppressed and its optimizer warning retained.

All 370 local tests pass, including 25 actual-R contracts; the source-declaration commit's GitHub checks also passed. Direct native dependencies are pinned, and every fit records all loaded namespace versions. This is the current R 4.6.1/fGarch 4052.93 environment, not a recovered historical author environment.

The original primary and all earlier numerical artifacts are unchanged. Minor last-bit differences in copied reference metrics arise from rescoring saved CSVs. Per-fit algebra records deliberately make no claim of a whole quarterly replication; the outer audit proves complete execution/integrity, while the printed-cell and optimizer-quality requirements remain unmet. NN was the remaining unimplemented E1 comparator at this completion; its [later completed comparison](MRF_NN.md) is separate. Exact source reconciliation, FA-ARRF's larger nonlinear gain and prequential Jev/LLM development remain open. No hosted forecasting calls were made.
