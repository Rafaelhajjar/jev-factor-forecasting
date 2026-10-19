# Research protocol

> Archived initial protocol, superseded by the [MRF extension protocol](RESEARCH_PROTOCOL.md) on October 18, 2026. Original experiment results remain recorded; they are not MRF replication results.

## Scope

Test whether a general decision model improves factor forecasting through conditional shrinkage of estimated factor contributions. Distinguish observed engineered signals from latent factors. The implemented PCA pipeline is a factor-augmented regression; a full dynamic factor model also models factor transitions and observation noise.

This protocol is an initial research plan, not a timestamped external preregistration. Current results are development results. Freeze the final configuration, prompt hash, model versions, dataset hashes, and selected baselines in Git before evaluating any new confirmatory holdout.

## Hypotheses

- H1: a changing contribution policy beats the expanding factor regression under coefficient instability.
- H2: Jev beats a conventional supervised gate trained on the same numeric evidence and marginal-action labels.
- H3: Jev has a better forecast-error/cost/latency tradeoff than an LLM using the same structured task.
- H4: semantic descriptions add value beyond the numeric evidence.
- H5: action probabilities are informative and calibrated on the explicitly defined action outcome.

H1 does not establish H2. H3 may hold through efficiency without higher accuracy. H4 requires an ablation and cannot be inferred from economic-sounding explanations. Calibration of marginal action predictions does not establish calibration of a joint target distribution.

## Mechanism and failure conditions

Dynamic weights could reduce errors when a relationship weakens and the evidence reveals it before the base estimator fully adapts. Jev's general prior could help combine weak evidence across unfamiliar contexts. The supervised gate instead estimates that mapping directly from past forecast cases.

The premise fails if numeric relationships are the whole problem and a trained statistical gate captures them as well; if descriptions introduce persuasive but false narratives; if probabilities are miscalibrated under distribution shift; or if marginal gating ignores redundant/correlated contributions. Suppression cannot repair a coefficient with the wrong sign and cannot increase an underestimated coefficient. Regime changes may be fundamentally unpredictable from the available information.

## Dataset stages

1. **Synthetic mechanism tests.** Initial switching-loadings generator, fixed seed set [7, 42, 123]. Add stable-loadings, gradually drifting, abrupt sign-flip, redundant-factor, no-signal, and false-metadata variants before a confirmatory experiment. No true regime or beta appears in model states. The initial generator includes anonymous signals and noisy panel measurements. It does not yet include a privileged oracle benchmark.
2. **FRED-MD development.** Pinned 2026-09 CSV with SHA-256 verification. Initial target INDPRO, horizon 1, origins every 3 months in 2010–2024. The target is the file's transformed series at t+h. All model methods receive the same availability lag. Include every chosen origin, including pandemic disruption. Report 2020–2021 separately only as a declared descriptive slice, alongside the full sample.
3. **Historical-vintage evaluation.** Use archived vintages, exact series release dates where possible, ragged-edge handling and a declared target vintage for scoring. This is required before describing a result as real-time. No current-vintage preprocessing can substitute for this.
4. **External replication.** Prespecify additional targets PAYEMS and CPIAUCSL and horizons 1, 3, 6, 12. CPI's default code 6 predicts inflation change, not inflation level; use and label a separate target transform if evaluating inflation itself. Use another domain only after fixing the first-domain method. Do not select another dataset because Jev lost.

Historical public data may appear in language-model training. Omitting dates and target names from the decision state reduces direct recall opportunities but does not prove independence. Anonymize factor descriptions, shuffle descriptions on the same numeric state, and ultimately collect a prospective holdout after the protocol freeze. Report the possibility of training contamination for all pretrained models.

## Information timing

At forecast origin t with horizon h and availability lag L:

```text
predictors at t use source values through t-L
training pair with origin s is eligible only when s+h <= t-L
preprocessing is fit on those eligible training feature rows
target history in predictors is also delayed by L
```

Missing predictor values are imputed using training medians. Series eligibility and scaling are determined from training rows. No backward fill, full-sample PCA, future-based feature screening or hidden future-label tuning. PCA is refit at every origin. A deterministic sign convention applies inside each origin; components may still rotate or exchange order. Interpret them using current loadings rather than claiming PC1 is always the same economic factor. Near-degenerate components can make individual gates unstable; compare subspace- or group-level gates later.

All state-building and forecasts happen before the evaluator reads that origin's future target. Online supervised-gate examples have a label-availability position and are filtered by t-L. The current gate starts from a uniform distribution until enough past evaluation-origin outcomes mature; report this cold start. A later version should pretrain it on a dedicated development period, then compare both warm and cold start policies.

