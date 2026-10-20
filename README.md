# Jev + Macroeconomic Random Forests

Can Jev improve a Macroeconomic Random Forest's forecast by identifying when its factor contributions should be stronger or weaker?

This project builds on **Philippe Goulet Coulombe's [The Macroeconomy as a Random Forest](https://doi.org/10.1002/jae.3030), Journal of Applied Econometrics, 2024**. We start by reconstructing its benchmark. The main experiment then adds Jev to the reference forest and tests whether it improves forecasts beyond the forest itself; any unresolved replication boundary stays explicit.

**Status:** all eight named E1 methods have completed runs, but the unemployment replication criterion still fails. The latest native-helper diagnostic is also complete: 0.799509/0.811123/0.808302 versus 0.72, all misses. It does not close the gap or replace the original primary. NN also has one seed miss, and native TV-FAAR has unresolved optimizer warnings. We retain every run. No Jev or LLM forecast evaluation has run. [Complete benchmark scorecard](reports/MRF_BENCHMARK_SCORECARD.md), [native-helper result](reports/MRF_NATIVE_HELPER_DIAGNOSTIC.md), [source audit and assumptions](docs/AUTHOR_CODE_AUDIT.md).

**October 20 follow-up:** the [September 2018 plain-RF reconstruction](reports/RF_SEPTEMBER2018.md) now uses actual ranger, 500 trees, minimum split-node size 3 and the raw-indicator feature set. Ratios 0.983534/0.971506/0.965598 versus 1.00 are close, but one seed misses our declared tolerance. The currently served vintage has 247 series because the Fed removed S&P: indust from all vintages in 2024. [RF settings, alignment and remaining assumptions](docs/SEPTEMBER2018_RF.md).

The user has now authorized [MRF as an explicitly qualified reconstruction](docs/SEPTEMBER2018_MRF.md), not a claim that RF reproduced. The separate runner preserves the RF vintage/calendar and pairs raw preprocessing, then adds the 1,037-column rich state and the five-coefficient equation. It retains MRF's declared 100 trees and three seeds, not ranger's settings. A score-suppressed preflight and full 18-fit run are the next execution steps; no new-vintage MRF result is claimed yet.

All five FA-ARRF reconstruction checks cover 48 quarters and pass complete artifact audits. The diagnostic requires the matching fixed FA-AR and **every** individual forest seed to be within 0.03 of 0.83 and 0.72, respectively. This is our diagnostic, not an author standard or statistical test. The native-helper path is separately labeled non-causal.

| Construction | Fixed FA-AR / AR(4) | FA-ARRF / AR(4), all three seeds | Joint criterion |
| --- | ---: | ---: | --- |
| [Original all-248 PCA](reports/MRF_UNEMPLOYMENT_RECONSTRUCTION.md) | 0.812577 | 0.797325–0.806346 | Fails: forests |
| [Recorded R signs only](reports/MRF_R_BASIS_SENSITIVITY.md) | 0.812577 | 0.783246–0.799636 | Fails: forests |
| [PCA125, full indicator/MAF state retained](reports/MRF_PCA125_SENSITIVITY.md) | 0.787136 | 0.744101–0.748815 | Fails: fixed FA-AR |
| [FRED125 adaptive preparation, full indicator/MAF state retained](reports/MRF_FRED125_SENSITIVITY.md) | 0.801723 | 0.746268–0.766320 | Fails: two forest seeds |
| [Native inner helper only, non-causal](reports/MRF_NATIVE_HELPER_DIAGNOSTIC.md) | 0.812577 | 0.799509–0.811123 | Fails: forests |

Do not combine the original linear score with the PCA125 forest to claim a pass: they use different factor constructions. The PCA125 forest improves on its own fixed-factor comparator by 4.87%–5.47%, still short of the roughly 13.3% implied by the source ratios. These post-primary sensitivities do not recover the missing original pipeline or replace the primary result.

