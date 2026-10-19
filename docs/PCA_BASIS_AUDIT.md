# PCA orientation audit: a concrete portability difference

Audited October 19, 2026. This checks a possible source of reconstruction differences without changing the primary forecasts, fitting new macro forests or selecting a basis using forecast loss. The [machine-readable record](../reports/mrf-pca-basis-audit.json) includes source hashes, runtime, component comparisons and sign maps.

## What the source says

The public [R usage example](https://mrf-web.readthedocs.io/en/latest/usage.html#r) uses `prcomp`, but it is a monthly tutorial with different preparation, not the quarterly paper runner. [R's documentation](https://stat.ethz.ch/R-manual/R-devel/library/stats/html/prcomp.html) explicitly notes that component signs are arbitrary and can vary across programs or R builds. Our first reconstruction instead fixes the largest-magnitude loading positive through scikit-learn's convention.

In an ordinary linear regression a consistent sign change of a regressor and its coefficient leaves the forecast unchanged. That is not a safe assumption for the pinned MRF implementation: its [native threshold-rank penalty](https://github.com/philgoucou/macrorf/blob/bdb2ed435affb741aafdf78bab12c470ec6d55d0/R/MRF_v210403.R#L1100-L1107) is not symmetric under reversing the ordered candidates. The function's comment describes a central-split preference; the actual calculation is the authority for this version.

## Experiment and result

For each of the six primary refits, reuse the declared training-only cleaning and EM-completed standardized indicator matrix. Run cross-sectional PCA and each variable's eight-lag, two-component PCA in both Python and base R, using identical values, scaling, centering and column order. No held-out outcomes enter these basis calculations. The primary artifact audit is repeated separately to verify that the source run remains intact.

All 30 cross-sectional components and 2,976 MAF components agree up to component signs. The largest sign-aligned loading differences are 1.1e-15 and 3.1e-13 respectively. Thus this comparison finds no retained-subspace discrepancy on the same completed data. It does not independently validate the EM completion or recover the original author's preprocessing.

R reverses 22 of 30 cross-sectional components and 1,468 of 2,976 MAF components relative to Python on this machine's R 4.6.1 build:

| Refit endpoint | Opposite cross-sectional signs | MAF 1 opposite signs / 248 | MAF 2 opposite signs / 248 |
| --- | --- | ---: | ---: |
| 2002Q4 | F1, F2, F3, F4 | 115 | 121 |
| 2004Q4 | All five | 118 | 123 |
| 2006Q4 | F1, F2 | 102 | 126 |
| 2008Q4 | All five | 127 | 129 |
| 2010Q4 | F1, F2 | 123 | 129 |
| 2012Q4 | F1, F3, F4, F5 | 124 | 131 |

Calling the unmodified engine's `DV.fun` on ten equal candidate losses, at the splitter's actual exponent 0.15, gives multipliers ranging from 1.0000 to 1.2286. Reversing this vector changes it by up to 0.2286. This is a diagnostic of the penalty, not a measurement of its contribution to the macro forecast error.

A real-R contract on a small explicitly synthetic problem confirms that consistently reversing a factor in both the equation and state can change the pinned engine's forecasts by more than 1e-5, with OLS priors refitted and identical seeds. It documents current behavior, not a desirable invariant or macro performance result. At this audit milestone the suite passed 103 tests, including seven actual-R checks. Tests distinguish simple sign changes from arbitrary rotations in a degenerate eigenspace.

## What we can conclude

PCA orientation is an observed implementation difference worth recording, not an innocuous unspecified detail in this engine. Today's R `prcomp` signs are not proof of the signs used by the author years earlier, and the monthly tutorial does not establish the quarterly pipeline.

We therefore do **not** attribute the 0.80-versus-0.72 gap to this finding, replace the primary basis, change the upstream penalty, or claim that adopting today's R basis would recover the original result. Any later orientation sensitivity must be declared as such and retain all results; its basis cannot be chosen by test-period RMSE. The [completed ARRF comparator](../reports/MRF_ARRF_DIAGNOSTIC.md) uses the original, unchanged state matrices. Exact FA-ARRF reproduction remains open.

The subsequently declared [coordinate-only sensitivity is now complete](../reports/MRF_R_BASIS_SENSITIVITY.md): all three R-signed seeds improve modestly to 0.783–0.800, but none meets the tolerance around 0.72. It preserves the primary result and does not recover the author's historical basis.

```bash
uv run python scripts/audit_pca_basis.py \
  --source-run runs/mrf-unemployment \
  --output reports/my-pca-basis-audit.json
```

The output must be fresh. Large intermediate training matrices are isolated and automatically removed; no raw panel or external GPL source is redistributed in the report.
