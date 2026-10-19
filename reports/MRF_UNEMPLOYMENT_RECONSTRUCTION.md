# Quarterly unemployment: completed independent reconstruction

Completed and audited October 19, 2026. This is a result from our own documented pipeline calling the author's pinned R engine. It is **not an exact reproduction** of the published benchmark, and it contains no Jev or LLM forecasts.

## Main result

The reconstructed forest improves on AR(4), but its incremental improvement over the fixed factor regression is small. It does not recover the paper's reported nonlinear gain.

| Model | Forecasts | RMSE | RMSE / AR(4) | Published ratio |
| --- | ---: | ---: | ---: | ---: |
| AR(4) | 48 | 0.0334997102 | 1.000000 | 1.00 |
| Fixed FA-AR | 48 | 0.0272211055 | 0.812577 | 0.83 |
| FA-ARRF, seed 101 | 48 | 0.0267101414 | 0.797325 | 0.72 |
| FA-ARRF, seed 202 | 48 | 0.0269399477 | 0.804184 | 0.72 |
| FA-ARRF, seed 303 | 48 | 0.0270123659 | 0.806346 | 0.72 |
| Mean of the three forest predictions | 48 | 0.0268552416 | 0.801656 | Not a published ensemble |

Published values are the rounded unemployment h=1 cells in appendix Table 4 of [Goulet Coulombe (2024)](https://doi.org/10.1002/jae.3030). They are not our results. The ensemble is our separately labeled diagnostic, not the author's model or a selected best seed.

Forest RMSE is 0.77%–1.88% below fixed FA-AR across the three seeds; the mean-prediction ensemble is 1.34% below it. These are descriptive differences over 48 quarters, not statistical significance claims. The corresponding improvement implied by the paper's rounded ratios is approximately 13.3%.

The fixed FA-AR ratio is within the previously declared absolute tolerance of 0.03. Every individual forest seed misses it: gaps from 0.72 are 0.0773, 0.0842 and 0.0863. The declared full numerical-agreement criterion therefore **fails**. We retain every seed and do not change the tolerance or settings to obtain a pass. The small observed seed spread does not establish convergence in tree count or identify the cause of the gap.

## What ran

- Exact checksum-pinned journal archive, with all 248 quarterly indicators; target is delta log UNRATE.
- Training target dates from 1961Q3; evaluation target dates 2003Q1–2014Q4, with each origin one quarter earlier.
- Six expanding fits through 2002Q4, 2004Q4, 2006Q4, 2008Q4, 2010Q4 and 2012Q4. Each fit supplies the next eight one-step forecasts.
- Training-only missing/outlier handling and five PCA factors; rich state with 1,041 columns. The small forest equation has an intercept, two target lags and two factor terms.
- Author R engine at `bdb2ed435affb741aafdf78bab12c470ec6d55d0`; 100 trees per fit, seeds 101/202/303: 18 jobs and 1,800 fitted trees.
- R 4.6.1 and pracma 2.4.6. No hosted forecasting calls or paid API calls.

The [frozen configuration](../configs/mrf_unemployment.json) and [code audit](../docs/AUTHOR_CODE_AUDIT.md) distinguish source-supported settings from reconstruction assumptions. Raw data and large run inputs remain local; source PDFs and the GPL engine are not redistributed as project source.

## Integrity checks

The completed [machine-readable audit](mrf-unemployment-audit.json) verified all 18 jobs and all 48 target dates, with no missing jobs. It checked checksums, settings, origin/target alignment, all eight target lags against archived levels, masked future outcomes, every reconstructed state matrix, per-seed outputs, aggregate predictions and recalculated metrics.

Independent base-R QR and Python SVD linear forecasts agree within 1.5e-15. Saved state matrices match recomputation within 3.6e-15, and all six EM fits converge. Forest predictions equal their saved intercept plus four coefficient-times-predictor contributions within 2.5e-15. These checks establish internal numerical integrity, not recovery of the missing author pipeline or historical release-date information.

Public derived artifacts:

- [Metrics CSV](mrf-unemployment-metrics.csv): every seed and the separate ensemble.
- [Predictions CSV](mrf-unemployment-predictions.csv): 48 rows per model, with target/origin dates, outcomes and predictions; 288 rows total.
- [Full audit JSON](mrf-unemployment-audit.json): inputs, configuration, source/output hashes, runtime versions, checks and the failed numerical-agreement result.

SHA-256:

```text
mrf-unemployment-metrics.csv
c6ff1f0c56a3cfe816763cadc935d91275a3ef3b7bd1eadf57d7e507d9803f39
mrf-unemployment-predictions.csv
ce8369e3a450f8c3e72feae313cccd1f61b71659842a86c8e56354ae90290597
mrf-unemployment-audit.json
51056ad0fbf3cda67b37be02993d4bb2502c94887eaaf1a18cb41a74a8593977
```

The earlier preliminary audit is preserved as an immutable progress snapshot, not the current completion status.

## How we continue independently

Keep this run as the first frozen independent baseline. Do not label later Jev gains as an extension of an exactly replicated 0.72 model. The missing original runner remains a source-fidelity issue, not a reason to halt implementation or wait for correspondence.

The next investigations are factor eligibility/completion/orientation, original forecast-row alignment and effective per-table forest/prior settings. The engine's native all-row normalization is a separately named diagnostic, not a silent change to the causal primary path. The present `sw_subset` option also changes the individual-indicator/MAF state, so it must not be described as a PCA-only sensitivity without separating those roles first.

Do not optimize these choices against the 2003–2014 outcomes. Preserve this result and register any alternative pipeline and its information set before running it. Until authoritative scripts establish the original choices, alternatives are sensitivities, not proof of the source of the discrepancy.

The shared [25-action algebra](../src/jev_factor/mrf_actions.py) is implemented, with 19 unit-test cases. It builds stable joint candidates from original-unit coefficient contributions, rejects invalid probabilities rather than repairing them, and averages candidate forecasts. An [integration check](../scripts/check_mrf_action_identity.py) verifies that identity and uniform probabilities both recover all 144 individual-seed forest forecasts within 2.5e-15. It sends no model requests and does not pass actual outcomes into the action layer. The full suite passes all 82 tests, including four real-R checks.

Controlled mechanisms, prequential evidence cards and joint-action hosted adapters can now be built without waiting for external code. Genuinely prequential development cases must be generated from earlier fits; neither in-sample fitted rows nor these 48 public evaluation outcomes may stand in for that development set. The action algebra alone does not establish availability of caller-supplied predictors or evidence. A future comparison against this baseline must be explicitly labeled an independent-reconstruction extension, with original-runner replication tracked separately. Jev/LLM prompts and confirmatory scores remain unrun.