The separate [ARRF diagnostic](reports/MRF_ARRF_DIAGNOSTIC.md) scores 0.892599/0.894426/0.901878 against 0.90, all within tolerance. That comparator match cannot establish the factor-augmented result. The [basis audit](docs/PCA_BASIS_AUDIT.md), [eligibility audit](reports/MRF_PCA_ELIGIBILITY_AUDIT.md) and [PCA125 declaration](docs/PCA125_SENSITIVITY.md) distinguish training evidence, fixed controls and forecast outcomes.

A [training-only FRED-recipe audit](docs/FRED_RECIPE_AUDIT.md) reconstructs the public preparation code's adaptive completion instead of fixing rank at five. Applied independently to the 125-series panel, it selects ranks 2/3/3/4/4/4 and converges within 50 iterations in all six windows; independent R calculations agree. That training stage calculated no forecast loss and is not proof of the MRF author's original preprocessing.

The separate [FRED125 forecast experiment](docs/FRED125_SENSITIVITY.md), declared before its outcomes, is now [fully completed and audited](reports/MRF_FRED125_SENSITIVITY.md): all 18 jobs and all 48 dates verify. It changes only the factor block, keeps the entire original indicator/MAF state and fits its own matching linear comparator. The forest's incremental RMSE reduction is 4.42%–6.92%, still below the roughly 13.3% implied by the printed source cells. This is a composite preparation check, not a pure rank change or recovery of the missing author runner. All earlier results remain frozen.

The separately declared [RF-MAF/AR+RF comparison is complete and fully audited](reports/MRF_PLAIN_CONTROLS.md): all 36 fits, 3,600 trees and 48 dates. AR+RF ratios 0.851235/0.815388/0.827334 all pass against 0.84. RF-MAF ratios 0.830382/0.824599/0.885091 include one failure against 0.85, so the combined six-cell control criterion fails. The [runner declaration](docs/PLAIN_CONTROLS.md) predates outcomes; every saved forest passes direct traversal, sampled-node reconstruction and deterministic refitting. Both controls retain all seeds, the unchanged original rich state and explicit backend assumptions. This neither replaces nor establishes the still-failed FA-ARRF replication.

The [native TV-FAAR comparison is complete and fully audited](reports/MRF_TVP_FAAR.md): six refits and 48 dates, ratio **0.942195 versus 1.19**, outside tolerance. **All six native GARCH fits report non-convergence code 1.** Independent covariance/CV calculations and identical full native reruns verify the arithmetic, not optimizer convergence or source fidelity. Both actual tuning stages are retained; the final two refits use a different lambda from the public first-stage return. The [declaration](docs/TVP_FAAR_CONTROL.md) predates outcomes, keeps the original nine-coefficient equation/two-year forecast cadence and qualifies the 2007Q2 interpretation context. The main FA-ARRF replication remains unresolved.

The [appendix NN comparison is complete and fully audited](reports/MRF_NN.md): all 180 networks and 48 dates. Ratios 0.793326/0.842565/0.801268 against 0.80 include one miss; the separately labeled outer-seed mean, 0.806908, cannot rescue it. The [declaration](docs/NN_CONTROL.md) predates outcomes and retains the unchanged 1,041-column state, five 100-unit ReLU layers and 10-member ensembles. Missing early-stopping/preprocessing details remain explicit assumptions. NumPy independently evaluates every saved network, and all 180 complete trainings reproduce identical parameters and histories. The optional CPU-only Torch backend does not establish equivalence with the missing historical NN runner or repair the primary FA-ARRF result.

A [no-tree native-normalization probe](docs/NATIVE_NORMALIZATION_BOUNDARY.md) now isolates another source boundary across all six refits. Native all-row scaling interacts with the pinned source's prior conversion: the intercept differs from correctly transformed OLS, while our training-only path agrees to numerical precision. All twelve actual initializations and independent calculations verify. This changes no result and establishes no forecast effect; native future-block covariates are not silently adopted as a causal baseline.

