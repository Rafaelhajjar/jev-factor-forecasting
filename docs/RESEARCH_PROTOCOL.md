# Research protocol: extending Macroeconomic Random Forests with Jev

Updated October 18, 2026. This supersedes the [initial generic factor-gating protocol](LEGACY_PROTOCOL.md). It is a research plan, not an implemented MRF benchmark or an external preregistration.

## 1. Research claim

Test whether Jev can improve a replicated Macroeconomic Random Forest (MRF) by selecting bounded adjustments to its factor contributions from observed economic evidence.

The primary intervention is **MRF + Jev**. The original MRF already adapts its coefficients, so Jev must show value beyond that adaptation. A forest-replacement experiment is secondary and must not be pooled with the hybrid experiment.

We are extending [Goulet Coulombe (2024)](https://doi.org/10.1002/jae.3030), not claiming that dynamic coefficients or probabilistic forecast combination are new. No finding about the benefit of Jev has been established.

## 2. Replication before extension

Use the [replication checklist](MRF_REPLICATION.md) as the first implementation milestone. The published paper is the citation target; the accessible arXiv manuscript is an earlier version. Do not silently mix their results, sample definitions or model variants.

The archived data are available and hashed. The exact published forecasting pipeline, transformations, factor-eligibility rules, tuning procedure and reported comparison cells still need reconciliation. The author's R package provides an MRF implementation, not by itself the complete reproduction pipeline. A Python implementation is an independent portability check after the R reference is verified.

Working-paper anchors, pending that reconciliation: quarterly FRED-QD; a factor-augmented autoregression with two target lags and one lag of each of two factors; direct horizons 1, 2, 4, 6 and 8 quarters; evaluation in 2003Q1–2014Q4. Factors are interpreted through activity and leading-indicator loadings. These details are provisional until the published-version record is locked. [Accessible manuscript, Section 4](https://arxiv.org/pdf/2006.12724).

The first project target is unemployment at horizon 1 quarter. Match its exact transformation and timing; do not assume forecasting the unemployment level and forecasting its change are equivalent. Reproduce the relevant AR, linear factor model and factor-augmented MRF cells first. Expand only after the source of discrepancies is understood. If reproduction fails, report that limitation rather than attributing differences to Jev.

The original retrospective sample is a replication/development benchmark. Its outcomes are public and it cannot be described as a new blind test for a pretrained model.

## 3. Scientific motivation

The statistical model may estimate useful relationships while still making state-dependent errors about their current magnitude. Jev could bring a transferable prior for interpreting compact economic evidence, especially when several weak signs need to be considered together. A soft combination of candidate adjustments could be more stable than choosing one action with certainty.

This is plausible, not guaranteed. Jev receives no new outcome information from a verbal description of the same numbers. A learned statistical gate may use the evidence better. The forest may already capture the relevant interactions; a second layer may add noise or double-count a regime signal. The joint task may be too numerical or too uncertain for Jev's useful capabilities. All of those are valid failure explanations to test.

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

The original MRF continues to use its full specified S(t). A bounded state card is a compressed view of that information. Do not describe the original forest and Jev as receiving identical representations. Jev, the LLM and a newly trained numeric gate must share the same candidate set and numerical card fields; document semantic fields separately. Add a compression-matched forest/gate control to test whether a gain or loss comes from representation.

Factor identities can rotate or swap when PCA is refit. Preserve the original preprocessing for replication, and share its exact resulting basis with every extension method. Sign/reordering adjustments in presentation must transform coefficients consistently and leave forecasts unchanged. Do not use full-sample information to give a factor a permanent economic name. Diagnose unstable subspaces; freezing or aligning a basis beyond the author's procedure is an explicit ablation.

## 6. Comparisons

| Method | What it isolates |
| --- | --- |
| Paper's AR and linear factor benchmarks | The value of factors and conventional adaptation |
| Replicated factor-augmented MRF | The main reference being extended |
| MRF + uniform action probabilities | An exact identity check against the original forecast |
| MRF + diagnostic rule | Whether a transparent mechanical adjustment is sufficient |
| MRF + learned multinomial gate | Whether ordinary supervised learning can choose the same 25 actions |
| MRF + learned loss-based gate | Whether forecasting-loss optimization outperforms winner classification |
| MRF + Jev | The primary proposed extension |
| MRF + LLM | The same structured decision task using a generative model |

Tune learned policies and conventional methods only on chronological development folds with comparable search budgets. Train the learned gates on historical candidate forecasts constructed by past-only model fits, not in-sample residuals from a model fit to the whole development period. Give gates a development warm-up rather than repeating the old scaffold's cold-start comparison.

The LLM uses the common typed-task adapter with the same frozen state, questions and choices. Pin provider/model/configuration; retain malformed responses, refusals, retries and token usage. Native structured output is permitted. Output validity alone is not a Jev advantage. Record actual latency and billed cost rather than importing vendor speed claims.

## 7. Timing and sample separation

First preserve the paper's exact retrospective timing for a faithful replication. Label fixed-vintage evaluation accurately. Separately build a historical-vintage evaluation that respects actual release timing; a uniform lag cannot recreate that information set.

For the extension, at origin t a training case with origin s is eligible only after its target at s+h is available under the declared release policy. This applies to factor estimation, coefficient fitting, candidate-loss labels, policy fitting, feature selection and calibration. Purge development splits where training labels overlap the validation boundary.

Choose development folds entirely before the locked retrospective evaluation start. Validate prompts, state compression, rule thresholds and gate regularization there. Freeze all settings before the complete Jev comparison. Keep any result-guided revision labeled exploratory and preserve the previous run.

The old 2010–2024 monthly INDPRO pilot uses another target, vintage and model. It is archived rather than treated as validation of this design. Reorienting the project follows the user's selected paper, not a search over results for a favorable table.

Historical macroeconomic outcomes may be in pretrained models' training data. Remove explicit calendar dates and run fully anonymized factor/predictor treatments, but do not claim this proves absence of recall. Date-free numerical states may remain identifiable. A later prospective holdout with a frozen policy provides stronger evidence.

## 8. Outcomes and action labels

Primary outcome: paired forecast RMSE for MRF + Jev against the unchanged MRF on the first locked target/horizon. Report MAE and all forecast paths as supporting measures. Also compare against the best conventional policy selected on development data.

For decision diagnostics, after the target is revealed, identify the candidate with minimum squared error. Break exact ties by preferring (1,1), then the pair closest to (1,1) in squared multiplier distance, then a frozen lexicographic order. Save tied/equivalent candidates; report sensitivity because a label among indistinguishable forecasts is not an economically meaningful distinction.

Compute multiclass Brier and log loss for that realized winner event, plus reliability and skill relative to uniform probabilities. These evaluate action predictions, not a posterior over true coefficients, causal factor relevance or a calibrated target distribution. More accurate winner classification need not yield the best mixture forecast; keep forecast loss primary and include the loss-trained policy control.

Use paired moving-block bootstrap uncertainty intervals for the loss difference, allowing serial dependence and overlapping horizons. Prespecify block choices from development data, not the sign of the test result. With few quarterly origins and a small number of downturns, report the resulting uncertainty rather than treating each factor question as an independent forecast case.

A suggested meaningful-effect threshold is 5% lower RMSE than the unchanged MRF, with paired evidence against no improvement. Freeze the threshold and inferential procedure before the complete comparison. Do not claim general superiority from a single target. Later multi-target/horizon tests require multiplicity handling and complete tables.

Efficiency outcomes include live p50/p95 call latency, total workflow time, input/output tokens, attempts, failures and actual billed cost. Separate cached responses from fresh latency measurements and distinguish a forecast-accuracy win from a cost/latency win.

## 9. Ablations and secondary studies

Prespecify on development data: remove semantics; shuffle metadata without changing numbers; reorder choices and factor presentation; remove recent-error evidence; compare argmax with probability mixtures; compare independent factor decisions with the joint menu; and compare reduced and full state-card representations.

Use synthetic controls inspired by the paper's state-dependent-coefficient mechanism: stable coefficients, predictable switching, unpredictable changes, zero coefficients and sign reversal. Record what the multiplier restriction cannot represent. The existing synthetic generator remains a legacy smoke test until these controls are implemented.

After the primary hybrid experiment, a **forest-replacement** study can use Jev to choose among coefficient vectors estimated from past data without access to the current forest's coefficients. That requires its own candidate construction, capacity-matched learned selector and evaluation. It cannot establish the primary hybrid claim or inherit its results automatically.

## 10. Implementation milestones

1. Reconcile and lock the replication specification and reference code commits.
2. Add a dedicated quarterly archive loader, factor eligibility handling and exact target definitions.
3. Implement the reference MRF adapter and factor/intercept/AR decomposition; reproduce selected paper cells.
4. Generalize the current hard-coded three-label gate interface to joint candidate records without breaking legacy runs.
5. Build past-only state cards and a prequential action-loss dataset; implement learned controls and identity/timing tests.
6. Freeze prompts and run bounded Jev/LLM contract pilots once credentials are available.
7. Run the declared retrospective comparison, then robustness and stronger-vintage/prospective validation.

The current turn refactors the plan only. No item is represented as completed merely because a corresponding legacy helper exists. See [current project status](../reports/STATUS.md) and the [planning manifest](../research/mrf_extension_plan.json).
