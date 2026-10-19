# Can the plain-forest controls match their unemployment cells?

Declared October 19, 2026, after the original, ARRF, R-sign, PCA125 and FRED125 outcomes, but before these controls' macro pilot or full outcomes. The [executable configuration](../configs/mrf_plain_controls.json) records the known earlier results. This is a post-primary reconstruction exercise, not a blind confirmation or a change to the failed FA-ARRF criterion.

## Problem, inputs, target

Implement the two distinct controls checked in the [source note](RF_MAF_CONTROL.md): RF-MAF predicts the transformed target from the full rich state; AR+RF fits an AR(2) on the training window, then predicts its residual with the same type of forest and adds back the AR forecast.

Reuse the **original all-248 primary** state matrices without changing any entry. This includes every target mask, AR lag, indicator/MAF input, cross-sectional factor lag, trend and row/column order. Do not select the later PCA125 or FRED125 representations using their scores. Retain delta-log unemployment, the same 48 target dates in 2003Q1–2014Q4, six original expanding refits, 100 trees and seeds 101/202/303. Two controls give 36 fits and 3,600 trees. The complete original primary configuration is checksum-pinned, in addition to its data/source/artifact audit.

The AR(2) uses an intercept and lags one and two of the transformed target. Fit it once per expanding refit using only training outcomes. Generate training residuals and forecast-row AR offsets from those coefficients. Base-R QR independently checks coefficients, all-row predictions and training residuals before fitting forests. A separately labeled `AR2_filter` forecast is retained as a diagnostic, not a reported Table 4 cell.

## Fixed construction and remaining assumptions

Scale all state columns using training means and sample standard deviations. For RF-MAF, similarly scale the training target; for AR+RF, scale its training residual instead. Reverse that target scaling before adding the AR offset. Constant-target SD at or below 1e-12 uses unit scale; constant state columns are rejected. Future rows do not refit any moments, coefficients or tree.

Use the separately implemented plain CART forest, not a relabeled MRF. Each tree fits its sampled rows and terminal means only, with no MRF ridge/RW prior, jitter, split-rank preference or full-training terminal refit. Fix nominal block size eight, retained fraction 0.75, candidate-feature fraction 1/3, minimum parent 10 and minimum leaf one, unrestricted depth and no pruning. The same external sampling/tree-seed schedule is used across the two controls for a given refit/seed.

The sampler reconstructs the native random-group/quantile law, not fixed-length eight-row blocks: realized group lengths and retained fractions vary. NumPy PCG64 draws are not historical R seed equivalence. The CART backend is fixed to scikit-learn 1.9.1; it converts features to float32 and may inspect more than the candidate-feature setting to find a valid split. The original plain-RF backend, terminal-size convention, random-number streams and exact per-table settings remain unknown. These are transparent independent choices, not recovery of the missing author runner. No setting is chosen by a new control test loss.

## Comparisons and rule

The source unemployment h=1 ratios to AR(4) are 0.85 for RF-MAF and 0.84 for AR+RF. Keep the original AR(4) denominator. Compare every individual seed to its own named source cell using the existing absolute-ratio tolerance of 0.03. This is a project diagnostic, not a statistical test or author standard. The control gate requires **all six individual cells**; the two separately labeled mean-prediction ensembles cannot rescue a failed seed.

Report both controls, every seed, both mean-prediction ensembles, the AR2-filter diagnostic and unchanged original reference methods. Keep all 48 dates. Do not choose a best seed or transfer source significance stars. Even a complete control match cannot establish the FA-ARRF replication, the larger published nonlinear gain or exact source fidelity. The original primary and all sensitivities remain preserved.

## Verification before interpretation

Repeat the complete primary artifact audit, including state reconstruction and independent R linear checks. Bind the new configuration, source hashes, backend versions, original matrices/settings and full model/refit/seed grid. Use training targets only; component tests perturb all future target values and later covariates.

Each fit saves JSON tree structures, group weights/memberships, sampled rows and tree seeds, plus forecast/base/nonlinear components. The verifier reconstructs sampled-node means directly from training data and traverses the saved trees using the backend's float32 routing convention. It checks averaging, inverse scaling and the AR offset independently of the saved forecast CSV. The final auditor also deterministically refits **every forest** and compares the saved structure, so an arithmetically valid substitute is insufficient. It then verifies saved aggregates, metrics and source-cell flags. No pickle loading is needed.

The bounded pilot uses two trees, seed 101 and one refit: two control fits and eight dates per control. It reports integrity only. Preparation-only and partial runs suppress accuracy comparisons. Full scores require all 36 fits and the unchanged declaration.

```bash
# First complete the original primary reconstruction and audit.
uv run python scripts/plain_controls.py run \
  --source-run runs/mrf-unemployment --output runs/plain-controls-pilot \
  --trees 2 --seeds 101 --max-refits 1

uv run python scripts/plain_controls.py audit \
  --run runs/plain-controls-pilot --allow-partial \
  --output reports/my-plain-controls-pilot.json

uv run python scripts/plain_controls.py run \
  --source-run runs/mrf-unemployment --output runs/plain-controls

uv run python scripts/plain_controls.py audit \
  --run runs/plain-controls --output reports/my-plain-controls-audit.json
```

`--prepare-only` writes the declaration/input record and independent AR(2) checks without fitting forests or scoring. Continue that exact run with `--resume`; changed inputs, code, configuration or backend versions are rejected. Full output directories include tree checkpoints, component forecasts, metrics, predictions, result and manifest records. These controls make no hosted Jev or LLM calls. The unemployment replication goal remains open until its actual requirements are satisfied.
