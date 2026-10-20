# Project status and initial experiment record

## October 20: qualified September-vintage MRF authorized

After the plain-RF check below, the user explicitly authorized a qualified
[September-vintage MRF reconstruction](../docs/SEPTEMBER2018_MRF.md). Its
separate runner is implemented, all six 1,037-column states are prepared and
paired with the frozen RF raw preparation/calendar, and the complete local
suite passes 477 tests. A score-suppressed two-tree native preflight and the
18-fit full run are next. The RF failure, missing original series/caller and
earlier MRF results remain unchanged; no new-vintage MRF score is claimed.

## October 20: September 2018 plain RF first

The [new raw-indicator RF run](RF_SEPTEMBER2018.md) is complete and audited:
actual ranger, 500 trees, min.node.size=3, 1,976 raw features, six two-year
refits and 48 target dates. Primary ratios 0.983534/0.971506/0.965598 against
1.00 include one miss outside the fixed 0.03 tolerance. The separately declared
appendix-style diagnostic cannot rescue it. Current-plus-seven and the old
target-indexed L1:L8 are equivalent at h=1; no extra date shift was warranted.
The Fed removed S&P: indust from every historical vintage in 2024, explaining
the available September archive's 247-series count, not proving the cause of
the score gap. No later-vintage series was grafted on. The formatter-only full
repeat and second audit are complete: all 36 full forests and predictions
reproduce byte-for-byte. No September-vintage MRF or Jev/LLM evaluation has run.
The [declaration](../docs/SEPTEMBER2018_RF.md) keeps the data, caller and first-row
uncertainties explicit. All older results below remain historical records.

## Active direction: MRF + Jev

On October 18, 2026, the user selected Goulet Coulombe's *The Macroeconomy as a Random Forest* as the research foundation. The [current protocol](../docs/RESEARCH_PROTOCOL.md) now starts with replication, followed by a joint 25-action adjustment of two MRF factor contributions. Jev can weaken or strengthen those contributions; the forest's other terms remain the reference.

The final 21-page article and 32-page publisher appendix have now been read. The [appendix evidence note](../docs/APPENDIX_FINDINGS.md) records the first Table 4 comparison cells, untuned forest/block settings, six data-rich simulation mechanisms, neural comparators, monthly average-growth targets and source inconsistencies. The primary target remains log-differenced quarterly unemployment h=1; the source FA-ARRF/AR(4) ratio of 0.72 is not our result. Constant recalibration and prespecified strong-comparator secondary tasks have been added to the plan.

The journal archive and author engine are now audited; see the [replication checklist](../docs/MRF_REPLICATION.md) and [code findings](../docs/AUTHOR_CODE_AUDIT.md). The dedicated quarterly loader and external-R adapter are implemented. The original benchmark runner is absent from the inspected public repositories, so the first run is explicitly a reconstruction.

### Quarterly reconstruction: completed first run

Fixed archived vintage, delta log UNRATE, 48 evaluation target dates from 2003Q1 through 2014Q4, expanding estimates from 1961Q3 and six two-year refits. All preprocessing uses the fitting sample; future target values are masked before the R engine is called.

| Model | Forecasts | RMSE | RMSE / AR(4) | Published ratio |
| --- | ---: | ---: | ---: | ---: |
| AR(4) | 48 | 0.0334997102 | 1.000000 | 1.00 |
| Fixed FA-AR | 48 | 0.0272211055 | 0.812577 | 0.83 |
| FA-ARRF, seed 101 | 48 | 0.0267101414 | 0.797325 | 0.72 |
| FA-ARRF, seed 202 | 48 | 0.0269399477 | 0.804184 | 0.72 |
| FA-ARRF, seed 303 | 48 | 0.0270123659 | 0.806346 | 0.72 |
| Mean forest prediction | 48 | 0.0268552416 | 0.801656 | Not a source ensemble |
| ARRF, seed 101 | 48 | 0.0299018061 | 0.892599 | 0.90 |
| ARRF, seed 202 | 48 | 0.0299630207 | 0.894426 | 0.90 |
| ARRF, seed 303 | 48 | 0.0302126367 | 0.901878 | 0.90 |
| Mean ARRF prediction | 48 | 0.0299932625 | 0.895329 | Not a source ensemble |

