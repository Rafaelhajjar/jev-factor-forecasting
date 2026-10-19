# Completed plain-forest controls: AR+RF agrees, one RF-MAF seed misses

Completed and independently audited October 19, 2026. All three AR+RF seeds are within the declared tolerance of the published unemployment cell. RF-MAF passes for two seeds and misses for seed 303. **The combined control criterion fails; the main FA-ARRF replication also remains unresolved.**

## What did we get?

Every method forecasts the same 48 target dates, 2003Q1–2014Q4, in delta-log unemployment units. The unchanged AR(4) denominator has RMSE 0.0334997102. Lower ratios mean lower forecast error.

| Method | RMSE | RMSE / AR(4) | Printed source ratio | Within 0.03 |
| --- | ---: | ---: | ---: | --- |
| RF-MAF, seed 101 | 0.0278175467 | 0.830382 | 0.85 | Yes |
| RF-MAF, seed 202 | 0.0276238291 | 0.824599 | 0.85 | Yes |
| RF-MAF, seed 303 | 0.0296502898 | 0.885091 | 0.85 | No |
| AR+RF, seed 101 | 0.0285161361 | 0.851235 | 0.84 | Yes |
| AR+RF, seed 202 | 0.0273152732 | 0.815388 | 0.84 | Yes |
| AR+RF, seed 303 | 0.0277154509 | 0.827334 | 0.84 | Yes |
| RF-MAF mean prediction | 0.0282283888 | 0.842646 | Not a source ensemble | Excluded |
| AR+RF mean prediction | 0.0277440511 | 0.828188 | Not a source ensemble | Excluded |
| AR(2) filter alone | 0.0336895427 | 1.005667 | Not a Table 4 cell | Diagnostic only |

The source ratios are the unemployment h=1 cells in appendix Table 4 of [Goulet Coulombe (2024)](https://doi.org/10.1002/jae.3030). Our absolute-ratio tolerance of 0.03 is a project diagnostic, not an author standard or statistical test. Source significance stars do not transfer to these estimates.

RF-MAF seed 303 differs from 0.85 by +0.035091. The fixed rule requires all six individual control/model seed cells, so five passes are insufficient. Both mean-prediction ensembles are retained but excluded from that rule. No seed is discarded or rerun to obtain a pass.

All these control seeds have higher RMSE than the preserved original FA-ARRF seeds, whose ratios are 0.797325–0.806346. That descriptive ordering supports retaining them as serious conventional controls. It does not establish statistical significance, Jev's value, the missing author pipeline or the larger published nonlinear gain.

## What exactly ran?

The [declaration](../docs/PLAIN_CONTROLS.md), [configuration](../configs/mrf_plain_controls.json) and runner were committed and pushed in **2e72a9fcb80a95767d72d1a987f06bd4c17d1172 before the actual-data pilot or full outcomes**. Earlier primary, ARRF and factor-preparation results were already known. This is a post-primary reconstruction, not a blind confirmation or a replacement selected by these losses.

Reuse the original all-248 primary matrices without changing any entry: 1,041 state columns, target masks, factor/indicator/MAF lags, trend, row order and forecast timing. Do not select the later PCA125 or FRED125 representation using its results.

RF-MAF fits a plain CART forest to that full rich state. AR+RF first fits an intercept plus AR(2) on the training window, fits the same forest type to training residuals, then adds the AR forecast back. All scaling and coefficients use training rows only. The AR(2)-only prediction is separately labeled, not presented as a source table cell.

Each control uses six expanding refits, 100 trees and seeds 101/202/303: 36 fits and 3,600 trees. The sampler follows the recorded random-group/quantile law with nominal block size eight and subsampling rate 0.75. CART uses one-third candidate features, minimum parent 10, minimum leaf one and no pruning. Leaves average sampled rows only; no MRF regularization or full-training leaf refit is used.

The original plain-RF backend and exact per-table settings remain unknown. NumPy random streams are not historical R seed equivalence; scikit-learn 1.9.1 uses float32 feature routing and its own valid-split convention. Those are explicit reconstruction boundaries, not details inferred from a matching score. No Jev, LLM or hosted forecasting call was made.

## What is verified?

The [full audit](mrf-plain-controls-audit.json) repeats the original primary artifact audit, checks all six unchanged matrices and independently recalculates the AR(2) coefficients, predictions and training residuals in base R. Their maximum differences are below 6.7e-16. It verifies the exact model/refit/seed grid, source/backend hashes and forecast dates.

For every forest, it reconstructs the sampled-node means from training data, traverses the saved JSON trees, checks prediction averaging and inverse scaling, and **deterministically refits the complete forest**. All 36 saved structures agree. Maximum node-mean error is 1.4e-15 in standardized units; maximum forecast reconstruction error is 2.1e-17 in original units. Saved aggregates, metrics and the failed control criterion are independently recalculated.

Final manifest SHA-256: 8cd5a4a42b870dd69ce11e3587e4eb5c6f9de09a2ef971bfd9bea887d80d4255.

- [Metrics](mrf-plain-controls-metrics.csv): all 15 original-reference/control/diagnostic methods.
- [Predictions](mrf-plain-controls-predictions.csv): 720 rows, 48 per method, including origin/target dates and actual outcomes.
- [Result record](mrf-plain-controls-result.json): every job's hashes, arithmetic checks and source-cell comparisons.
- [Pilot audit](mrf-plain-controls-pilot-audit.json): two trees per control on eight dates, integrity only, with accuracy scores suppressed.

All 320 local tests pass, including 17 real-R checks. The original primary and all earlier sensitivity numerical artifacts remain unchanged. TV-FAAR and NN quarterly comparisons, exact source reconciliation, the published nonlinear-gain milestone and prequential Jev/LLM development remain open.
