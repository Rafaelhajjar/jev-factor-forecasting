# Completed PCA125 sensitivity: forest agreement, joint replication still fails

Completed and independently audited October 19, 2026. Restricting cross-sectional PCA to the historical 125-series subset substantially narrows the forest discrepancy. All three forest seeds are now within our declared tolerance. **The matching fixed-factor regression is outside tolerance, so the joint replication criterion still fails.** The original result is preserved.

## Did this eligibility choice close the gap?

| Method | RMSE | RMSE / AR(4) | Printed source ratio |
| --- | ---: | ---: | ---: |
| AR(4), unchanged | 0.0334997102 | 1.000000 | 1.00 |
| Fixed FA-AR, PCA125 | 0.0263688148 | 0.787136 | 0.83 |
| FA-ARRF PCA125, seed 101 | 0.0250850823 | 0.748815 | 0.72 |
| FA-ARRF PCA125, seed 202 | 0.0249271667 | 0.744101 | 0.72 |
| FA-ARRF PCA125, seed 303 | 0.0250265999 | 0.747069 | 0.72 |
| Mean forest prediction, separately labeled | 0.0249768749 | 0.745585 | Not a source ensemble |

Every method has the same 48 target dates, 2003Q1–2014Q4, in delta-log unemployment units. Source ratios are the unemployment h=1 cells in appendix Table 4 of [Goulet Coulombe (2024)](https://doi.org/10.1002/jae.3030), not our results.

The forest gaps from 0.72 are 0.02881, 0.02410 and 0.02707. All meet the predeclared 0.03 absolute-ratio diagnostic tolerance. But the corresponding fixed FA-AR differs from 0.83 by -0.04286 and fails. Its lower error is a forecasting improvement here, not a reproduction of the printed linear result. This is numerical agreement for the forest cells only, not a statistical replication test or recovery of the original pipeline.

The forest's incremental RMSE reduction over its **own** fixed-factor comparator is 4.87%–5.47%; the separately labeled ensemble reduces it by 5.28%. The printed 0.72/0.83 ratios imply approximately 13.3%. Thus we still do not recover the source's larger nonlinear gain. These are descriptive comparisons over 48 quarters, not significance claims.

Do not pair this forest with the original all-248 linear ratio of 0.812577 to claim a joint pass. That would combine different factor constructions. The original forest ratios, 0.797325/0.804184/0.806346, and the R-sign sensitivity, 0.786503/0.783246/0.799636, also remain in the record; none is silently replaced or promoted to a new primary model using these test losses.

## One construction change, fixed controls

The [declaration](../docs/PCA125_SENSITIVITY.md), [configuration](../configs/mrf_pca125_sensitivity.json) and runner were published in `5db5735` before pilot/full outcomes, after the earlier results were known. This is explicitly a post-primary diagnostic, not blind confirmation.

Fit five PCs on the metadata-selected 125 columns of the same all-248 training-only cleaned, standardized and EM-completed panel. Replace exactly 40 cross-sectional-factor lag columns. Every non-factor entry, target/mask, AR lag, indicator lag, individual-series MAF, trend, row and column order remains unchanged. The state still has 1,041 columns, and the explicit forest equation still has five coefficients. The OLS-prior rule is refitted in the new coordinates. This does not independently complete a reduced panel or stack the R-sign experiment.

The unchanged author engine ran six expanding refits, 100 trees each and seeds 101/202/303: 18 jobs and 1,800 trees. Other effective settings are inherited from the primary run. Runtime was R 4.6.1 with pracma 2.4.6. No Jev, LLM or paid API forecasting calls were made.

## Complete audit and public artifacts

The [full audit](mrf-pca125-sensitivity-audit.json) verifies all 18 jobs with none pending. It repeats the primary and native-R subset-PCA audits, reconstructs each variant matrix, checks exact preservation outside the 40 factor-lag columns, verifies settings and target/origin timing, and rescores every saved forecast. Independent R QR and Python SVD linear checks agree within 1.5e-15; coefficient reconstructions agree within 2.1e-15. Saved aggregates and the failed joint criterion agree with recomputation.

- [Metrics](mrf-pca125-sensitivity-metrics.csv): both linear constructions, every seed and separately labeled ensembles.
- [Predictions](mrf-pca125-sensitivity-predictions.csv): 528 rows, 48 per method, with target/origin dates and actual values.
- [Result record](mrf-pca125-sensitivity-result.json): per-job output hashes/runtime modes, paired changes and gains over the new fixed-factor comparator.
- [Pilot audit](mrf-pca125-pilot-audit.json): preserved bounded integrity check, with no pilot scores.

The [native-initialization checks](../docs/AUTHOR_CODE_AUDIT.md#direct-native-initialization-check) additionally verify the actual adapter/native boundary without fitting trees. Their PCA125 record is a pre-completion snapshot; it is not the full run's live status. Minor last-bit differences in reference metrics arise from rescoring saved CSVs; original artifacts were not edited.

## What remains unresolved

This shows that PCA eligibility matters in this implementation; it does not establish that the author used this subset or that fewer PCA inputs generally improve forecasting. The exact original eligibility/completion, alignment and per-table invocation remain unverified. The printed linear/nonlinear comparison has not been reproduced jointly.

Keep the original baseline and all sensitivities, the unchanged tolerance, and the distinction between numerical integrity and source fidelity. Do not extend this into a search over arbitrary panels, ranks, signs or seeds to hit 0.72. Original scripts or authoritative clarification are needed to identify the missing choices. Any independent Jev extension still requires prequential development cases and a frozen evaluation plan; it cannot be described as extending an exactly replicated source model.