The original fixed factor regression is close to the printed ratio, not identical. Every original FA-ARRF seed misses the prespecified 0.03 absolute-ratio tolerance, so that run's full numerical-agreement criterion fails. Forest RMSE is only 0.77%–1.88% below its fixed FA-AR; the separately labeled mean-prediction ensemble improves by 1.34%. This does not reproduce the paper's larger nonlinear gain. All 18 jobs and all seeds are retained, with no test-period retuning. See the [completed original result](MRF_UNEMPLOYMENT_RECONSTRUCTION.md), [metrics](mrf-unemployment-metrics.csv), [predictions](mrf-unemployment-predictions.csv) and [full audit](mrf-unemployment-audit.json).

An eight-forecast, two-tree end-to-end pilot completed and passed coefficient reconstruction. It is not a full benchmark result. All 370 local tests passed: 345 ordinary tests and 25 real-R checks, including native two-step TVP covariance/CV/GARCH/forecast and quarterly integration/refit contracts, quarterly plain-control tree/refit/provenance/gate contracts, plain-forest sampling/leaf/timing contracts, native empty-equation rejection, FRED125 preparation/timing/joint-gate guards, independent base-R AR(2)/completion/QR/PCA, direct native-initialization capture, the two-term ARRF equation and the engine's sign sensitivity. CI additionally runs both native estimators, a synthetic-boundary TVP integration/refit and a bounded quarterly MRF smoke/audit, not the full forest benchmark. Local runtime: R 4.6.1 and pracma 2.4.6; TVP requires fGarch 4052.93 and matrixcalc 1.0-6. Each native fit records all loaded namespace versions.

The October 19 final audit independently checked all 48 linear forecasts in R (maximum difference 1.5e-15), recomputed all six complete state matrices (maximum difference 3.6e-15), checked all eight target lags against archived levels, and verified coefficient decompositions for all 18 forest jobs (maximum difference 2.5e-15). It verified aggregate forecasts and metrics and confirmed the failed numerical-agreement criterion. Unknown original preprocessing remains a separate limitation regardless of score agreement.

The earlier [preliminary integrity snapshot](mrf-unemployment-preliminary-audit.json) verified eight of eighteen forest jobs, with maximum coefficient-reconstruction error 1.3e-15. It is an immutable progress snapshot, not a live status indicator or a full performance result; no partial forest RMSE is published in it.

The shared 25-action algebra is now implemented and tested independently of the legacy gate. Identity and uniform probabilities recover all 144 saved individual-seed forest forecasts within 2.5e-15, with no selector or API calls. The algebra accepts only the four equation terms, not actual outcomes; it does not by itself enforce historical availability of caller-supplied evidence.

Still pending: exact source-fidelity reconciliation; the other Table 4 comparators; controlled mechanisms; prequential evidence and the joint-action selector adapters; and hosted Jev/LLM evaluation. Independent tooling proceeds against the preserved qualified baseline, without claiming the original 0.72 result has been reproduced. A completed program run is not automatically an exact replication.

The [ARRF diagnostic is complete](MRF_ARRF_DIAGNOSTIC.md): 0.892599, 0.894426 and 0.901878 against 0.90, all within the declared tolerance. Its [declaration](../docs/ARRF_DIAGNOSTIC.md) predates full outcomes. All 18 jobs and saved aggregates pass the [separate audit](mrf-arrf-diagnostic-audit.json), with coefficient discrepancy at most 6.3e-16. The same rich-state matrices, engine and R adapter were retained. This is a useful comparator match, not evidence that FA-ARRF's 0.72 result or the missing author pipeline has been recovered.

The [PCA basis audit](../docs/PCA_BASIS_AUDIT.md) independently compares Python and base R on identical completed training inputs. All retained components match up to signs, but 22/30 cross-sectional and 1,468/2,976 MAF components have opposite signs on this R build. Native split penalties and a synthetic real-engine contract establish sign sensitivity. This narrows one portability issue, not the cause of the macro gap; no basis or forecast has been replaced.

