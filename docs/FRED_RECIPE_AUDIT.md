# Does the missing-data recipe change our factor construction?

Training-only audit completed October 19, 2026, after the earlier forecast results were known. The source-recipe port and independent R check agree on all six training windows. **No new forest was fitted or forecast loss calculated.** The joint unemployment replication remains incomplete.

## Why this is a source-backed next check

The pinned code distributed from the [St. Louis Fed's FRED databases page](https://www.stlouisfed.org/research/economists/mccracken/fred-databases) uses a different completion recipe from our fixed-rank-five implementation. Its inspected driver specifies demeaning/standardization, the jj=2 criterion and maximum rank eight. The EM function reselects rank after each missing-cell update and caps iterations at 50, using relative reconstruction change 1e-6. Our original reconstruction uses rank five and a cap of 100.

This archive's driver is for monthly FRED-MD. Applying those numerical preparation functions to each quarterly 125-series training window is **our adaptation**, not evidence that the MRF author used this code or subset. MATLAB/Octave is unavailable here; we do not claim to have executed the original MATLAB functions.

Archive SHA-256: `cbb4b5f1e9549e506bf12979643422c3fb6fda108f1a94fd5f998a0536399036`. The [machine-readable audit](../reports/mrf-fred-recipe-training-audit.json) records member hashes for `fredfactors.m`, `factors_em.m` and `remove_outliers.m`. Original MATLAB files are not vendored.

## What ran

Use only predictor observations through each original refit endpoint. Select the 125 historical-subset series **before** cleaning/completion; keep the source's 10-IQR rule and sample-standard-deviation scaling. This is not the previous conditional PCA125 construction, which selected columns after completing all 248 series.

The jj=2 code minimizes, over ranks zero through eight:

```text
log(mean squared reconstruction residual)
  + rank * (N + T) / (N * T) * log(min(N, T))
```

Observed cleaned cells stay exactly unchanged. Missing cells are updated, moments are recomputed and rank is selected again. The implementation exposes the source iteration cap and its zero-reconstruction/undefined-ratio stopping edge case; it does not silently extend the cap or call that edge case ordinary convergence. Only the relevant jj=2/DEMEAN=2 path is reconstructed, not the full MATLAB API.

Completion rank is not the model's factor count. After completion, retain five state PCs using the existing deterministic Python orientation. The small forecasting equation still uses two factors. The class also implements a frozen-basis, row-independent future-completion method, but that is our causal extension; the supplied FRED script does not specify it.

## Actual training results

| Refit endpoint | Final completion rank | EM iterations | Converged before cap |
| --- | ---: | ---: | --- |
| 2002Q4 | 2 | 48 | Yes |
| 2004Q4 | 3 | 43 | Yes |
| 2006Q4 | 3 | 36 | Yes |
| 2008Q4 | 4 | 47 | Yes |
| 2010Q4 | 4 | 25 | Yes |
| 2012Q4 | 4 | 25 | Yes |

The 2004/2006 fits start at rank two and finish at three: selecting rank only once would miss an actual source-algorithm step. These are numerical EM iterations, not economic regime forecasts or Jev decisions.

An independent base-R implementation uses Gram-matrix eigenvectors and explicit residual matrices; Python uses direct SVD and singular-value tail sums. Entire rank paths, stopping reasons, missing/outlier masks and completed values agree. Maximum completed-value difference is below 4.0e-14 in final training-standard-deviation units; final PC loadings agree up to signs within 5.2e-15.

Compared with conditional PCA125, corresponding first-two training-score correlations are approximately 0.997–1.000 and 0.987–0.999. High correlation does not establish equal nonlinear forecasts or improved accuracy. All 201 local tests pass, including 12 real-R contracts. The original primary and sensitivity inputs/results remain unchanged.

## Reproduce and interpret

After completing the primary reconstruction, obtain the inspected code ZIP from the official page's Code link and supply its path; the audit rejects a different hash.

```bash
uv run python scripts/audit_fred_recipe.py \
  --source-run runs/mrf-unemployment \
  --code-archive data/raw/fred-databases_code.zip \
  --output reports/my-fred-recipe-audit.json
```

A forecast comparison requires a separate declaration before its outcomes, the same dates/trees/seeds and its own matching fixed FA-AR. A factor-block-only version must explicitly preserve the full indicator/MAF state; it must not be called a pure rank toggle because the completion panel and iteration policy also change. No recipe is selected using a new test score here, no old result is replaced, and original-author preprocessing remains unverified.
