# Project status and initial experiment record

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

An eight-forecast, two-tree end-to-end pilot completed and passed coefficient reconstruction. It is not a full benchmark result. All 201 local tests passed: 189 ordinary tests and 12 real-R checks, including independent base-R completion/QR/PCA, direct native-initialization capture, the two-term ARRF equation and the engine's sign sensitivity. CI additionally runs a bounded quarterly smoke and artifact audit, not the full forest benchmark. Local runtime: R 4.6.1 and pracma 2.4.6; each job records its runtime separately.

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

The [FRED source-recipe training audit](../docs/FRED_RECIPE_AUDIT.md) now implements the inspected code's jj=2/DEMEAN=2 completion, selecting rank at every EM iteration with bound eight and a 50-iteration cap. On independently completed 125-series training panels, final ranks are 2/3/3/4/4/4 and iteration counts 48/43/36/47/25/25; all converge before the cap. Independent R Gram-eigen calculations agree with Python direct SVD on every rank path and completed matrix, within 4.0e-14 in training-standard-deviation units. Five state PCs and two equation factors remain separate from that completion rank. This is a port of public FRED preparation functions, not execution of MATLAB or recovery of the MRF caller. No new forest/forecast loss has been produced; any full comparison needs a separate declaration and matching linear comparator. The [audit JSON](mrf-fred-recipe-training-audit.json) retains the exact source and numerical evidence.

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