The [R-sign sensitivity is complete](MRF_R_BASIS_SENSITIVITY.md), with its [declaration](../docs/R_BASIS_SENSITIVITY.md) committed before full outcomes. Ratios are 0.786503, 0.783246 and 0.799636; the separately labeled mean-prediction ratio is 0.788647. All three seeds improve modestly relative to their original runs, but all remain outside the declared tolerance around 0.72. Its [full audit](mrf-r-basis-sensitivity-audit.json) verifies all 18 jobs, native R sign maps and exact signed-input equality, with coefficient discrepancy at most 2.7e-15 and unchanged linear forecasts within 1.5e-15. No other information or forest setting changed. The original primary result is preserved, and the original author basis and pipeline remain unknown.

The [PCA-eligibility representation audit](MRF_PCA_ELIGIBILITY_AUDIT.md) completed across all six refits. It fits five PCs on the 125 flagged series of the same all-248 completed panel and changes only the 40 cross-sectional-factor lag columns. The full 1,041-column state and every non-factor entry remain exactly unchanged. Original factor lags reconstruct with zero discrepancy; independent R agrees with the subset loadings up to signs within 2.1e-15. Corresponding first-two training-score correlations are 0.987–0.990 and 0.921–0.955. No forecast loss was calculated or forest fitted in that training-only stage. Its separately declared forecast test is now complete below; neither stage recovers the author's original eligibility rule.

The [full PCA125 sensitivity is complete](MRF_PCA125_SENSITIVITY.md). Ratios are 0.748815, 0.744101 and 0.747069; every forest seed meets the unchanged tolerance around 0.72. The separately labeled mean-prediction ratio is 0.745585. But its own fixed-factor comparator scores 0.787136 versus 0.83 and fails, so the joint criterion remains false. The forest adds only 4.87%–5.47% RMSE improvement over that comparator, not the roughly 13.3% implied by the printed source cells. Combining the old linear model with the new forest would mix factor constructions and cannot establish a pass.

All 18 PCA125 jobs and all 48 dates pass the [full audit](mrf-pca125-sensitivity-audit.json), with coefficient discrepancy at most 2.1e-15 and independent linear-check differences at most 1.5e-15. Exact non-factor preservation, settings, timing, aggregates and metrics verify. The [declaration](../docs/PCA125_SENSITIVITY.md) predates outcomes; this does not stack the R-sign change or replace the primary result. [Metrics](mrf-pca125-sensitivity-metrics.csv), [predictions](mrf-pca125-sensitivity-predictions.csv) and the [full result record](mrf-pca125-sensitivity-result.json) retain every seed. The earlier [pilot audit](mrf-pca125-pilot-audit.json) remains a bounded integrity record, not a score.

An additional actual-native initialization probe now checks the boundary after the author's argument translation, normalization, prior conversion and effective parent-size guard. All six [primary inputs](mrf-primary-native-initialization-audit.json) and six [PCA125 inputs](mrf-pca125-native-initialization-audit.json) pass: four slope terms, 1,041 state variables, 347 candidate states, correct trend position and effective minimum parent size 12. Standardized OLS prior discrepancies are below 1.9e-15. Each isolated probe deliberately stops before noise injection or tree fitting; it does not modify source files or any running forest. The PCA125 record binds the pre-completion manifest and is an initialization snapshot, not a live run-status report or a new forecast result. These checks find no mismatch at this boundary, not proof of the missing author pipeline.

The [FRED source-recipe training audit](../docs/FRED_RECIPE_AUDIT.md) implements the inspected code's jj=2/DEMEAN=2 completion, selecting rank at every EM iteration with bound eight and a 50-iteration cap. On independently completed 125-series training panels, final ranks are 2/3/3/4/4/4 and iteration counts 48/43/36/47/25/25; all converge before the cap. Independent R Gram-eigen calculations agree with Python direct SVD on every rank path and completed matrix, within 4.0e-14 in training-standard-deviation units. Five state PCs and two equation factors remain separate from that completion rank. This is a port of public FRED preparation functions, not execution of MATLAB or recovery of the MRF caller. That training-only stage produced no forest/forecast loss; its separately declared forecast comparison is completed below. The [audit JSON](mrf-fred-recipe-training-audit.json) retains the exact source and numerical evidence.

