# Native-helper diagnostic completed: the unemployment gap remains

Completed and independently audited October 19, 2026. All **18 forests, 1,800 trees and 48 target dates** are verified. Native-helper FA-ARRF/AR(4) ratios are **0.799509, 0.811123 and 0.808302** versus the printed 0.72. Every seed misses the declared tolerance. Selecting the native helper behind the same adapter does **not** close the gap in this reconstruction.

## What did we get?

| Seed | Original training-only ratio | Native-helper ratio | Native-helper gain over matching FA-AR |
| --- | ---: | ---: | ---: |
| 101 | 0.797325 | 0.799509 | 1.608% |
| 202 | 0.804184 | 0.811123 | 0.179% |
| 303 | 0.806346 | 0.808302 | 0.526% |
| Separate mean-prediction ensemble | 0.801656 | 0.805532 | 0.867% |

The AR(4) denominator remains RMSE 0.0334997102. The matching fixed FA-AR remains RMSE 0.0272211055 and ratio **0.812577 versus 0.83**, within tolerance. Native-helper RMSEs for the three seeds are 0.0267833289, 0.0271723785 and 0.0270778841; the separate mean-prediction RMSE is 0.0269850908.

The source FA-ARRF cell is unemployment h=1 in appendix Table 4 of [Goulet Coulombe (2024)](https://doi.org/10.1002/jae.3030). Keep the original 0.03 absolute-ratio diagnostic, matching FA-AR and **every individual seed**. The mean ensemble cannot rescue a miss; it misses too. The joint criterion is false. The tolerance is ours, not an author standard or statistical test; source significance stars do not transfer.

Every native-helper seed has slightly higher RMSE than its original paired run: increases of 0.274%, 0.863% and 0.243%. These are descriptive paired results, not evidence of a statistically significant general disadvantage. Gains over the matching fixed FA-AR are only 0.18%–1.61%, not the roughly 13.3% implied by the printed 0.72/0.83 source cells.

## What exactly changed?

The [declaration](../docs/NATIVE_ALLROWS_DIAGNOSTIC.md), [configuration](../configs/mrf_native_allrows.json), paired wrapper and tests were committed and pushed in **785ea663373211e6c294696008f5766746dd949e before this diagnostic's actual-data outcomes**. Earlier losses and the initialization interaction were already known. No setting or seed was changed after its outcomes.

Keep the same all-248 preparation, every original 1,041-column state matrix byte, factor basis, linear forecasts, target/origin records, four-slope MRF equation, 100 trees and three seeds at each of six refits. Use the same pinned author engine, adapter/preparation code and recorded R 4.6.1/pracma 2.4.6 versions. Do not stack R signs, PCA125 or FRED125.

Only the inner helper selection changes. Both paths still mask every future target and apply the adapter's outer training-only standardization. The new path uses the literal native all-supplied-row helper and leaves its prior conversion untouched, including the documented intercept interaction. This is not an obtained original table caller or a simultaneous source correction.

Native moments include covariates from later origins within each eight-quarter block. The result is explicitly **non-causal**, not a deployable replacement baseline. Even a score match would not establish the original author's invocation. This negative paired result narrows the effect of this interface change; it does not prove that every possible preprocessing/normalization choice is irrelevant or explain the entire source discrepancy.

## What is verified?

The [fresh full audit](mrf-native-helper-audit.json) repeats the complete primary audit, checks every byte-identical pairing and independently reconstructs all six state matrices from the deposited archive. Maximum reconstruction difference is 3.6e-15. Independent base-R QR linear forecasts agree with Python within 1.5e-15.

All 18 completed outputs have finite original-unit coefficients/forecasts with decomposition discrepancies below 2.7e-15. Runtime versions match the primary. All 18 stderr logs are empty. The auditor recomputes dates, outcomes, aggregates, metrics, all-seed/source-cell flags and matching-comparator gains, then compares the saved result record. These are actual-engine artifact checks, not a claim of independently refitting every tree or recovering the missing original caller.

An additional independent base-R rescore of the published CSVs agrees on all six methods: RMSE and MAE differences below 3.5e-18, ratio differences below 1.2e-16. Independently regrouped seed predictions reproduce the labeled mean within 1.4e-17. All 288 forecast rows are retained, 48 per method.

Final manifest SHA-256: 7d404c198070b78b69cb73360ce183154fd572b64190515bddb9abdf24c63e5a.

- [Metrics](mrf-native-helper-metrics.csv).
- [All predictions](mrf-native-helper-predictions.csv).
- [Full result record](mrf-native-helper-result.json).
- [Pilot audit](mrf-native-helper-pilot-audit.json), with performance suppressed.
- [Initial](MRF_NATIVE_HELPER_PROGRESS.md) and [interim](MRF_NATIVE_HELPER_INTERIM.md) snapshots, preserved as dated integrity records rather than live status.

All **451 local tests** passed again after completion: 370 ordinary, 53 optional NN and 28 optional real-R contracts. The declaration commit's GitHub workflow also passed. Tests and artifact integrity do not turn the failed source-cell criterion into a pass.

All source/configuration choices and every earlier numerical artifact remain unchanged. No retry, fallback or outcome-guided revision was used. The original primary still fails; other preparation sensitivities and conventional controls keep their separate results. The remaining source questions concern the actual preparation, factor construction, priors and per-table invocation—not a license to search settings until 0.72 appears. No Jev/LLM forecast evaluation or hosted forecasting call has run.