A separate [native-helper forecast diagnostic](docs/NATIVE_ALLROWS_DIAGNOSTIC.md) is now declared and implemented **before its macro outcomes**. It changes only that helper selection behind the same target-masking/outer-scaling adapter; every prepared matrix byte, representation, linear forecast and other setting must remain paired with the original. It retains all 18 cases, seeds and source-cell criteria, without repairing the native prior formula. Later block covariates make it explicitly non-causal, not a new primary or proof of the missing original caller. No macro pilot or full forecast for this diagnostic has run at declaration.

Following that declaration, the [native-helper full comparison completed and passed its separate artifact audit](reports/MRF_NATIVE_HELPER_DIAGNOSTIC.md): all 18 forests, 1,800 trees and 48 dates. Ratios 0.799509/0.811123/0.808302 all miss 0.72; each seed has slightly higher RMSE than the original. Matching-FA-AR gains are only 0.18%–1.61%. An independent base-R rescore agrees. Exact input/runtime pairing verifies the intended interface change, not a recovered original caller or successful reproduction. The [initial snapshot](reports/MRF_NATIVE_HELPER_PROGRESS.md) remains a historical integrity record; no prior numerical result is replaced.

## The idea we are building on

A Macroeconomic Random Forest (MRF) keeps a linear forecasting equation and learns how its coefficients change with the economic state:

```text
forecast = X(t)' beta(t)
beta(t)  = forest(S(t))
```

`X(t)` contains the terms whose contributions we want to interpret. `S(t)` contains the information used to determine their coefficients. These are different roles: a variable can help identify a regime without being an explicit term in the small forecasting equation.

Our starting point is the final paper's factor-augmented model: an intercept, two target-history terms, and two PCA factors associated with real activity and leading indicators. All five coefficients can vary. The forest sees a richer state, including five PCA factors with their lags, individual indicators and moving-average factors. [Final-source findings](docs/APPENDIX_FINDINGS.md), [implementation documentation](https://mrf-web.readthedocs.io/en/latest/).

## The main extension: MRF + Jev

We keep a frozen reconstructed forest, its estimated factors, and its forecast as the reference. The first run remains the primary independent baseline; these public sensitivity losses do not silently select a replacement. Jev receives a compact account of the current state, the two estimated factor contributions, their recent predictive evidence, and candidate adjustments calculated by code.

For each factor, the initial adjustment menu is:

| Multiplier | Meaning |
| --- | --- |
| 0 | Remove the contribution |
| 0.5 | Halve it |
| 1 | Keep the forest's contribution |
| 1.5 | Increase its magnitude by half |
| 2 | Double its magnitude |

The two factors give **25 joint candidate forecasts**. Jev returns probabilities over the joint alternatives. Code averages their forecasts using those probabilities:

```text
candidate(a,b) = MRF intercept and AR contribution
              + a * MRF factor-1 contribution
              + b * MRF factor-2 contribution

Jev forecast = sum_(a,b) p(a,b | current evidence) * candidate(a,b)
```

This is an extension of the forest's forecast. It can strengthen as well as suppress a factor, addressing a limitation of our earlier shrinkage-only idea. A joint menu elicits both adjustments in one decision. For a linear point forecast, only the marginal mean multipliers matter; a later many-factor version can use per-factor/grouped questions without claiming to recover a joint posterior.

The unmodified forest is inside the menu at `(1,1)`. A uniform distribution over the symmetric grid also recovers its forecast. The initial policy preserves the forest's coefficient signs and cannot restore an effect whose estimated coefficient is zero. Signed or additive adjustments are a later, separately evaluated extension.

Jev selects among precomputed alternatives. It does not estimate PCA factors, calculate correlations, or generate exact coefficients. Its output is a decision distribution, not a posterior over true economic effects. The 25-way task may still exceed its useful numerical judgment; that is a hypothesis to test.