A separate [FRED125 factor-block forecast test](../docs/FRED125_SENSITIVITY.md) was declared and implemented in `dbd4338` before its own outcomes. It independently completes the 125-series panel with the audited adaptive recipe, changes only the 40 factor-lag columns, keeps the entire primary indicator/MAF state and refits its own fixed-factor comparator. It retains the original dates, forest settings and joint gate, without stacking R signs or selecting a best seed. The [pilot/preparation record](MRF_FRED125_PROGRESS.md) remains a historical integrity snapshot, not live status.

The [full FRED125 comparison is now completed and independently audited](MRF_FRED125_SENSITIVITY.md). Its own fixed FA-AR scores 0.801723 versus 0.83 and passes, but forest ratios 0.746268/0.766320/0.757391 include two failures against 0.72. The joint criterion remains false. Its separate mean-prediction ratio is 0.754493; it cannot rescue the seed rule. Forest RMSE gains over the matching linear model are 4.42%–6.92%, still short of the roughly 13.3% implied by the source cells.

All 18 jobs and 48 dates pass the [full FRED125 audit](mrf-fred125-sensitivity-audit.json), including every reconstructed matrix, exact non-factor preservation, settings, timing and aggregates. Maximum coefficient discrepancy is 1.4e-15 and independent linear-fit differences are below 1.5e-15. [Metrics](mrf-fred125-sensitivity-metrics.csv), [all predictions](mrf-fred125-sensitivity-predictions.csv) and the [result record](mrf-fred125-sensitivity-result.json) retain every seed. All earlier results and the original primary remain unchanged. This composite preparation test does not recover the missing original pipeline; exact reconciliation, nonlinear-gain reproduction and other Table 4 controls remain open. No Jev/LLM forecast evaluation has run.

The remaining-control work has a [source-checked plain-forest core](../docs/RF_MAF_CONTROL.md). Main Tables 1-2 and appendix A.6/Table 4 were rechecked, including table visuals: RF-MAF uses the full state and AR+RF needs a separately fitted AR(2) residual stage. The pinned native MRF rejects an empty linear equation; a real-R contract verifies that boundary. The separate CART primitive implements random-group block subsampling, sampled-only terminal means and uniform prediction averaging, with NumPy/sklearn backend differences and unresolved original settings explicit. Thirty-one core synthetic contracts and four sampling/native-boundary real-R checks pass.

The [quarterly RF-MAF/AR+RF declaration](../docs/PLAIN_CONTROLS.md) and runner were published in commit 2e72a9f before their actual-data outcomes. The bounded pilot passed with accuracy scores suppressed. The [full comparison is now complete](MRF_PLAIN_CONTROLS.md): 36 fits, 3,600 trees and 48 dates. AR+RF ratios 0.851235/0.815388/0.827334 all pass against 0.84. RF-MAF ratios 0.830382/0.824599/0.885091 include one failure against 0.85, so the combined six-cell control criterion fails. No seed or configuration was changed to rescue the miss.

The [full control audit](mrf-plain-controls-audit.json) repeats the primary audit, confirms every unchanged 1,041-column input, checks the training-only AR(2) filter in R, reconstructs sampled-node means and forecasts, and deterministically refits every saved forest. All 36 structures and saved aggregates verify; maximum forecast discrepancy is 2.1e-17. Thirty-nine integration contracts and one additional real-R filter check pass, including altered-artifact rejection and score suppression. [Metrics](mrf-plain-controls-metrics.csv), [720 forecast rows](mrf-plain-controls-predictions.csv), [result record](mrf-plain-controls-result.json) and the [pilot audit](mrf-plain-controls-pilot-audit.json) retain every seed and both separately labeled ensembles. The existing FA-ARRF joint failure, unknown original settings and all earlier numerical artifacts remain unchanged. TV-FAAR and NN quarterly comparisons remain open; no Jev/LLM forecast evaluation has run.

The [native TV-FAAR control](../docs/TVP_FAAR_CONTROL.md) is declared and implemented before macro outcomes. The entire pinned public estimator/help file and the main specification/analysis pages were inspected. This is the nine-coefficient factor regression, not the five-coefficient MRF equation. Its two-step ridge/CV/GARCH estimator is called externally; independent covariance/CV/weight/forecast calculations and a complete native repeat verify it. Both actual tuning stages, namespace versions and optimizer convergence codes are recorded. The six original two-year forecast refits are retained; the 2007Q2 interpretation context is not substituted for the forecast experiment. Fifty new contracts pass, including eight actual-TVP contracts; no real-data TV-FAAR pilot or full scores have run at this declaration. The original FA-ARRF requirement remains open.

