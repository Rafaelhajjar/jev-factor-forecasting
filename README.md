# Jev + Macroeconomic Random Forests

Can Jev improve a Macroeconomic Random Forest's forecast by identifying when its factor contributions should be stronger or weaker?

This project builds on **Philippe Goulet Coulombe's [The Macroeconomy as a Random Forest](https://doi.org/10.1002/jae.3030), Journal of Applied Econometrics, 2024**. We start by reconstructing its benchmark. The main experiment then adds Jev to the reference forest and tests whether it improves forecasts beyond the forest itself; any unresolved replication boundary stays explicit.

**Status:** the joint unemployment replication criterion still fails. The completed PCA125 sensitivity now puts every forest seed within our declared tolerance around 0.72, but its matching fixed FA-AR is 0.787 versus 0.83 and fails. We retain every run and the original primary result. No Jev or LLM forecast evaluation has run. [Latest completed result](reports/MRF_PCA125_SENSITIVITY.md), [source audit and assumptions](docs/AUTHOR_CODE_AUDIT.md).

All three constructions cover 48 quarters and pass complete artifact audits. The diagnostic requires the fixed FA-AR and **every** individual forest seed to be within 0.03 of 0.83 and 0.72, respectively. This is our diagnostic, not an author standard or statistical test.

| Construction | Fixed FA-AR / AR(4) | FA-ARRF / AR(4), all three seeds | Joint criterion |
| --- | ---: | ---: | --- |
| [Original all-248 PCA](reports/MRF_UNEMPLOYMENT_RECONSTRUCTION.md) | 0.812577 | 0.797325–0.806346 | Fails: forests |
| [Recorded R signs only](reports/MRF_R_BASIS_SENSITIVITY.md) | 0.812577 | 0.783246–0.799636 | Fails: forests |
| [PCA125, full indicator/MAF state retained](reports/MRF_PCA125_SENSITIVITY.md) | 0.787136 | 0.744101–0.748815 | Fails: fixed FA-AR |

Do not combine the original linear score with the PCA125 forest to claim a pass: they use different factor constructions. The PCA125 forest improves on its own fixed-factor comparator by 4.87%–5.47%, still short of the roughly 13.3% implied by the source ratios. These post-primary sensitivities do not recover the missing original pipeline or replace the primary result.

The separate [ARRF diagnostic](reports/MRF_ARRF_DIAGNOSTIC.md) scores 0.892599/0.894426/0.901878 against 0.90, all within tolerance. That comparator match cannot establish the factor-augmented result. The [basis audit](docs/PCA_BASIS_AUDIT.md), [eligibility audit](reports/MRF_PCA_ELIGIBILITY_AUDIT.md) and [PCA125 declaration](docs/PCA125_SENSITIVITY.md) distinguish training evidence, fixed controls and forecast outcomes.

A [training-only FRED-recipe audit](docs/FRED_RECIPE_AUDIT.md) now reconstructs the public preparation code's adaptive completion instead of fixing rank at five. Applied independently to the 125-series panel, it selects ranks 2/3/3/4/4/4 and converges within 50 iterations in all six windows; independent R calculations agree. No new forecast score is available, and this is not proof of the MRF author's original preprocessing.

A separate [FRED125 forecast experiment](docs/FRED125_SENSITIVITY.md) is now declared and implemented before its outcomes. It changes only the factor block, keeps the entire original indicator/MAF state, and fits its own matching linear comparator. This is a composite preparation check, not a pure rank change or recovery of the missing author runner. All earlier results remain frozen; no FRED125 forecast result is available at declaration.

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

The suite has 233 ordinary tests plus 12 optional real-R checks, including independent completion/linear/PCA calculations, actual native-initialization capture and the engine's sign sensitivity. All 245 passed locally, including FRED125 preparation-only/recipe/joint-gate guards, FRED-recipe stopping/timing contracts, PCA125 job/setting/score-suppression guards, PCA-only eligibility preservation, orientation/ARRF provenance guards, action algebra, changed-input, checkpoint and artifact-verifier guards. To enable the R contracts:

```bash
JEV_MRF_REFERENCE_ENGINE=data/raw/MRF_v210403.R \
JEV_MRF_R_LIBRARY=runs/r-library \
uv run pytest -q
```

CI includes real-R contracts and a bounded two-tree/eight-quarter integration smoke with artifact verification, not the full expensive macro benchmark. The existing `configs/synthetic.json` and `configs/fred_md.json` still run the original smoke-test harness. Their three-action gate and four-factor monthly setup do not implement the new Jev study. See the [archived scaffold guide](docs/LEGACY_SCAFFOLD.md) and [results record](reports/STATUS.md).

Model credentials are needed when the new integration reaches its API pilot; they are not needed for this reconstruction. No hosted forecasting calls have been made.

Our code is MIT licensed. Author implementations and data retain their own licenses and attribution requirements. This independent project is not endorsed by Goulet Coulombe, TypeSafe or the Federal Reserve. [Sources and evidence boundaries](docs/SOURCES.md).
