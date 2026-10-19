# Completed FRED125 sensitivity: joint replication still fails

Completed and independently audited October 19, 2026. The adaptive FRED preparation brings the matching fixed-factor regression within our declared tolerance. **Only one of three forest seeds passes, so the joint replication criterion still fails.** Every seed and the original primary result are retained.

## Did this preparation close the gap?

| Method | RMSE | RMSE / AR(4) | Printed source ratio | Within 0.03 |
| --- | ---: | ---: | ---: | --- |
| AR(4), unchanged | 0.0334997102 | 1.000000 | 1.00 | Reference |
| Fixed FA-AR, FRED125 | 0.0268574744 | 0.801723 | 0.83 | Yes |
| FA-ARRF FRED125, seed 101 | 0.0249997520 | 0.746268 | 0.72 | Yes |
| FA-ARRF FRED125, seed 202 | 0.0256715069 | 0.766320 | 0.72 | No |
| FA-ARRF FRED125, seed 303 | 0.0253723752 | 0.757391 | 0.72 | No |
| Mean forest prediction, separately labeled | 0.0252752891 | 0.754493 | Not a source ensemble | Excluded from seed rule |

Every method uses the same 48 target dates, 2003Q1–2014Q4, and delta-log unemployment units. Printed ratios are the unemployment h=1 cells in appendix Table 4 of [Goulet Coulombe (2024)](https://doi.org/10.1002/jae.3030), not project results. The absolute-ratio tolerance of 0.03 is our frozen diagnostic, not an author standard or a statistical test.

The new fixed FA-AR differs from 0.83 by -0.028277 and passes. Forest gaps from 0.72 are +0.026268, +0.046320 and +0.037391; seeds 202 and 303 fail. The rule requires the matching linear model and **every** individual seed. Selecting seed 101, reporting only an ensemble or mixing factor constructions cannot establish a pass.

The forest reduces RMSE over its **own** fixed-factor comparator by 6.92%, 4.42% and 5.53%. The separately labeled mean prediction reduces it by 5.89%. The printed source cells imply about 13.3%, so the larger published nonlinear gain remains unreproduced. These descriptive comparisons do not establish statistical significance or general superiority.

## What changed, and why?

The [declaration](../docs/FRED125_SENSITIVITY.md), [configuration](../configs/mrf_fred125_sensitivity.json) and runner were published in `dbd43380e6401c8810b2b9294b9508fc4330416d` before this variant's outcomes. Earlier primary, ARRF, R-sign and conditional PCA125 results were already known. This is a source-motivated development investigation, not a blind confirmation or test-loss-selected replacement.

Independently clean and complete the 125 metadata members using the public FRED jj=2/DEMEAN=2 recipe, selecting completion rank at every EM step, with maximum rank eight, 50 iterations and tolerance 1e-6. All six training windows converge; final completion ranks are 2/3/3/4/4/4. Then estimate five state PCs with the original Python orientation. The small forest equation still uses two factors. Forecast-origin rows use our explicitly separate frozen-basis, independent-row completion rule.

Replace only the 40 factor-lag columns. Preserve every original non-factor entry: all 248 indicator/MAF inputs, target masks, AR lags, trend, dates and ordering. The state remains 1,041 columns; the equation remains intercept + AR(2) + two factor terms. Refit the OLS prior in these coordinates with the same settings. This does not stack the R-sign experiment.

This is a composite preparation contrast, **not** a pure rank toggle: the completion panel and iteration policy change. The public driver is monthly FRED-MD; applying its functions quarterly and specifying a causal forecast-row extension do not recover the missing author runner. The original MATLAB functions were not executed. The independent R reconstruction cross-checks our port, not the original caller.

The external author engine ran all six original expanding refits, 100 trees and seeds 101/202/303: 18 jobs and 1,800 trees, using R 4.6.1 and pracma 2.4.6. All other forest settings are inherited from the primary run. No Jev, LLM or paid forecasting API call was made.

## Full verification and retained artifacts

The [full audit](mrf-fred125-sensitivity-audit.json) verifies all 18 jobs, with no jobs pending. It repeats the primary and independent-R FRED training audits, reconstructs all six matrices, verifies exact non-factor preservation, settings, origin/target timing, coefficients and saved aggregates, and recalculates the scores and failed joint criterion. Coefficient reconstruction error is below 1.4e-15; independent R/Python linear forecasts agree within 1.5e-15.

Final manifest SHA-256: `9729f5318571c3023a39ef67d2b03feb9de8648eccd2c1b06a49c13a1a1301b9`.

- [Metrics](mrf-fred125-sensitivity-metrics.csv): original and new matching linear models, every seed and separately labeled ensembles.
- [Predictions](mrf-fred125-sensitivity-predictions.csv): 528 rows, 48 per method, retaining target/origin dates and actual outcomes.
- [Result record](mrf-fred125-sensitivity-result.json): per-job hashes/runtime, paired changes against the original forest and gains over the new linear comparator.
- [Pilot/preparation record](MRF_FRED125_PROGRESS.md): historical integration checks, not live status or performance results.
- [Native initialization audit](mrf-fred125-native-initialization-audit.json): all six prepared matrices checked at the actual adapter/engine boundary, stopping before tree fitting.

The preparation/native reports bind the earlier prepared manifest; their hashes are not substituted for the final manifest above. Local progress snapshots are immutable partial checks, with scores suppressed. The last snapshot loaded an incomplete manifest and subsequently saw all output files; only the separate final audit establishes full verification. No existing primary or earlier sensitivity numerical artifact was edited. Minor last-bit differences in copied reference metrics arise from rescoring saved CSVs.

## What remains open?

This source-backed preparation choice does not reproduce the printed linear/nonlinear comparison jointly or identify the original author pipeline. Keep the original primary and all sensitivities, all seeds and the same tolerance. Do not turn the remaining discrepancy into a search over arbitrary ranks, panels, orientations or seeds to hit 0.72.

Exact processing/invocation reconciliation, the published nonlinear-gain milestone and the remaining Table 4 controls stay open. Independent extension work must retain the qualified-reconstruction label and still needs genuinely prequential development evidence and a frozen selector plan. No Jev benefit has been established.