Following that declaration, the [full native TV-FAAR comparison completed](MRF_TVP_FAAR.md): six refits, all 48 dates and ratio 0.942195 versus 1.19, outside tolerance. All six native GARCH optimizers return non-convergence code 1. The [full audit](mrf-tvp-faar-audit.json) repeats the primary audit, independently reconstructs both ridge/CV stages, weights, volatility recursion and forecasts, then identically reproduces every native artifact in six fresh R fits. Arithmetic agreement does not establish optimizer convergence. The final two windows' actual second-stage lambda differs from the public first-stage return; both are recorded.

The [336 predictions](mrf-tvp-faar-predictions.csv), [metrics](mrf-tvp-faar-metrics.csv), [result record](mrf-tvp-faar-result.json) and score-suppressed [pilot audit](mrf-tvp-faar-pilot-audit.json) retain all outputs and warnings. No retry, fallback or score-based change was used. The original primary and earlier results remain unchanged. The TV-FAAR printed cell, optimizer-quality boundary and exact caller remain unreconciled; NN is the remaining unimplemented E1 comparator. The main FA-ARRF joint criterion and nonlinear gain remain unmet, and no Jev/LLM forecast evaluation has run.

The [appendix NN control](../docs/NN_CONTROL.md) is now declared and implemented, before any actual-data NN pilot or full outcomes. It uses all 1,041 unchanged state columns, five 100-unit ReLU hidden layers and a 10-member forecast ensemble per seed/refit: 180 networks across the six original refits and three retained seeds. Appendix-supported settings and our missing-detail assumptions are separated explicitly. Numeric-only checkpoints are independently evaluated with NumPy, and the final audit must repeat every training exactly. Random 85% validation is not presented as chronological policy validation; no target scaling or later HNN settings are silently imported.

All 423 local checks pass: 345 ordinary, 53 optional NN and 25 optional real-R. New checks include independently calculated derivatives/Adam updates, actual best-checkpoint restoration, exact retraining, substitute-model rejection, all-member aggregation and score suppression for reduced/incomplete runs. The original FA-ARRF failure and all earlier results are preserved. No macro NN forecasts or new performance scores exist at this declaration; no Jev/LLM forecast evaluation has run.

Following declaration commit 42fe535, the [full NN comparison completed](MRF_NN.md): 180 networks, 18 ten-member ensembles and all 48 dates. Ratios 0.793326/0.842565/0.801268 include a seed-202 miss against 0.80. The separate outer-seed mean 0.806908 is excluded from the criterion; no seed or setting changed. Every member stopped by the declared patience rule, restored its best checkpoint and passed independent NumPy arithmetic. The [full audit](mrf-nn-audit.json) repeats the primary audit, reconstructs all aggregates and **retrains every network identically**, including every parameter and complete training history. Independent base-R scores agree within 1.2e-16 in ratio units.

[All member forecasts](mrf-nn-member-predictions.csv), [480 aggregate rows](mrf-nn-predictions.csv), [metrics](mrf-nn-metrics.csv), [result record](mrf-nn-result.json) and score-suppressed [pilot audit](mrf-nn-pilot-audit.json) retain the complete outcome. All eight named E1 methods now have completed implementations/runs; the [scorecard](MRF_BENCHMARK_SCORECARD.md) separates that milestone from successful reproduction. The primary FA-ARRF joint criterion/nonlinear gain, source-fidelity unknowns and TVP optimizer quality remain unresolved. No Jev/LLM forecast evaluation or hosted forecasting call has run.

