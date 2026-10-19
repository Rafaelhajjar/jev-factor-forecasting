# Research protocol: extending Macroeconomic Random Forests with Jev

Updated October 19, 2026 after reading the published article, its 32-page appendix and the public author engine. This supersedes the [initial generic factor-gating protocol](LEGACY_PROTOCOL.md). The first quarterly reconstruction is complete but misses the source forest ratio; the new Jev study remains a plan, not an external preregistration. The [completed result](../reports/MRF_UNEMPLOYMENT_RECONSTRUCTION.md), [appendix note](APPENDIX_FINDINGS.md) and [code audit](AUTHOR_CODE_AUDIT.md) separate results, source facts, reconstruction choices and unresolved discrepancies.

## 1. Research claim

Test whether Jev can improve a replicated Macroeconomic Random Forest (MRF) by selecting bounded adjustments to its factor contributions from observed economic evidence.

The primary intervention is **MRF + Jev**. The original MRF already adapts its coefficients, so Jev must show value beyond that adaptation. A forest-replacement experiment is secondary and must not be pooled with the hybrid experiment.

We are extending [Goulet Coulombe (2024)](https://doi.org/10.1002/jae.3030), not claiming that dynamic coefficients or probabilistic forecast combination are new. No finding about the benefit of Jev has been established.

## 2. Replication before extension

Use the [replication checklist](MRF_REPLICATION.md) as the first implementation milestone. The final 2024 article and its publisher-supplied appendix have now been read. They replace the earlier arXiv draft as the specification source. Do not silently mix source versions, forecast tables and coefficient-anatomy figures.

The archived data are available and hashed. Main Section 3 and Tables 1–2 establish quarterly FRED-QD with 248 series, expanding estimation from 1961Q3, evaluation target dates 2003Q1–2014Q4 and direct horizons 1, 2, 4, 6 and 8 quarters. The main models are re-estimated every two years. Confirm exact forecast-origin indexing and each method's invocation in reference code; do not replace this schedule with an every-origin refit while calling it a reproduction.

FA-ARRF has an intercept, two target-history terms and one design-row value for each of two PCA factors; all five coefficients can vary. The factors are associated with real activity and leading indicators. Its full state includes eight target lags, time, two lags of individual indicators, eight lags of five PCA factors and two moving-average factors per indicator. Small X(t) and rich S(t) are deliberately different.

The first target remains unemployment at horizon 1 quarter. The article explicitly applies a log before first differencing unemployment: the primary target is delta log unemployment, not its level or percentage-point change. Appendix Table 4 reports FA-ARRF/AR(4) RMSE = 0.72, fixed FA-AR = 0.83 and NN = 0.80. Reproduce these cells and the additional controls recorded in the evidence note. They are rounded source results, not results of our implementation. Predeclare seeds and numerical tolerances before reproducing them; do not choose a seed or tune a forest until it matches 0.72.

Appendix A.6 says the main RFs were untuned. Preserve that reference and its published block scheme: 75% subsampling, block parameter 8 quarters (24 months), nominal minimum parent size 10 quarterly (15 monthly), and ridge prior means based on OLS. The pinned engine defaults to RWR 0.75, ridge 0.1, MLF 1, trend push 1, mtry 1/3, 50 trees and block parameter 12. Its FA-ARRF parent-size floor raises 10 to 12. The first run explicitly overrides blocks to 8, supplies an OLS prior, and declares 100 trees with seeds 101/202/303. Recommendations of 100 trees for means or 200–300 for bands do not establish exact per-table invocations. The separately tuned 1998–2002 exercise is not the main reference.

The author's R package is an implementation, not a complete reproduction pipeline. The [audit](AUTHOR_CODE_AUDIT.md) verifies the archive's header repair and historical Stock-Watson metadata semantics, while qualifying unknown original factor eligibility, missing/outlier handling, PCA orientation and method-specific invocations. The first reconstruction uses all 248 series and training-only fixed-rank-five EM/PCA. Its normalization override deliberately removes the native interface's dependency on future forecast-row covariates. These choices are explicit, not recovered source facts.

The reconstruction's absolute RMSE-ratio tolerance of 0.03 was fixed before inspecting full forest scores; it is our diagnostic threshold, not an author standard or a statistical test. All seeds are retained and the mean-prediction ensemble is labeled separately. The fixed FA-AR/AR(4) ratio is 0.812577 on all 48 quarters versus the paper's rounded 0.83. Forest ratios are 0.797325, 0.804184 and 0.806346 versus 0.72: the full criterion fails. Artifact integrity passes, but neither the score nor missing source settings are reconciled. Target-count, monthly denominator, synthetic sample-length and TV-FAAR discrepancies also remain open. Independent tooling can proceed against this qualified baseline without waiting; a later Jev comparison must not be described as extending an exactly replicated paper result. Report limits rather than attribute them to Jev.

The original retrospective sample is a replication/development benchmark. Its outcomes are public and it cannot be described as a new blind test for a pretrained model.

### Experiment sequence

| ID | Experiment | Decision or deliverable |
| --- | --- | --- |
| E0 | Final-source and pinned-code audit | Lock the remaining settings and resolve or explicitly qualify inconsistencies |
| E1 | Quarterly unemployment h=1 reproduction | Compare AR, FA-AR, FA-ARRF, RF-MAF, ARRF, AR+RF, TV-FAAR and NN to Table 4 |
| E2 | Appendix-inspired controlled mechanisms | Test changing coefficients versus changing noise, irrelevant state variables and unexpected changes before interpreting economic results |
| E3 | Primary two-factor MRF + selector comparison | Compare unchanged forest, constant recalibration, rules, learned selectors, Jev and LLM under frozen evidence and options |
| E4 | Prespecified robustness and secondary tasks | GDP h=2, unemployment h=6, monthly CPI h=12; semantic, ordering, history and refit ablations |
| E5 | Scaling and stronger validation | 2/4/8-factor extensions, separate forest replacement, historical vintages and prospective validation |

E0–E2 are implementation/diagnostic gates, not claims of Jev superiority. Pilot prompts on development cases only, freeze them before E3, and do not discard unfavorable E4 tasks. Broader testing does not depend on finding a favorable E3 score, although hosted execution depends on a declared budget.

## 3. Scientific motivation

The statistical model may estimate useful relationships while still making state-dependent errors about their current magnitude. Jev could bring a transferable prior for interpreting compact economic evidence, especially when several weak signs need to be considered together. A soft combination of candidate adjustments could be more stable than choosing one action with certainty.

This is plausible, not guaranteed. Jev receives no new outcome information from a verbal description of the same numbers. A learned statistical gate may use the evidence better. The forest may already capture the relevant interactions; a second layer may add noise or double-count a regime signal. The joint task may be too numerical or too uncertain for Jev's useful capabilities. All of those are valid failure explanations to test.

A.2 motivates a more specific mechanism hypothesis: a useful selector distinguishes predictable changes in coefficients from irrelevant covariates and changing residual variance. A.7.1 adds a limitation: a changing economic state under a stable coefficient map is not the same as a change in that map. Separate frozen-map and periodically re-estimated experiments; don't expect semantic judgment to foresee an independent, unobserved break.

The current study concerns changes to factor-to-target contributions. It does not ask Jev to reconstruct latent factors or estimate a state-space factor transition model.

## 4. Primary model: MRF + a joint factor policy

At each origin t and horizon h, obtain the replicated MRF's coefficient vector in the current factor basis. Decompose its forecast into:

```text
b(t,h)  = forest intercept + all autoregressive contributions
c1(t,h) = forest coefficient for factor 1 * its design-row value
c2(t,h) = forest coefficient for factor 2 * its design-row value
yhat_MRF = b + c1 + c2
```

The primary adjustment set is M = {0, 0.5, 1, 1.5, 2}. For every pair (a,b) in M x M, code constructs:

```text
candidate_(a,b) = base_AR_intercept + a*c1 + b*c2
```

Use one Choice question over these 25 alternatives. Option descriptions explain the two factor adjustments and refer explicitly to state fields. Ask which candidate is most likely to have the smallest future squared forecast error, using only the available evidence. All candidate arithmetic is completed before the call.

Let p_(a,b) be the returned probability. The policy forecast is the weighted average of the candidate forecasts. Equivalently, factor j receives the probability-weighted mean of its candidate multipliers. Do not assume independence between factors: the distribution is joint by construction.

For this linear point forecast only, the joint distribution affects the answer through its two marginal mean multipliers. Independence is not required for that identity. A many-factor implementation can therefore use per-factor or grouped decisions without enumerating every joint combination; this does not make independently elicited probabilities a validated joint posterior. Keep the two-factor joint question as the initial task and compare the alternative on development data.

This intervention leaves the forest's intercept and AR terms intact and adjusts its two factor terms. A primary result therefore concerns **factor modulation of an existing MRF**, not unconstrained coefficient estimation or replacement of all forest decisions.

Useful identities for implementation:

- A point mass on (1,1) returns the original MRF forecast exactly.
- A uniform distribution also returns it: the average multiplier in M is 1.
- A mixture forecast equals the linear forecast made with the expected multipliers.
- For a fixed origin, all candidates use the same factor values and fitted coefficients.

Increasing a multiplier increases the magnitude of an existing signed contribution. It does not necessarily increase the target forecast. Multipliers do not reverse signs and cannot recover a missing effect when a forest coefficient is zero. Any signed/additive menu is a prespecified follow-up, not a change made after seeing test results.

Uniform recovery is an algebraic property, not an assurance of calibrated uncertainty. A nonuniform but low-confidence response need not recover the baseline. Do not multiply the weights by vendor confidence or add an unvalidated confidence threshold. A failed API call aborts or is recorded as missing; it is not silently counted as a successful baseline forecast.

## 5. Evidence supplied to the decision models

Construct a bounded state card in code, containing:

- Current target history and numeric economic-state summaries with explicit availability cutoffs.
- Current factor values, their loading leaders, and descriptions grounded in those loadings.
- Forest coefficients and the resulting factor/intercept/AR contributions.
- Recent versus longer-run relationship diagnostics, correctly labeled as training diagnostics.
- Completed historical forecast errors and action losses from genuinely prequential cases whose outcomes have matured.
- All 25 computed candidate forecasts, the action definitions and current horizon.

Do not give the language model an ex-post recession label, future target, a full-sample coefficient plot, or the paper's description of what happened next in the historical episode. Begin without news or external text. A later text augmentation must have timestamped sources and information-matched controls.

In particular, don't select the card's indicators from published OOS variable importance or surrogate trees (A.5/A.8). Those explain a completed historical experiment. Any importance-based selection must be recomputed using prior development data; use loading-based/group-level descriptions and deterministic summaries rather than treating one surrogate cutoff as an economic law.

The original MRF continues to use its full specified S(t). A bounded state card is a compressed view of that information. Do not describe the original forest and Jev as receiving identical representations. Jev, the LLM and a newly trained numeric gate must share the same candidate set and numerical card fields; document semantic fields separately. Add a compression-matched forest/gate control to test whether a gain or loss comes from representation.

Factor identities can rotate or swap when PCA is refit. Preserve the original preprocessing for replication, and share its exact resulting basis with every extension method. Sign/reordering adjustments in presentation must transform coefficients consistently and leave forecasts unchanged. Do not use full-sample information to give a factor a permanent economic name. Diagnose unstable subspaces; freezing or aligning a basis beyond the author's procedure is an explicit ablation.

## 6. Comparisons

| Method | What it isolates |
| --- | --- |
| Paper's AR and linear factor benchmarks | The value of factors and conventional adaptation |
| Paper's RF-MAF, ARRF, AR+RF, TV-FAAR and NN | Whether gains require factor modulation rather than ordinary nonlinear or time-varying prediction |
| Replicated factor-augmented MRF | The main reference being extended |
| MRF + uniform action probabilities | An exact identity check against the original forecast |
| MRF + constant bounded multipliers | Whether time-invariant recalibration is sufficient; include constant mixtures/continuous mean multipliers in [0,2], not only single grid actions |
| MRF + diagnostic rule | Whether a transparent mechanical adjustment is sufficient |
| MRF + learned multinomial gate | Whether ordinary supervised learning can choose the same 25 actions |
| MRF + learned loss-based gate | Whether forecasting-loss optimization outperforms winner classification |
| MRF + Jev | The primary proposed extension |
| MRF + LLM | The same structured decision task using a generative model |

Tune learned policies and conventional methods only on chronological development folds with comparable search budgets. Train the learned gates on historical candidate forecasts constructed by past-only model fits, not in-sample residuals from a model fit to the whole development period. Give gates a development warm-up rather than repeating the old scaffold's cold-start comparison.

For E2, retain A.2's PCA-interaction OLS, Lasso interactions and macro neural network (MNN), alongside OLS, rolling OLS, RF and MRF. A.2 specifies a 10-fit neural ensemble, 85% subsampling, batch 32, Adam, learning rate 0.001, up to 100 epochs and early stopping on the omitted 15%. NN has five 100-unit ReLU hidden layers; MNN has four before coefficient-specific output structure. Verify remaining architectural details. Preserve source validation in the reproduction track and use chronological validation in our extension, naming the difference. Adding MNN to real-data tests is a new comparator, not a reported Table 4 result.

The LLM uses the common typed-task adapter with the same frozen state, questions and choices. Pin provider/model/configuration; retain malformed responses, refusals, retries and token usage. Native structured output is permitted. Output validity alone is not a Jev advantage. Record actual latency and billed cost rather than importing vendor speed claims.

## 7. Timing and sample separation

First preserve the paper's exact retrospective timing for a faithful replication. Label fixed-vintage evaluation accurately. Separately build a historical-vintage evaluation that respects actual release timing; a uniform lag cannot recreate that information set.

For the extension, at origin t a training case with origin s is eligible only after its target at s+h is available under the declared release policy. This applies to factor estimation, coefficient fitting, candidate-loss labels, policy fitting, feature selection and calibration. Purge development splits where training labels overlap the validation boundary.

Our proposed quarterly selector split is: prequential training cases with target dates in 1985–1997, chronological development/selection in 1998–2002, then the paper's 2003–2014 evaluation target dates. Earlier observations fit the underlying models. Purge cases whose outcomes have not matured at each boundary, especially h=6. These are our selector-development choices, not a claim that the paper used this split for every method. Validate prompts, state compression, rule thresholds, constant recalibration and gate regularization there. Freeze all settings before the complete Jev comparison. Keep any result-guided revision labeled exploratory and preserve the previous run.

For the monthly extension, use only pre-2003 development cases and the paper's same retrospective test period, checking exact endpoints against code. At h=12, the label is average transformed inflation across months t+1 through t+12, not inflation in month t+12. It matures only when the full window is available. Preserve overlap in uncertainty calculations and resolve the AR(12)-versus-table-note AR(4) denominator discrepancy before comparing normalized scores.

The old 2010–2024 monthly INDPRO pilot uses another target, vintage and model. It is archived rather than treated as validation of this design. Reorienting the project follows the user's selected paper, not a search over results for a favorable table.

Historical macroeconomic outcomes may be in pretrained models' training data. Remove explicit calendar dates and run fully anonymized factor/predictor treatments, but do not claim this proves absence of recall. Date-free numerical states may remain identifiable. A later prospective holdout with a frozen policy provides stronger evidence.

## 8. Outcomes and action labels

Primary outcome: paired forecast RMSE for MRF + Jev against the unchanged MRF on the first locked target/horizon. Report MAE and all forecast paths as supporting measures. Also compare against the best conventional policy selected on development data.

For decision diagnostics, after the target is revealed, identify the candidate with minimum squared error. Break exact ties by preferring (1,1), then the pair closest to (1,1) in squared multiplier distance, then a frozen lexicographic order. Save tied/equivalent candidates; report sensitivity because a label among indistinguishable forecasts is not an economically meaningful distinction.

Compute multiclass Brier and log loss for that realized winner event, plus reliability and skill relative to uniform probabilities. These evaluate action predictions, not a posterior over true coefficients, causal factor relevance or a calibrated target distribution. More accurate winner classification need not yield the best mixture forecast; keep forecast loss primary and include the loss-trained policy control.

Use paired moving-block bootstrap uncertainty intervals for the loss difference, allowing serial dependence and overlapping horizons. Prespecify block choices from development data, not the sign of the test result. With few quarterly origins and a small number of downturns, report the resulting uncertainty rather than treating each factor question as an independent forecast case.

The original two-year forest subsampling blocks and the paper's DM stars are not our paired inference procedure. Distinguish source ratios, reproduced ratios and new paired comparisons. Report performance inside and outside downturn episodes as descriptive diagnostics, without using ex-post recession labels as model inputs or treating a handful of episodes as many independent replications.

A suggested meaningful-effect threshold is 5% lower RMSE than the unchanged MRF, with paired evidence against no improvement. Freeze the threshold and inferential procedure before the complete comparison. Do not claim general superiority from a single target. Later multi-target/horizon tests require multiplicity handling and complete tables.

Efficiency outcomes include live p50/p95 call latency, total workflow time, input/output tokens, attempts, failures and actual billed cost. Separate cached responses from fresh latency measurements and distinguish a forecast-accuracy win from a cost/latency win.

## 9. Ablations and secondary studies

Prespecify on development data: remove semantics; shuffle metadata without changing numbers; reorder choices and factor presentation; remove recent-error evidence; compare argmax with probability mixtures; compare independent factor decisions with the joint menu; and compare reduced and full state-card representations.

E2 uses the six A.2/Table 3 mechanisms: switching coefficients, random walks, an observed-through-noisy-measurements latent driver, slow drift, a break, and constant coefficients with stochastic volatility. Two equation regressors are distinct from the two latent state drivers generating 100 noisy indicators; one state driver is irrelevant. Match the conditioning convention before calling this forecasting replication.

The paper's A.2 prose and Figure 15 caption disagree on OOS lengths. Source replication must resolve that. Our explicitly separate extension uses paths of length 1,000 with 400 initial-fitting, 200 chronological-development and 400 locked-test observations, with 50 fixed seeds for numerical controls. Freeze and record the budgeted hosted subset before running Jev/LLM; both get the identical cases. Score forecast loss and, where identified from known truth, coefficient-path error. Constant coefficients with changing noise test false discoveries. Add zero-coefficient and sign-reversal cases as our own stress tests. The existing synthetic generator is still a legacy smoke test, not this experiment.

E4 fixes three secondary tasks now, before any Jev scores: GDP h=2 quarters (NN is a strong published comparator), unemployment h=6 quarters (TV-FAAR is strong), and monthly CPI h=12 (include ARRF, Tiny ARRF, RF-MAF and Atkeson–Ohanian-style moving averages). Table 5 reports FA-ARRF and Tiny ARRF at 0.67 for monthly CPI h=12, subject to the denominator audit. These public-source motivations are not independent confirmation. Complete the five main-text quarterly targets across all five horizons later; retain the extra HOUST table row as a discrepancy audit until its definition is verified.

Scaling to 4 and 8 equation factors is a new model specification. Tune factor count using only development data, refit the corresponding conventional MRF, and give all selectors the same resulting factors. Do not call this a reproduction of the paper's two-factor FA-ARRF.

After the primary hybrid experiment, a **forest-replacement** study can use Jev to choose among coefficient vectors estimated from past data without access to the current forest's coefficients. That requires its own candidate construction, capacity-matched learned selector and evaluation. It cannot establish the primary hybrid claim or inherit its results automatically.

## 10. Implementation milestones

1. Done for the available engine: document actual behavior/defaults, qualify missing per-table settings, and freeze reconstruction seeds and tolerance. Recovering the original runner remains open.
2. Implemented and tested: dedicated quarterly archive loader, verified metadata/header handling, separate log-difference target and past-only factor/state construction. Exact source preprocessing remains unverified.
3. Adapter and coefficient decomposition implemented; full 48-quarter reconstruction and artifact audit completed. Primary FA-ARRF numerical agreement fails and the first result is preserved. The separately declared ARRF comparator now agrees with its source cell across all three seeds and passes full artifact verification. Exact FA-ARRF replication and the remaining Table 4 comparators stay open; independent tooling retains the qualified-reconstruction label.
4. Shared 25-action algebra implemented and tested, including identity checks on all 144 saved individual-seed forecasts. Joint-action evidence cards and selector routing remain to be built; the legacy three-label hosted adapter is unchanged.
5. Build appendix-inspired controlled DGPs, past-only state cards and a prequential action-loss dataset; implement constant, learned and neural/interaction controls and identity/timing tests.
6. Freeze prompts and run bounded Jev/LLM contract pilots once credentials are available.
7. Run the declared retrospective comparison, then robustness and stronger-vintage/prospective validation.

The new quarterly execution path is distinct from the legacy scaffold. Its tests and full forest result are recorded, but exact numerical reproduction and any Jev benefit remain unestablished. See [current status](../reports/STATUS.md), the executable reconstruction config and the separate [planning manifest](../research/mrf_extension_plan.json).
