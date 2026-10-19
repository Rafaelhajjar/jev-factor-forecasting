# Separate factor eligibility from the forest's information set

Declared October 19, 2026, after the primary, ARRF and R-sign results. This stage is a training-only representation audit, not another forecast contest.

**Completed:** all six refits pass input-preservation and independent base-R PCA checks. The first two subset factors have absolute training correlations of 0.987–0.990 and 0.921–0.955 with their corresponding original factors. No new forecast loss was calculated. See the [completed representation result](../reports/MRF_PCA_ELIGIBILITY_AUDIT.md) and [machine-readable audit](../reports/mrf-pca-eligibility-audit-v2.json).

## Question

The archived FRED-QD metadata mark 125 series as members of the historical Stock-Watson factor subset. Our original reconstruction estimates cross-sectional factors from all 248. Does restricting only that PCA input materially change the factors, while preserving every individual-indicator and MAF state entry?

The final article's Tables 1–2 distinguish the rich state from the small factor-augmented equation. Its discussion on printed page 409 motivates the first two factors as real activity and forward-looking indicators. It does not identify the exact PCA eligibility rule. The official [FRED-QD paper](https://www.stlouisfed.org/-/media/project/frbstl/stlouisfed/publications/review/pdfs/2021/01/14/fred-qd-a-quarterly-database-for-macroeconomic-research.pdf) explains the historical-subset metadata; the [author engine](https://github.com/philgoucou/macrorf/tree/bdb2ed435affb741aafdf78bab12c470ec6d55d0) does not prepare factors. None of this establishes that the MRF author used the 125-series subset.

## Fixed construction

Retain the primary run's all-248 training-only cleaning, rank-five EM completion, standardization and completed panel. Fit five principal components using only the metadata-selected columns of that completed panel and only rows available at the refit. Keep the same deterministic Python PCA sign convention as the original run: do not stack the R-sign sensitivity onto this change.

Replace exactly the 40 cross-sectional-factor lag columns. Preserve every target, autoregressive term, indicator lag, MAF, trend, row, column order and target mask. The forest's state therefore still contains the full 248 indicators and their MAFs. This is a PCA-eligibility-only change conditional on the original completion, not an independently completed 125-series pipeline. The existing whole-panel `sw_subset` option is not equivalent.

## Checks and decision boundary

Audit the primary artifacts first. For each of the six declared refits, verify the original factor lag values against recomputation, check that exactly 40 columns are eligible to differ, and require exact equality everywhere else. Independently compare the subset PCA loadings with base R up to signs. Verify the first and last target rows explicitly so lag reindexing cannot drop the final forecast row.

Report training-only absolute score correlations, first-two/five score-subspace overlaps, explained variance and largest loadings. Do not calculate target correlations, forecast losses, regression performance or a preferred subset using the 2003–2014 outcomes. No forest is fitted at this stage and no primary artifact is modified.

A later full forecast sensitivity would require a separate declaration, all three seeds, unchanged forest settings and its own fixed-factor linear comparator. These training diagnostics alone neither reproduce 0.72 nor establish that the historical subset is better.

```bash
uv run python scripts/audit_pca_eligibility.py \
  --source-run runs/mrf-unemployment \
  --output reports/my-pca-eligibility-audit.json
```
