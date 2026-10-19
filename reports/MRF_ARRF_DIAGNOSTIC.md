# Completed ARRF unemployment diagnostic

Completed and audited October 19, 2026. This named comparator now numerically agrees with the paper under our declared diagnostic tolerance. The primary **FA-ARRF replication remains unsuccessful**; ARRF is a different model and cannot close that requirement.

## Result

| Model | Forecasts | RMSE | RMSE / AR(4) | Published ratio |
| --- | ---: | ---: | ---: | ---: |
| ARRF, seed 101 | 48 | 0.0299018061 | 0.892599 | 0.90 |
| ARRF, seed 202 | 48 | 0.0299630207 | 0.894426 | 0.90 |
| ARRF, seed 303 | 48 | 0.0302126367 | 0.901878 | 0.90 |
| Mean ARRF prediction | 48 | 0.0299932625 | 0.895329 | Not a source ensemble |

The source is the unemployment h=1 ARRF cell in appendix Table 4 of [Goulet Coulombe (2024)](https://doi.org/10.1002/jae.3030). All three individual seeds are within the predeclared 0.03 absolute-ratio tolerance. The ensemble is labeled separately and excluded from that pass rule. This is numerical agreement, not a statistical test or proof of the missing original pipeline.

For context, the unchanged fixed FA-AR ratio is 0.812577 and the original FA-ARRF seeds are 0.797325, 0.804184 and 0.806346. Their published counterparts are 0.83 and 0.72. Thus the forest with explicit factor terms still has a substantial source discrepancy, despite matching this simpler comparator. The original result and its failed criterion have not been replaced.

## What was held fixed

The [declaration](../configs/mrf_arrf_diagnostic.json) was committed before the full ARRF outcomes. All six original rich-state matrices were reused byte-for-byte, including their PCA and moving-average-factor state columns. ARRF removes the two factors only from the explicit equation, leaving an intercept and two target lags. It does not remove factor information from the forest state.

The experiment used the same archived data, delta log UNRATE target, 2003Q1–2014Q4 target dates, expanding estimates, six two-year refits, 100 trees and seeds 101/202/303. The author engine and independent R adapter were unchanged. All other effective input settings were inherited. The package's dimension-dependent guard naturally leaves ARRF's nominal minimum parent size at 10 rather than FA-ARRF's effective 12; prior vectors likewise follow the unchanged OLS-prior rule. This is the named paper comparator, not a controlled factor-removal treatment holding model capacity fixed.

All 18 jobs completed. The [separate artifact audit](mrf-arrf-diagnostic-audit.json) rechecked the primary source, input/settings provenance, complete date/seed grid, saved outputs and runtimes, coefficient decompositions, aggregated forecasts, saved metrics and the result record. Maximum forecast/coefficient discrepancy is 6.3e-16. The checker reuses the declared aggregation routine; it is not an independent re-estimation of the forest or recovery of the author pipeline.

## Artifacts

- [Metrics CSV](mrf-arrf-diagnostic-metrics.csv): ARRF seeds/ensemble plus the unchanged reference methods, rescored from saved forecasts.
- [Predictions CSV](mrf-arrf-diagnostic-predictions.csv): 480 rows, comprising 48 dates for each of ten methods including the separately labeled ensembles.
- [Audit JSON](mrf-arrf-diagnostic-audit.json): all 18 jobs verified; ARRF diagnostic tolerance passes; FA-ARRF replication and exact author-pipeline recovery explicitly remain false.

Reference methods are rescored from their CSVs, so last-bit floating-point differences from the original metrics record are possible; no original forecast or metric file was modified. The original [FA-ARRF report](MRF_UNEMPLOYMENT_RECONSTRUCTION.md) remains the primary record.

All 110 local tests passed, including seven real-R checks. There have been no hosted Jev/LLM forecasting calls. R runtime is 4.6.1 with pracma 2.4.6. The earlier two-tree pilot remains execution evidence only.

## Implication and next investigation

The ARRF match provides a useful check on this pipeline, but does not identify a unique cause of FA-ARRF's gap. Shared preprocessing can still differ, and the two equations interact differently with the forest's regularization and partitioning.

The [basis audit](../docs/PCA_BASIS_AUDIT.md) identifies a concrete R/Python orientation difference and verifies that the pinned engine can respond to a consistent sign reversal. A carefully declared coordinate-only sensitivity is a justified next investigation: preserve all information and inputs except those recorded signs, retain all seeds/results and never select signs by test RMSE. It would quantify portability, not establish the author's original R build or basis. No orientation-based replacement or score is claimed here.

Exact source preprocessing, per-table invocation and the other Table 4 comparators remain open. The full unemployment replication goal is not marked complete.
