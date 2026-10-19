# PCA eligibility: the factors change, the full indicator state does not

Completed October 19, 2026. The new builder separates the input used for cross-sectional PCA from the forest's full indicator/MAF information set. All six refits pass preservation checks. **No new forest was fitted and no new forecast loss was calculated.**

Subsequent work: the separately declared [full forecast sensitivity has now completed](MRF_PCA125_SENSITIVITY.md). Its forest cells meet tolerance, its linear cell fails and the joint replication remains incomplete. This document stays the training-only representation record.

## Training-only result

| Refit endpoint | Absolute correlation, original/subset F1 | Absolute correlation, original/subset F2 | Smallest five-factor subspace cosine |
| --- | ---: | ---: | ---: |
| 2002Q4 | 0.9871 | 0.9548 | 0.8972 |
| 2004Q4 | 0.9877 | 0.9392 | 0.8901 |
| 2006Q4 | 0.9872 | 0.9219 | 0.8860 |
| 2008Q4 | 0.9892 | 0.9214 | 0.9076 |
| 2010Q4 | 0.9893 | 0.9475 | 0.5348 |
| 2012Q4 | 0.9898 | 0.9445 | 0.8686 |

Correlations compare scores on the same training dates, not their correlations with unemployment outcomes. Subspace cosines compare the spans of the five centered training score vectors: one means identical direction, zero means orthogonal. They are not percentages of variance explained or forecast accuracy. Full correlation matrices, all principal cosines, explained-variance ratios and top loadings are retained in the [audit JSON](mrf-pca-eligibility-audit-v2.json).

The subset changes more than coordinate signs, especially part of the five-factor span at the 2010 refit. The high first-two correlations do not establish that their economic content or the resulting nonlinear forecasts are identical. Both representations contain activity-related and forward-looking leading loadings; those descriptive labels cannot identify the author's missing eligibility rule.

## Exactly what was checked

Start with the original all-248 training-only cleaned, standardized and EM-completed panel. Fit five principal components using the 125 columns marked by the archived historical-subset metadata. Keep completion fixed: this does not rerun EM on a reduced panel. Transform later predictor rows with these frozen loadings, using the original deterministic Python PCA convention rather than stacking the separate R-sign change.

Only the 40 cross-sectional-factor lag columns may differ. All 1,041 state columns remain present. Every target/mask, autoregressive term, individual-indicator lag, individual-series MAF and trend entry is exactly preserved, as are row and column order. Original factor-lag reconstruction error is zero in all six refits. The checks cover both the first training target, 1961Q3, and the last target of every refit block, including 2014Q4.

Independent base-R PCA agrees with the subset's loadings up to signs; maximum sign-aligned difference is 2.1e-15. These native R signs are checked, not adopted. The source primary artifact audit also passes again. Original forecasts, results and source files are unchanged.

The [declaration](../docs/PCA_ELIGIBILITY_AUDIT.md) specifies the construction and forbids choosing eligibility using 2003–2014 forecast losses. The [implementation](../src/jev_factor/pca_eligibility.py) has 24 synthetic contract tests covering independent SVD, future-data perturbation, excluded-series perturbation, exact non-factor preservation, final-row lag handling, mismatched primary configurations and invalid inputs. All 150 local tests pass, including the seven existing real-R contracts; the actual six-refit audit additionally runs base R on the archived data.

## Boundary before another performance run

The 125-series flag is not a recovered author instruction. This audit does not claim the subset is preferable or explains the 0.72 gap. A full sensitivity must be separately declared before its outcomes, retain 100 trees and all three seeds, leave the full state and forest settings unchanged, and recompute its own fixed FA-AR comparator. Preserve both existing FA-ARRF records and report every result, not a selected best configuration.

Reproduction command is in the [declaration](../docs/PCA_ELIGIBILITY_AUDIT.md). The current audit records source/helper/data/engine hashes and all six native-R checks. Audit SHA-256: `87d60a38380f6db620d8b1f9715d5e65265126719e2aec1e2f530238a0c0c8e1`. The [first audit generation](mrf-pca-eligibility-audit.json) is preserved with its original source hash; after adding explicit mismatched-configuration rejection and dependency hashes, the fresh v2 audit verifies exactly the same six-refit results. This remains a representation diagnostic; the unemployment replication goal is not complete.
