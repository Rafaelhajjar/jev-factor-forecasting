# Unemployment benchmark: all named E1 methods run, reproduction unresolved

Updated October 19, 2026. All eight named E1 methods have now been implemented and run on the same fixed archived vintage, 48 target quarters (2003Q1–2014Q4), delta-log unemployment and original all-248 preparation. This is an independent reconstruction, not execution of the missing original table runner. Each linked report records its assumptions and full artifacts.

| Method | Printed RMSE / AR(4) | Reconstruction, seeds 101 / 202 / 303 where applicable | Diagnostic outcome |
| --- | ---: | --- | --- |
| AR(4) | 1.00 | 1.000000 by definition | Denominator, not independent source-cell validation |
| [Fixed FA-AR](MRF_UNEMPLOYMENT_RECONSTRUCTION.md) | 0.83 | 0.812577 | Within tolerance |
| [FA-ARRF](MRF_UNEMPLOYMENT_RECONSTRUCTION.md) | 0.72 | 0.797325 / 0.804184 / 0.806346 | All miss; primary criterion fails |
| [RF-MAF](MRF_PLAIN_CONTROLS.md) | 0.85 | 0.830382 / 0.824599 / 0.885091 | Seed 303 misses |
| [ARRF](MRF_ARRF_DIAGNOSTIC.md) | 0.90 | 0.892599 / 0.894426 / 0.901878 | All within tolerance |
| [AR+RF](MRF_PLAIN_CONTROLS.md) | 0.84 | 0.851235 / 0.815388 / 0.827334 | All within tolerance |
| [TV-FAAR](MRF_TVP_FAAR.md) | 1.19 | 0.942195, native fixed-seed CV | Miss; all six GARCH optimizers non-converged |
| [NN](MRF_NN.md) | 0.80 | 0.793326 / 0.842565 / 0.801268 | Seed 202 misses |

Source: appendix Table 4 of [Goulet Coulombe (2024)](https://doi.org/10.1002/jae.3030), PDF page 31, printed page 70. Absolute-ratio tolerance is 0.03, fixed by this project, not an author criterion or a significance test. All individual declared seed models must pass; separately labeled mean-prediction ensembles cannot rescue a miss. NN's ten-member forecast ensemble is inside each reported seed; TV-FAAR's native deterministic procedure is not artificially triplicated.

## What can we conclude?

The pipeline produces forecasts with audited timing, input reconstruction and numerical artifacts. Several conventional controls approach the source cells. That does **not** establish the missing original preparation, model invocations, historical dependencies or FA-ARRF nonlinear gain. In the primary reconstruction, the forest improves on its own matching fixed-factor comparator by only 0.77%–1.88%, not the roughly 13.3% implied by 0.72 versus 0.83.

The [R-sign](MRF_R_BASIS_SENSITIVITY.md), [PCA125](MRF_PCA125_SENSITIVITY.md) and [FRED125](MRF_FRED125_SENSITIVITY.md) sensitivities remain separate, explicitly qualified checks. None satisfies the full matching-comparator/all-seed criterion. They do not replace the original primary, and old linear scores must not be combined with changed-factor forests.

The separate [native-helper forecast diagnostic](MRF_NATIVE_HELPER_DIAGNOSTIC.md) is also complete: all 18 cases and unchanged 48 dates, with ratios 0.799509/0.811123/0.808302 versus 0.72. All miss and are slightly worse than their original pairs. The matching fixed FA-AR is still 0.812577. Independent full artifact checks and base-R rescoring pass; the joint source-cell criterion does not. Future block covariates make this explicitly non-causal, not a new primary. This interface change does not close the gap in this reconstruction.

Remaining source-backed questions include original PCA eligibility/completion/orientation, the actual normalization/table invocation, exact OLS-prior choices and historical runtime. The author request remains a route to resolving those unknowns; settings must not be searched merely until 0.72 appears. TVP optimizer quality also remains open and must not be ignored to claim a later Jev advantage.

The next experiment stages remain controlled mechanisms and prequential selector development, followed by matched Jev/LLM testing only under a frozen protocol and declared hosted-call budget. Independent tooling can use the preserved qualified baseline, but must not call it a successfully replicated paper result. No empirical Jev advantage has been established.