The later [native-normalization boundary probe](../docs/NATIVE_NORMALIZATION_BOUNDARY.md) checks twelve actual initializations, with no tree fitting or new forecast scores. In all six native all-row cases, the source's already-rescaled-slope intercept calculation differs from normalized-equation OLS; the maximum offset is 0.005296 in native standardized target units. Slopes agree, and our original training-only path's complete prior agrees within 3.4e-16. Independent NumPy moments/prior calculations agree with the captured R quantities within 5.4e-15. The [JSON](mrf-native-normalization-boundary.json) and [CSV](mrf-native-normalization-boundary.csv) retain every case and unchanged input/source hashes. This verifies an interaction, not its forecast effect, and does not repair source code, use future targets or change the baseline. Three added actual-R contracts bring the current full local suite to 426 (345 base, 53 NN, 28 R).

The source-backed [native-helper forecast diagnostic](../docs/NATIVE_ALLROWS_DIAGNOSTIC.md) is now declared and implemented before its actual-data pilot/full outcomes. The wrapper verifies exact matrix and linear-forecast preservation before launching a forest, permits only the helper selection (plus reduced pilot caps), retains all seeds and the original source-cell rule, and rejects provenance/runtime drift. It leaves the native prior conversion untouched and explicitly labels later block covariates as non-causal; it cannot replace the primary. Twenty-five additional contracts pass, including a reduced-run score-suppression guard even when an upstream completion signal is wrong. No macro forecast for this diagnostic exists at declaration.

Following declaration commit 785ea66, the [two-tree/eight-date pilot audit](mrf-native-helper-pilot-audit.json) passed, with original-unit reconstruction error below 4.6e-16 and performance suppressed. The full cohort's [initial audit](mrf-native-helper-initial-audit.json) independently rebuilds six matrices and verifies all 18 byte-identical input pairings. At that snapshot no full forest is completed and no full accuracy conclusion exists. The [progress record](MRF_NATIVE_HELPER_PROGRESS.md) documents launch of the 18-case/100-tree run and direct confirmation of its four active R workers; it is not a live status page. All 451 local tests pass. The code/configuration and every earlier result remain frozen; the main objective is not complete.

A bounded [public-reconstruction source check](../docs/INDEPENDENT_RECONSTRUCTION_CHECK.md) completed while the native-helper workers were fitting. The pinned independent driver's reported h=1 FA-AR/FA-ARRF ratios are 0.924/0.872, not the reference 0.83/0.72. Its vintage, settings, external cache and label convention differ; none is substituted into our experiment. The [static record](mrf-independent-driver-source-audit.json) preserves source hashes and a conditional date illustration, without running external models or claiming to reproduce their scalar results. This check does not recover the original author caller, and no live diagnostic setting was changed.

The later [interim native-helper audit](mrf-native-helper-interim-audit.json) verifies four completed 100-tree cases, with maximum coefficient-reconstruction discrepancy below 6.8e-16 and R/pracma versions matching the primary. Fourteen cases remain pending in that snapshot, and no accuracy or numerical-pass field is published. All six matrices and all 18 pairings still verify. The [interim note](MRF_NATIVE_HELPER_INTERIM.md) records direct observation of four workers on subsequent cases; it does not replace the immutable initial snapshot or declare a reproduction result.

