# Does PCA eligibility explain part of the unemployment gap?

Declared October 19, 2026, after seeing the original FA-ARRF, ARRF and R-sign results, but before this variant's forecast outcomes. The [configuration](../configs/mrf_pca125_sensitivity.json) records those known results and the already-completed training diagnostics. This is a post-primary investigation, not a blind confirmatory test.

The declaration and runner were published in `5db5735` before the pilot and full outcomes. The actual-R two-tree/eight-date pilot passes its [independent audit](../reports/mrf-pca125-pilot-audit.json), with no pilot scores published. The full comparison is now [completed and audited](../reports/MRF_PCA125_SENSITIVITY.md): all 18 jobs pass integrity checks; forest ratios 0.748815/0.744101/0.747069 meet the forest-cell tolerance, but fixed FA-AR 0.787136 fails against 0.83. The joint criterion remains false. The declaration below is retained unchanged in substance.

## Hypothesis

Our original factors use all 248 series. The archived metadata also identify a historical 125-series factor subset. The [training-only audit](../reports/MRF_PCA_ELIGIBILITY_AUDIT.md) shows that the subset changes the factor representation, while the first two factors remain strongly related to their original counterparts. A nonlinear coefficient forest can respond to these differences. We do not assume it will improve.

The question is whether changing only cross-sectional PCA eligibility changes the fixed-factor and forest forecasts, and whether it brings either closer to its named source ratio. The metadata do not establish that the author used this subset.

## Inputs and one change

Reuse the all-248 primary run's training-only cleaning, standardization and rank-five EM completion. Estimate five PCs from the completed panel's 125 flagged columns. Use the original deterministic Python sign convention: do not combine this test with the R-sign sensitivity or independently complete a reduced panel.

Replace only the 40 cross-sectional-factor lag columns, consistently in training and forecast rows. Preserve every target/mask, AR lag, individual-indicator lag, MAF, trend, row and column order. All 1,041 state columns remain present. The explicit forest equation retains its intercept, two AR terms and two factor terms, so its dimension-dependent safeguards are unchanged. The OLS-prior rule is refitted on the new factor coordinates; its settings are unchanged.

Keep the archived data, delta-log unemployment target, all 48 target dates in 2003Q1–2014Q4, the six original expanding refits, 100 trees and seeds 101/202/303. Every other effective forest setting is inherited from the corresponding original job.

## Comparisons and checks

Re-estimate a separate fixed FA-AR with the subset factors, named `FA_AR_PCA125`. It retains four AR lags and two lags of each of the first two factors. AR(4) must remain unchanged; the new fixed-factor model is not required to equal the old one. Check both linear fits independently using base-R QR before fitting forests.

Retain every individual seed and a separately labeled mean-prediction ensemble. Report the new fixed FA-AR/AR(4) ratio against 0.83 and every new forest seed against 0.72, using the unchanged 0.03 absolute-ratio diagnostic tolerance. Every individual forest seed and the new fixed-factor comparator must pass. The ensemble cannot rescue that rule. Also report paired forecast and ratio changes versus the original seeds and the forest's incremental gain over its own fixed-factor comparator. Do not select a best seed or replace the primary result.

Before fitting, repeat the original artifact and subset-PCA audits. Reconstruct and verify the saved matrices, exact preservation of every non-factor entry, full refit/seed grid, target/origin dates, settings and source hashes. Check the final forecast row as well as the first. The bounded pilot uses two trees, seed 101 and one refit/eight dates; it publishes integrity checks, not forecast scores. Partial runs likewise withhold performance comparisons.

## Interpretation

A closer ratio would quantify this eligibility choice conditional on our original completion and engine; it would not recover the author's missing pipeline. A worse ratio is equally reportable. These are development investigations on an already-public test period, not independent evidence for selecting a production model or a Jev policy. Do not extend this into a search over arbitrary panels, ranks, signs or hyperparameters. Jev and LLM evaluation remain unrun.

For a newly created primary run, first generate its matching eligibility audit. The report binds the exact primary manifest, source and native-R checks; the committed report from our local run is not a portable replacement. Pass the fresh report to both commands below.

```bash
uv run python scripts/audit_pca_eligibility.py \
  --source-run runs/mrf-unemployment \
  --output reports/my-pca-eligibility.json

uv run python scripts/pca125_sensitivity.py run \
  --source-run runs/mrf-unemployment \
  --eligibility-report reports/my-pca-eligibility.json \
  --output runs/mrf-pca125 --workers 4

uv run python scripts/pca125_sensitivity.py audit \
  --run runs/mrf-pca125 \
  --eligibility-report reports/my-pca-eligibility.json \
  --output reports/my-pca125-audit.json
```

Use `--resume` only with the exact same declaration, inputs and source. Bounded pilots can reduce trees/seeds/refits; they cannot be relabeled as the full sensitivity. A run with changed source files must use a new directory. The original unemployment replication goal remains open until its required benchmark is actually reproduced.
