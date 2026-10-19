# Completed R-sign sensitivity: a change, not a replication

Completed and audited October 19, 2026. Using the recorded native-R PCA/MAF signs modestly improves all three paired forest runs, but **does not reproduce the paper's 0.72 ratio**. The original primary result remains unchanged.

## Question and result

Does an invertible coordinate change alter the pinned forest's forecast? Yes. Does this recorded R convention close our reconstruction gap? No.

| Run | Original FA-ARRF RMSE / AR(4) | R-signed FA-ARRF RMSE / AR(4) | Paired ratio change |
| --- | ---: | ---: | ---: |
| Seed 101 | 0.797325 | 0.786503 | -0.010821 |
| Seed 202 | 0.804184 | 0.783246 | -0.020939 |
| Seed 303 | 0.806346 | 0.799636 | -0.006710 |
| Mean prediction, separately labeled | 0.801656 | 0.788647 | -0.013009 |

Every method has 48 target dates, 2003Q1–2014Q4. The source is appendix Table 4's unemployment h=1 FA-ARRF ratio, 0.72, in [Goulet Coulombe (2024)](https://doi.org/10.1002/jae.3030). The individual R-signed seeds miss it by 0.0665, 0.0632 and 0.0796: all remain outside the previously declared 0.03 absolute-ratio tolerance. The mean-prediction ensemble is not the source model and cannot satisfy the individual-seed rule.

AR(4) and fixed FA-AR are unchanged: RMSE 0.0334997102 and 0.0272211055, respectively; fixed FA-AR/AR(4) is 0.812577 versus the source's 0.83. The largest absolute paired forecast changes are 0.01284, 0.01505 and 0.01015 in delta-log unemployment units. These are descriptive changes, not significance claims or evidence of forecast convergence.

## What was held fixed

The [declaration](../docs/R_BASIS_SENSITIVITY.md) and [configuration](../configs/mrf_r_basis_sensitivity.json) were committed in `6832ea4` before the full outcomes, after the original FA-ARRF and ARRF results were known. This is an explicitly post-primary diagnostic, not a blind confirmatory experiment.

All six matrices equal the original inputs multiplied only by the previously recorded cross-sectional-PC and MAF sign vectors. The archived values, information set, cleaning/completion, loadings, target/origin alignment, masked future targets, autoregressive terms, indicator lags, trend and all forest settings are unchanged. All eight lags of each cross-sectional component receive the same sign. The OLS-prior rule is refitted in the signed coordinates. Saved coefficients must be used with each job's signed matrix.

The unchanged author engine ran 100 trees at each of six refits for seeds 101/202/303: 18 jobs and 1,800 trees. Runtime was R 4.6.1 with pracma 2.4.6. There were no Jev, LLM or paid API calls, no search over signs, and no replacement of the primary result.

## Integrity and public artifacts

The independent [full audit](mrf-r-basis-sensitivity-audit.json) verifies all 18 jobs, recomputes the native R sign maps, checks exact signed-input equality, reconstructs the coefficient contributions and rescores every saved forecast. No jobs are pending. Maximum coefficient-reconstruction discrepancy is 2.7e-15. Across all six refits, Python SVD and independent base-R QR checks keep the linear forecasts within 1.5e-15 of the original values.

- [Metrics](mrf-r-basis-sensitivity-metrics.csv): all seeds, both separately labeled ensembles, and unchanged linear references.
- [Predictions](mrf-r-basis-sensitivity-predictions.csv): 480 rows, 48 per method, with target/origin dates and actual values.
- [Result record](mrf-r-basis-sensitivity-result.json): full per-job output hashes, runtime modes and paired comparisons.
- [Pilot audit](mrf-r-basis-pilot-audit.json): preserved earlier bounded check, not a performance result.

The original [FA-ARRF record](MRF_UNEMPLOYMENT_RECONSTRUCTION.md) and successful [ARRF comparator](MRF_ARRF_DIAGNOSTIC.md) remain separate and unchanged. Last-bit differences in reference metrics arise from rescoring saved CSV forecasts.

## What this establishes—and what remains open

This engine can give different forecasts for economically equivalent PCA coordinates; the actual native-R convention tested here improves this implementation modestly. It is not the full explanation of the source discrepancy. We have not recovered the author's historical R build, original basis or missing benchmark runner, and have not ruled out every possible orientation.

Do not promote this variant to a new primary model based on these public evaluation losses, pick its best seed, widen the tolerance or search for a sign pattern that hits 0.72. Source-supported investigation of factor eligibility, completion and per-table settings remains appropriate. In particular, a PCA-eligibility sensitivity must preserve the full individual-indicator/MAF state; the existing whole-panel `sw_subset` option does not do that. The original unemployment replication goal remains open.