## What we want to learn

1. Does the reconstructed MRF improve on the paper's linear benchmark in our implementation?
2. Does adding Jev improve on that same MRF?
3. Does Jev beat a small learned gate choosing from the same 25 alternatives?
4. Does economic meaning help, beyond anonymous numerical summaries?
5. Does Jev offer a useful accuracy/cost/latency tradeoff against an LLM given the same task?

The decisive comparison is **MRF + Jev versus original MRF**. Beating a fixed regression alone would not establish our contribution. Any later attempt to replace the forest is a separate experiment with a different claim.

## Data and first target

We located and inspected the journal's [replication-data archive](https://doi.org/10.15456/jae.2023321.0115060814). It contains `FREDQD_2019-03.csv` and `FREDMD_2018-01.csv` in levels. The archive contains data, not a complete reproduction script. Its files and hashes are recorded in the [replication checklist](docs/MRF_REPLICATION.md).

The first target remains **quarterly unemployment, one quarter ahead**, using the paper's first difference of log unemployment. The published evaluation covers 2003Q1–2014Q4. Appendix Table 4 reports a factor-augmented MRF/AR(4) RMSE ratio of **0.72**; that is a replication target, not our result. The exact remaining processing/defaults are tracked in the [checklist](docs/MRF_REPLICATION.md).

The appendix strengthens the plan in four ways: six data-rich synthetic mechanisms (including constant coefficients with changing volatility), explicit block-subsampling settings, neural and interaction comparators, and defined monthly average-growth targets. We also add a constant bounded-multiplier control so ordinary recalibration cannot masquerade as dynamic Jev judgment. Prespecified secondary tasks are GDP two quarters ahead, unemployment six quarters ahead, and monthly CPI averaged over the next 12 months. These deliberately include tasks where conventional alternatives are strong.

A fixed archived vintage permits retrospective replication. It does not establish that every observation was available at the historical forecast date. Historical-vintage evaluation and a prospective test remain separate stages.

## Comparisons and execution order

| Stage | Work | Completion requirement |
| --- | --- | --- |
| E0 | Finish the source/code audit | Final PDFs read; resolve remaining processing/defaults and source inconsistencies |
| E1 | Reproduce quarterly unemployment h=1 | Compare to the named Table 4 cells before adding Jev |
| E2 | Controlled synthetic mechanisms | Distinguish changing relevance from changing noise, nuisance signals and unpredictable changes |
| E3 | Common 25-candidate selector comparison | Freeze evidence and prompts; compare MRF, constant/rule/learned policies, Jev and LLM |
| E4 | Prespecified secondary tasks and ablations | Report all tasks, semantic/order sensitivity and refit effects |
| E5 | More factors and stronger validation | Separate 2/4/8-factor scaling, forest replacement, vintage and prospective evidence |

The [research protocol](docs/RESEARCH_PROTOCOL.md) specifies the interventions, controls, evaluation and implementation tasks. The [appendix evidence note](docs/APPENDIX_FINDINGS.md) records exact source locations, ratios, settings and unresolved inconsistencies. A [machine-readable planning manifest](research/mrf_extension_plan.json) records the design; it is not an executable experiment configuration. Source PDFs are not redistributed in this repository.

## What runs today

The new quarterly path uses `configs/mrf_unemployment.json`. It downloads the checksum-pinned journal archive and external GPL R engine on first use. Install R separately, then install the pinned `pracma` dependency into a project-local library:

```bash
uv sync --frozen --extra api
uv run --frozen --extra api pytest
Rscript scripts/setup_mrf_r.R

# Bounded end-to-end pilot: 8 forecast dates, not a replication result.
uv run jev-factor replicate-mrf --output runs/mrf-pilot \
  --trees 2 --seeds 101 --max-refits 1

# Full reconstruction: 48 dates, 6 refits, 100 trees and all 3 declared seeds.
uv run jev-factor replicate-mrf --output runs/mrf-unemployment --workers 4

# Resume the exact same run after interruption; changed inputs are rejected.
uv run jev-factor replicate-mrf --output runs/mrf-unemployment --workers 4 --resume

# Verify full artifacts, raw-data timing, state reconstruction and independent R OLS.
uv run jev-factor audit-mrf --run runs/mrf-unemployment \
  --output reports/mrf-unemployment-audit.json
```

