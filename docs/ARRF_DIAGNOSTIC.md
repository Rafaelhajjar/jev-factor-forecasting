# ARRF diagnostic after the first reconstruction miss

Declared October 19, 2026, after observing the first FA-ARRF result and before the full ARRF run. This is a named comparator from the published paper, not a search for hyperparameters that reproduce 0.72. The original reconstruction, failed criterion and tolerance remain unchanged.

## Why this comparison

The final article's Table 2 specifies ARRF with an intercept and two target lags, using the same rich state as FA-ARRF. PCA factor lags stay in the forest's state; they are removed only from its explicit linear equation. Appendix Table 4 reports an unemployment h=1 ARRF/AR(4) RMSE ratio of 0.90, distinct from FA-ARRF's 0.72.

Rechecking the article's equations and target-date RMSE definition did not uncover a contradiction in our current AR(4), fixed FA-AR or FA-ARRF lag setup. Exact original preprocessing and invocation remain unknown. A separate [public replication project](https://nanyeonk.github.io/macroforecast/replication/mrf_2024_replication.html) uses a different vintage and a complete-series subset; it reports 0.872 for unemployment h=1 FA-ARRF against 0.72. Its reconstruction is not the missing author runner, and its headline replication claim does not establish our required cell. We do not adopt its settings as author facts.

ARRF provides an additional source comparison without first changing our data preparation. If ARRF is closer while FA-ARRF is not, that would prioritize investigation of the added equation factors, their representation and model-specific regularization. If both miss, shared pipeline/engine choices remain candidates. Neither outcome identifies a unique cause: both forests still see the PCA state, and their explicit equation dimensions differ.

## Frozen design

The [diagnostic declaration](../configs/mrf_arrf_diagnostic.json) specifies 100 trees, seeds 101/202/303, all 48 target dates and the same six refits. All source primary state matrices are reused by path and checksum, not rebuilt. The downloaded engine and independent R adapter are unchanged. Only `xnames` changes to the two target lags; the adapter's existing OLS-prior rule naturally supplies a three-coefficient prior.

All effective input settings are inherited. One consequence of the engine's own dimension-dependent safeguard is that the nominal minimum parent size 10 remains 10 for ARRF, whereas it becomes 12 for five-coefficient FA-ARRF. This is not a controlled causal test of factor removal alone; it implements the two paper specifications using the same package rules. It does not silently impose a different leaf-size setting.

The absolute ratio tolerance is 0.03, used only as a declared ARRF diagnostic. Every seed will be retained, with a separately labeled mean-prediction ensemble. An ARRF match cannot satisfy the still-open FA-ARRF replication requirement. No model/settings will be selected from this comparison using test-period loss, and no hosted selector is called.

## Verification and execution

Before fitting, the runner repeats the full primary artifact audit and verifies the primary manifest, forecasts and source hashes. It rejects an incomplete primary source, altered/undeclared jobs, changed state matrices, changed inherited settings and output paths outside the declared diagnostic layout. Resume checks the same provenance, including this diagnostic's source hash. Every checkpoint must have the two-slope schema and reconstruct its saved forecast from coefficients and inputs.

The actual-R two-tree pilot completed on eight dates, with maximum reconstruction discrepancy 1.4e-16. Its [saved execution record](../reports/mrf-arrf-diagnostic-pilot.json) deliberately contains no forest performance scores or source comparisons. Unit fixtures are explicitly synthetic artifact contracts, not published results. Real-R tests additionally check held-out-target masking and coefficient reconstruction for the two-term ARRF equation.

```bash
# Requires the already completed, audited 48-quarter primary reconstruction.
uv run python scripts/run_arrf_diagnostic.py \
  --source-run runs/mrf-unemployment \
  --output runs/mrf-arrf-diagnostic --workers 4

# Same declaration and inputs only; do not change source files mid-run.
uv run python scripts/run_arrf_diagnostic.py \
  --source-run runs/mrf-unemployment \
  --output runs/mrf-arrf-diagnostic --workers 4 --resume
```

Archive, engine, R executable and project-library locations can be supplied explicitly. Bounded `--trees`, `--seeds` or `--max-refits` pilots cannot establish the full declared comparison and suppress performance scores. Full outputs include predictions, all model/seed metrics, runtime information, per-output hashes and comparison to the ARRF source cell. The primary FA-ARRF files are never overwritten.
