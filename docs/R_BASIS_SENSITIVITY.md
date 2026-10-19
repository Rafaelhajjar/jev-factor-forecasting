# Does the recorded R factor orientation change the forecast?

Declared October 19, 2026, after observing the primary FA-ARRF miss and the successful ARRF diagnostic, but before the full orientation experiment. The [configuration](../configs/mrf_r_basis_sensitivity.json) records those already-known outcomes. This is a post-primary investigation, not a blind confirmatory test.

## Hypothesis

Python and R recover the same PCA components up to signs on our completed training data. The pinned MRF engine is not sign-invariant. So changing only the coordinate convention could alter its forecast, even though it receives exactly the same information.

The test is simple: use the signs from the [training-only R basis audit](PCA_BASIS_AUDIT.md), refit the same factor-augmented forest, and compare every declared seed with its original forecast. Do not try different sign combinations or choose one using test-period loss.

## Inputs that stay fixed

Keep the archived data, cleaned/completed values, loadings, regression dates, target masks, lag structure and information set. Keep all forest settings, the OLS-prior rule, 100 trees, seeds 101/202/303 and all six refits. The explicit equation still has the same five coefficients; its dimension-dependent safeguards therefore remain the same as the primary FA-ARRF.

The original primary run and the ARRF comparator are not edited. The new run lives in a separate directory with its own source, configuration, basis-report and input hashes.

## What changes

Multiply each cross-sectional component by its recorded R-relative sign, consistently across all eight lags and all training/forecast rows. Apply the recorded signs to each individual-series MAF as well. This uses R's observed signs, not newly estimated R factor values: the underlying Python values and loadings are unchanged.

Targets, autoregressive lags, indicator lags and trend are untouched. Reading/writing uses round-trip precision, and validation requires exact numerical equality to the original matrix times the declared sign vector. A sign reversal is invertible, so it does not add or remove information.

The R adapter refits the OLS prior in the signed coordinates and calls the unchanged author engine. Saved factor coefficients belong to those coordinates. Use each job's signed matrix with its coefficients; do not pair them directly with unsigned factor values.

## Checks before the full fit

First repeat the original artifact audit and the native R PCA audit. The supplied sign maps must agree with the newly calculated maps and runtime; a metadata flag alone is not enough. Reject missing/duplicate jobs, changed targets or origins, altered settings, invalid signs, changed input hashes and paths outside the new run layout.

AR(4) and fixed FA-AR forecasts must remain unchanged. Verify that in Python and independently with base-R QR regression before fitting forests. This distinguishes a coordinate-only change from an accidental preprocessing or alignment change.

The actual-R pilot uses two trees, one seed and eight forecast dates. Its coefficient reconstruction error is at most 1.2e-15; its Python and R linear checks differ from the original forecasts by at most 1.1e-16. The [pilot audit](../reports/mrf-r-basis-pilot-audit.json) publishes no forest scores or source comparisons. All 126 local tests pass, including seven real-R checks.

## How the result will be judged

Retain all three seeds and label the mean-prediction ensemble separately. Report paired forecast changes and RMSE-ratio changes against the corresponding original seeds. Compare fixed FA-AR with 0.83 and the R-signed FA-ARRF with 0.72, using the same 0.03 absolute-ratio diagnostic threshold. Every individual seed must pass; an ensemble cannot rescue that rule.

Whatever happens, keep the first result. A closer ratio would quantify the effect of this encoding in our implementation; it would not prove that we recovered the author's original R build, orientation or complete pipeline. A worse ratio is equally reportable. There is no upstream penalty change, additional hyperparameter search or Jev/LLM call in this experiment.

## Run and verify

For a newly created primary run, first create its matching native basis audit. R's signs can differ across builds; do not silently reuse or modify a mismatched report.

```bash
uv run python scripts/audit_pca_basis.py \
  --source-run runs/mrf-unemployment \
  --output reports/my-native-basis.json

uv run python scripts/r_basis_sensitivity.py run \
  --source-run runs/mrf-unemployment \
  --basis-report reports/my-native-basis.json \
  --output runs/mrf-r-basis --workers 4

uv run python scripts/r_basis_sensitivity.py audit \
  --run runs/mrf-r-basis \
  --basis-report reports/my-native-basis.json \
  --output reports/my-r-basis-result-audit.json
```

Use `--resume` with the identical run arguments after an interruption. Changed settings, source files or sign reports are rejected. A different native build requires a newly declared run, not silently changing an existing one. Bounded pilots suppress performance comparisons. The original unemployment replication goal remains open until the actual required results are demonstrated.