The R engine is computationally expensive. `--prepare-only` writes inputs and linear benchmarks without fitting forests. Outputs include configuration/source hashes, forecasts, coefficients, per-seed metrics and R runtime information. Keep all seeds; a seed-mean forecast is separately labeled and is not the paper's reported forest.

The shared 25-action algebra is implemented in `jev_factor.mrf_actions`: stable action IDs, original-unit coefficient contributions, strict probability validation and weighted forecasts. It accepts no actual-outcome field. Identity and uniform policies reproduce all 144 saved individual-seed forest forecasts within 2.5e-15. This is a mathematical integration check, not a Jev result. Recheck it without fitting forests or calling any hosted model:

```bash
uv run python scripts/check_mrf_action_identity.py --run runs/mrf-unemployment
```

Prequential evidence cards, joint-action selector adapters and the controlled-mechanism study still need implementation. The legacy hosted adapter is not yet a 25-choice MRF policy.

`audit-mrf` rejects incomplete runs by default. `--allow-partial` permits progress checks but withholds partial forest scores and any numerical reproduction pass. It recalculates all inputs and metrics, checks each coefficient decomposition, and independently compares Python least squares with base-R QR regression. Numerical agreement requires FA-AR and every individual declared seed to be within 0.03 of the corresponding published ratio; the separately labeled seed-mean ensemble cannot satisfy this rule. Agreement is not proof that the missing original preprocessing was recovered.

The suite has 370 ordinary tests, 53 optional neural-network checks and 28 optional real-R checks. All 451 passed locally, including paired native-helper input/provenance/runtime/score-suppression guards; actual neural training/checkpoint restoration, independent derivatives/Adam calculations, deterministic refits and altered-model rejection; native normalization/prior-boundary checks; native two-step TVP covariance/CV/GARCH/forecast and quarterly integration/refit contracts; quarterly plain-control tree/refit/provenance/gate contracts; and the earlier preparation, timing, action-algebra and artifact guards. To enable all checks after the original engines have been fetched:

```bash
Rscript scripts/setup_tvp_r.R runs/r-library
uv run python -c "from pathlib import Path; from jev_factor.tvp_ridge import ensure_tvp_engine; ensure_tvp_engine(Path('data/raw/MV2SRR_v210407.R'))"
JEV_MRF_REFERENCE_ENGINE=data/raw/MRF_v210403.R \
JEV_TVP_REFERENCE_ENGINE=data/raw/MV2SRR_v210407.R \
JEV_MRF_R_LIBRARY=runs/r-library \
uv run --frozen --extra api --extra nn pytest -q
```

CI includes actual NN training/refits against a synthetic source boundary, both native R estimators, a synthetic-boundary TVP integration/refit and a bounded two-tree/eight-quarter MRF smoke with artifact verification, not the full expensive macro benchmark. The existing `configs/synthetic.json` and `configs/fred_md.json` still run the original smoke-test harness. Their three-action gate and four-factor monthly setup do not implement the new Jev study. See the [archived scaffold guide](docs/LEGACY_SCAFFOLD.md) and [results record](reports/STATUS.md).

Model credentials are needed when the new integration reaches its API pilot; they are not needed for this reconstruction. No hosted forecasting calls have been made.

Our code is MIT licensed. Author implementations and data retain their own licenses and attribution requirements. This independent project is not endorsed by Goulet Coulombe, TypeSafe or the Federal Reserve. [Sources and evidence boundaries](docs/SOURCES.md).