The final article's full printed pages 408–409 were then rechecked visually for the remaining timing question. Its Section 3 RMSE formula indexes OOS by actual target date t, comparing against the forecast made at t-h; Table 2's h=1 lag structure supports our locked target-date convention. The [source note](../docs/INDEPENDENT_RECONSTRUCTION_CHECK.md#timing-boundary) distinguishes that paper evidence from the independent driver's conditional illustration. No date, code, setting or forecast was changed, and the missing executable caller and numerical gap remain unresolved.

The [full native-helper diagnostic has now completed](MRF_NATIVE_HELPER_DIAGNOSTIC.md): all 18 forests, 1,800 trees and 48 dates. Ratios 0.799509/0.811123/0.808302 all miss 0.72, with the matching FA-AR unchanged at 0.812577. Every native-helper seed has slightly higher RMSE than its original paired run; gains over FA-AR are only 0.18%–1.61%. The separate mean ratio is 0.805532 and cannot rescue the failed criterion. No setting, seed or source correction was tried after the outcome.

The [fresh full audit](mrf-native-helper-audit.json) rebuilds all six matrices, verifies all 18 exact pairings and runtime versions, checks original-unit coefficient decompositions within 2.7e-15, and recomputes every saved aggregate/result flag. Independent base-R rescoring agrees within 1.2e-16 in ratio units; all 18 stderr logs are empty. [Metrics](mrf-native-helper-metrics.csv), [all 288 predictions](mrf-native-helper-predictions.csv) and the [result record](mrf-native-helper-result.json) retain every seed. The initial/interim records remain dated snapshots, not live status. This narrows the effect of selecting the native helper behind the same adapter; its future block covariates remain non-causal, and no original caller is recovered. The primary, all earlier numerical artifacts and the still-unmet benchmark objective are unchanged.

The original code and results below are retained as a historical scaffold. The 32 existing tests validate that scaffold, not the new MRF study. No numerical result below is relabeled as MRF or Jev evidence.

## Original scaffold results

Verified October 18, 2026. This is an untuned development run, not a confirmatory result. Both supplied configurations completed with zero hosted-model API calls. The source revision is recorded in the run manifests. All 32 tests passed, including future-data perturbation checks and real SDK serialization/parsing using local fake transports.

## Synthetic changing-loadings experiment

Three fixed seeds, 60 forecast origins per seed, 180 forecasts per method. The observed-signal representation uses the four supplied signals; extra noisy measurements are available to multivariate ridge and trees. This setup intentionally makes a changing-coefficient model plausible.

| Method | RMSE |
| --- | ---: |
| Random-walk coefficient Kalman | 1.543567 |
| Exponentially weighted factor ridge | 1.707400 |
| Diagnostic rule gate | 1.858059 |
| Online learned gate | 1.932331 |
| Target-history AR ridge | 1.933577 |
| Expanding factor ridge | 1.935911 |
| Multivariate ridge | 1.949570 |
| Gradient-boosted trees | 2.055984 |
| Rolling factor ridge | 2.113304 |
| Persistence | 2.114738 |
| Zero | 3.197403 |

The Kalman baseline has about 20.3% lower pooled RMSE than the expanding factor regression. This is a descriptive result without a paired uncertainty interval. It demonstrates that an adaptive conventional model is a serious comparator. It does not demonstrate that Jev adds value. The learned gate begins cold and only trains as past evaluated cases mature.

## FRED-MD development experiment

Pinned September 2026 vintage; transformed INDPRO target; one-month point horizon; one-month availability lag; four PCA factors; 60 origins, every three months from January 2010 through October 2024. Predictions target the following month. Data are revised historical values, not a reconstruction of information available at each date.

| Method | RMSE, log-growth units |
| --- | ---: |
| Zero growth | 0.006872 |
| Gradient-boosted trees | 0.007572 |
| AR ridge | 0.008680 |
| Diagnostic rule gate | 0.009718 |
| Online learned gate | 0.009782 |
| Exponentially weighted factor ridge | 0.009783 |
| Expanding factor ridge | 0.010116 |
| Rolling factor ridge | 0.012119 |
| Persistence | 0.013522 |
| Multivariate ridge | 0.014474 |
| Random-walk coefficient Kalman | 0.023389 |

The zero-growth baseline is best in this configuration. This pilot **does not establish a factor forecasting advantage on this target/horizon**. FRED-MD remains a literature-motivated research candidate rather than a validated favorable benchmark for our exact setup.

At the time of this run, a longer-horizon specification was proposed as a next step. That direction is superseded by the user's selection of the MRF paper. This table remains part of the record. The large Kalman error also warrants development-period tuning before using that implementation in any broader comparison.

## Hosted models

Jev and LLM forecasts have not been run because their API credentials were unavailable. The adapters passed local contract tests, but actual service access, numerical calibration, latency, cost, and forecasting quality remain unverified. There are no Jev/LLM scores in the tables and no mock results presented as real model results.

## Reproduction

```bash
uv sync --frozen --extra api
uv run --frozen --extra api pytest
uv run jev-factor download-fred
uv run jev-factor run --config configs/synthetic.json --output runs/synthetic-baseline
uv run jev-factor run --config configs/fred_md.json --output runs/fred-baseline
```

Published CSV summaries preserve all methods, per-seed metrics, exact configurations, and manifests. Shared preprocessing is excluded from the model timing column. Timings are local measurements and are not valid hosted-model latency comparisons. Raw FRED data, decision states and API caches stay local. No significance or universal ranking is claimed.