## Marginal decision target

For each factor, form three candidate forecasts from the ungated full-model forecast: remove its contribution, halve it, retain it. The realized action label is the candidate with minimum squared error. Ties prefer retain, then weaken, then suppress. This is an observable decision outcome, not a causal effect or true latent relevance label.

Class probabilities should correspond to this event, not an undefined idea of influence. Each factor's question holds the other factors fixed at full-model values. The final policy applies all expected multipliers simultaneously, so decision labels and final forecast performance can disagree. Keep both metrics. Do not reconstruct a joint coefficient posterior by treating independently returned probabilities as independent random factors.

## Comparisons

Implemented controls: zero, persistence, AR ridge, full multivariate ridge, expanding factor ridge, rolling factor ridge, exponentially weighted factor ridge, random-walk coefficient Kalman regression, gradient-boosted trees, rule gate, and online multinomial logistic gate. They share target-history information and the forecast schedule. The rule gate's hand-assigned probabilities are heuristic weights, not advertised calibrated probabilities.

Required before a strong research claim:

- A full state-space DFM with estimated factor transitions and observation noise.
- Dynamic model averaging or a comparably strong probabilistic adaptive regression.
- Chronological validation for factor count, regularization, window length, forgetting rate, Kalman Q/R and tree settings; use the same search budget across comparable methods.
- Equal-weight forecast combination and learned stacking of individual factor experts. These are combinations of forecasts, which is a different architecture from multiplying raw factors.
- Same-state LLM gate in probability mode; record provider, exact snapshot, reasoning configuration, retries, usage, latency and cost. Add direct LLM forecasting as a separate experiment, not a replacement for the matched gate comparison.
- One time-series foundation-model baseline with its native numeric input format and disclosed training overlap when practical.

Current defaults use 4 factors, ridge alpha 10, 3 AR features, rolling windows 180/240, recent diagnostics 48/60, EWLS forgetting 0.98 and fixed Kalman Q/R rules. These are untuned starting values. `factor_static` means expanding-window fitted coefficients that are constant within each forecast, not frozen coefficients across the whole backtest. `factor_rls` is implemented by weighted batch ridge in each current factor basis, avoiding invalid recursive updates across changing PCA coordinates.

## Ablations

Implemented switches: remove factor descriptions (`--anonymize`) and reverse Choice order (`--reverse-options`). A fresh run directory keeps their cached responses separate. These are not interchangeable with a fully anonymized target/predictor identity treatment because factor IDs remain in the state.

Planned: metadata only, numeric diagnostics only, randomized metadata, permutation of factor order, stable factor basis versus refitting, recent diagnostics removed, hard argmax versus soft weighting, Jev versus a learned small gate, and delayed/missing contextual cues. Give all methods any added numeric/context features or explicitly declare the information advantage.

## Metrics and decision rules

Current outputs: RMSE, MAE, per-origin paired squared/absolute errors, per-seed metrics, model-only time, multiclass Brier and log loss for the marginal-action event, raw states and hashes, and API response records. Model-only time excludes shared preprocessing. Cached elapsed time is not a fresh network latency observation.

For the confirmatory stage add MASE or target-specific relative RMSE; reliability diagrams; p50/p95 live end-to-end latency; billed cost; request failure/retry rates; and interval coverage if target intervals are actually modeled. Do not infer forecast intervals from gate entropy.

Use paired moving-block bootstrap intervals for loss differences (and a Diebold–Mariano test with appropriate serial-correlation correction if reported). Account for dependence between nearby origins, overlap at h>1, correlated factors and repeated targets. Synthetic seeds are independent replicates; macro factor questions at one date are not independent forecast cases. Correct or explicitly label multiple comparisons and exploratory slices.

Select the strongest conventional comparator using only the development period. A suggested confirmatory threshold is at least 5% lower RMSE than that frozen comparator with a paired uncertainty interval excluding no improvement; freeze the criterion before collecting the new holdout. Report a loss even if only LLM efficiency improves. Do not call the project successful because it beats AR but loses to adaptive factor regression.

## Immediate next steps

1. Review the initial local results and diagnose the strongest conventional baseline.
2. Supply TypeSafe access and a chosen LLM provider/snapshot; run two-origin contract pilots.
3. Choose a fixed development period, tune fairly, and freeze questions before full hosted runs.
4. Add historical-vintage evaluation, state-space DFM and dynamic model averaging.
5. Freeze a prospective test, then report all outcomes and ablations.
