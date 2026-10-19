# Appendix NN completed: two seed ensembles match, one misses

Completed and independently audited October 19, 2026. All **180 networks and 48 forecast dates** are verified. NN/AR(4) ratios are **0.793326, 0.842565 and 0.801268**, compared with the paper's 0.80. Seed 202 misses the declared absolute-ratio tolerance of 0.03, so the all-seed criterion fails. The other two seeds and the separately labeled outer-seed mean do not rescue it.

## What did we get?

| Method | RMSE | RMSE / AR(4) | Printed source ratio | Within tolerance? |
| --- | ---: | ---: | ---: | --- |
| AR(4), unchanged denominator | 0.0334997102 | 1.000000 | 1.00 | Reference |
| Fixed FA-AR, unchanged | 0.0272211055 | 0.812577 | 0.83 | Yes |
| NN seed 101, 10-member ensembles | 0.0265762067 | 0.793326 | 0.80 | Yes |
| NN seed 202, 10-member ensembles | 0.0282256883 | 0.842565 | 0.80 | No |
| NN seed 303, 10-member ensembles | 0.0268422332 | 0.801268 | 0.80 | Yes |
| NN outer-seed mean prediction | 0.0270311899 | 0.806908 | Not a source ensemble | Excluded |

The source cell is unemployment h=1 in appendix Table 4 of [Goulet Coulombe (2024)](https://doi.org/10.1002/jae.3030), PDF page 31, printed page 70. Our tolerance is a project diagnostic, not an author standard or a statistical test; source significance stars do not transfer. All results concern delta-log unemployment on the fixed archived vintage and target dates 2003Q1–2014Q4, not reconstructed historical releases or a new blind test.

The NN is competitive with the reconstructed fixed-factor and factor-forest forecasts, but its seed sensitivity matters. These descriptive scores establish neither a robust NN advantage nor a Jev result. The original FA-ARRF numerical-agreement criterion and larger nonlinear-gain requirement remain unmet.

## What exactly ran?

The [declaration](../docs/NN_CONTROL.md), [configuration](../configs/mrf_nn.json), complete runner and tests were committed and pushed in **42fe535f21dfa3098f8db02b97087934da51a39c before the actual-data pilot or full outcomes**. Earlier primary and comparator losses were already public. No NN unemployment loss was used to select these settings, and no setting or seed was changed after the results.

Each of six original expanding two-year refits uses the entire unchanged 1,041-column state, not only two factors. At each refit, each outer seed trains 10 separate networks on random 85% subsamples of the past fitting window and uses the omitted rows for validation. Average the 10 member forecasts, not parameters. Architecture: five fully connected 100-unit ReLU hidden layers and a scalar linear output. Adam, batch size 32 and the 100-epoch cap follow appendix A.2; modern CPU Torch 2.14.1, exact stopping/scaling/RNG conventions and unscaled targets are our explicit missing-detail assumptions.

Every member stops by the declared patience-10 rule; none reaches the 100-epoch cap. Training lengths range from 11 to 53 epochs (median 15); selected checkpoint epochs range from 1 to 43 (median 5). Each forecast uses the restored best-validation checkpoint. These are observed training diagnostics, not extra tuning choices or proof of global optimization.

Random validation is not chronological/prequential validation. Scaling and already-built lag/PCA features use the past fitting window, including validation covariates; no forecast target is passed to training. The source NN runner, historical runtime, target scaling and unstated early-stopping details remain unknown. Later HNN code is not substituted for that missing runner.

## What is verified?

The [full audit](mrf-nn-audit.json) repeats the entire primary audit, rebuilding all six original state matrices and checking linear forecasts independently in R. It binds source/configuration/environment/code hashes, member identities, row partitions, moments, epoch histories, checkpoint selection, parameter arrays and forecast dates. Numeric NPZ arrays are loaded without pickle; independent NumPy forward passes reproduce every restored network's forecasts and validation/training MSEs.

Maximum independent forecast discrepancy is 5.96e-8; validation-MSE discrepancy is 4.16e-10 and training-MSE discrepancy is 1.72e-10, within the declared float32 tolerances. The final auditor then **retrains all 180 networks**, requiring exact equality of every parameter and the complete split/batch/loss/stopping history. All 180 repeats pass on the recorded platform. This does not claim cross-platform or historical Torch/R bitwise equivalence.

Independent base-R rescoring of the published CSVs agrees on all ten methods: maximum RMSE and MAE differences 3.5e-18 and ratio difference 1.2e-16. Its independently grouped 10-member forecasts agree with all 144 individual-seed ensemble predictions within 1.4e-17. The outer audit also reconstructs the separate outer-seed mean and the failed all-seed criterion.

Final manifest SHA-256: 7c394be22597c29fe1c88583baa59e48eb1aa7b9165c3004ca0aced25450117b.

- [Metrics](mrf-nn-metrics.csv): all ten reference/new-control methods.
- [Predictions](mrf-nn-predictions.csv): 480 rows, 48 per method.
- [Member predictions](mrf-nn-member-predictions.csv): all 1,440 member forecasts, with refit, seed and member identities.
- [Result record](mrf-nn-result.json): every member's checkpoint/stopping diagnostics and arithmetic checks.
- [Pilot audit](mrf-nn-pilot-audit.json): one member, two epochs and eight dates, with scores suppressed and exact retraining verified.

All 423 local tests pass: 345 ordinary, 53 optional NN and 25 optional real-R contracts. The declaration commit's actual-NN CI job also passed on Linux. All earlier numerical artifacts are unchanged. Every named E1 method now has a completed implementation/run, but that is not a successful reproduction: see the [benchmark scorecard](MRF_BENCHMARK_SCORECARD.md). No Jev/LLM forecast evaluation or hosted forecasting call has run.
