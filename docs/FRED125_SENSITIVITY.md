# Does the public FRED preparation recipe change the unemployment comparison?

Declared October 19, 2026, after the original, ARRF, R-sign and conditional PCA125 results, but before this construction's forecast outcomes. The [configuration](../configs/mrf_fred125_sensitivity.json) records those known results and the training-only rank paths. This is a source-motivated development check on an already-inspected evaluation period, not a blind confirmation or a search for the best score.

## Hypothesis

Our original completion fixes rank at five. The inspected public FRED functions instead select completion rank at each EM step using the jj=2 criterion, with a maximum of eight and a 50-iteration cap. The [training-only audit](FRED_RECIPE_AUDIT.md) independently completes the 125 flagged series and finds final ranks 2/3/3/4/4/4. Python and an independent base-R implementation agree on the complete rank paths and filled values.

The question is whether that preparation changes both the fixed-factor and forest forecasts. Similar training factors do not guarantee similar nonlinear forecasts, and improvement is not assumed. The public driver is monthly FRED-MD, not the missing quarterly MRF runner. Its availability does not establish that the author used these functions, this subset or our forecast-row completion method.

## Change and fixed controls

Select the 125 metadata members **before** outlier cleaning and missing-value completion. Within each original training window, use the source 10-IQR rule, sample-SD scaling, jj=2/DEMEAN=2 adaptive completion, maximum rank eight, 50 iterations and relative-error threshold 1e-6. Stop with an error if that training fit does not converge before the source cap; do not silently extend it or change the rank.

After completion, estimate five state PCs using the original deterministic Python orientation. Completion rank, state-PC count and the two explicit equation factors are different quantities. Do not stack the R-sign sensitivity. Forecast-origin predictor rows use frozen training moments and the fitted completion basis independently; that causal out-of-sample rule is our extension, not supplied by the FRED driver. No future row changes a past row's completion or loadings.

Replace only the 40 cross-sectional-factor lag columns. Preserve the complete original 248-indicator/MAF state, every target and target mask, all AR lags, trend, dates and column order. The full state remains 1,041 columns and the small forest equation remains intercept + AR(2) + two lag-one factors. Refit its OLS prior in the new factor coordinates with unchanged prior settings.

This is a **composite preparation contrast**, not a pure completion-rank toggle: completion uses a separate 125-series panel rather than the all-248 panel, and its rank/iteration policy changes. Indicator and MAF preprocessing nevertheless stay frozen from the primary run. The prior conditional PCA125 experiment selected its 125 columns only after all-248 completion and is not the same construction.

Keep the pinned archive, delta-log unemployment target, all 48 target dates in 2003Q1–2014Q4, the six original expanding refits, 100 trees and seeds 101/202/303. Inherit every other effective forest setting from the corresponding primary job. Retain every seed and separately label the mean-prediction ensemble. No outcome-based choice of panels, ranks, signs or forest settings is permitted in this test.

## Comparators and success rule

Fit a new fixed comparator, `FA_AR_FRED125`: AR(4) plus two lags of each of the first two new factors. AR(4) must remain unchanged. Independently check both linear forecasts with base-R QR before forests run. The old linear model cannot be paired with a new forest to claim a pass.

Compare the matching fixed-factor RMSE/AR(4) ratio to 0.83 and every individual forest ratio to 0.72. The unchanged absolute-ratio tolerance is 0.03; it is a project diagnostic, not the author's standard or a statistical test. The new fixed-factor comparator and **all three** forest seeds must pass jointly. The mean-prediction ensemble cannot rescue a failed seed. Also retain paired changes against the original forest and the new forest's RMSE improvement over its own fixed-factor comparator.

Even joint numerical agreement would not prove that the missing author pipeline has been recovered. A worse result is equally reportable. The primary and all earlier sensitivities remain unchanged; this test does not select a replacement for later Jev evaluation.

## Verification and execution

Repeat the original artifact audit and the saved FRED training audit, including the independent R completion checks. Verify exact source/archive hashes, every reconstructed matrix, unchanged non-factor entries, the complete refit/seed grid, target/origin records and settings. Check coefficient decompositions and saved aggregates. The bounded actual-R pilot uses two trees, seed 101 and one refit/eight dates; it reports integrity, not performance. Incomplete full runs likewise withhold scores.

First create a matching training audit for a fresh primary run. Obtain the checksum-pinned FRED code ZIP from the official source linked in the training note; do not substitute the committed report from a different local run.

```bash
uv run python scripts/audit_fred_recipe.py \
  --source-run runs/mrf-unemployment \
  --code-archive data/raw/fred-databases_code.zip \
  --output reports/my-fred-recipe-training.json

# Bounded integrity pilot, not a forecast benchmark.
uv run python scripts/fred125_sensitivity.py run \
  --source-run runs/mrf-unemployment \
  --code-archive data/raw/fred-databases_code.zip \
  --recipe-report reports/my-fred-recipe-training.json \
  --output runs/mrf-fred125-pilot --trees 2 --seeds 101 --max-refits 1

# Full, unchanged declaration.
uv run python scripts/fred125_sensitivity.py run \
  --source-run runs/mrf-unemployment \
  --code-archive data/raw/fred-databases_code.zip \
  --recipe-report reports/my-fred-recipe-training.json \
  --output runs/mrf-fred125 --workers 4

uv run python scripts/fred125_sensitivity.py audit \
  --run runs/mrf-fred125 \
  --code-archive data/raw/fred-databases_code.zip \
  --recipe-report reports/my-fred-recipe-training.json \
  --output reports/my-fred125-audit.json
```

Use `--prepare-only` to construct and verify all inputs/linear forecasts without fitting forests or calculating scores, then continue the exact same run with `--resume`. Use `--resume` only for the same source, inputs and declaration. A changed implementation requires a fresh run directory. No hosted Jev or LLM calls are part of this preparation experiment. The unemployment replication remains open.
