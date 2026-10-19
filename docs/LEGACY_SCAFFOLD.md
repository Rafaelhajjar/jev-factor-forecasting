# Jev Factor Forecasting

> Archived initial scaffold. The active direction is the [MRF extension](../README.md), with its [current protocol](RESEARCH_PROTOCOL.md). Commands below still run the original scaffold from the repository root. They do not implement the new MRF study.

Can a general decision model identify which factors are useful **right now**, and turn those judgments into a better time-series forecast?

The idea is to give Jev a target, engineered signals or estimated factors, and evidence about how their relationships have been behaving. For each factor it returns probabilities over a small set of actions. Ordinary code converts those probabilities into a changing linear combination.

This is a research experiment. We want to find out whether the extra decision layer improves forecasting, when it helps, and whether its accuracy justifies its cost. A negative result against a good statistical model is useful.

## Research question and hypothesis

Many related series contain a smaller number of common signals. Their usefulness for a particular target can change. A stable average coefficient can obscure a factor that mattered last year but is misleading today.

**Hypothesis:** a general decision model can combine recent statistical evidence with factor descriptions to choose useful changes to factor contributions, particularly when history is short or relationships change. Soft probability weights may make these changes less brittle than picking one model or applying a hard threshold.

That hypothesis has two separate parts:

1. Dynamic weighting helps on the selected problem.
2. Jev makes better weighting decisions than conventional methods given comparable evidence, or reaches comparable accuracy at a better cost/latency than an LLM.

The first does not establish the second. A Kalman filter, rolling regression, or supervised gate may already solve the problem. Jev cannot add new information to purely numeric diagnostics; any advantage there must come from a useful prior, representation, or decision rule. Descriptions or contemporaneous text could supply additional context, but their value needs a separate experiment.

## What Jev actually does

[TypeSafe's introduction](https://docs.typesafe.ai/introduction) describes Jev as a model that reads a state and answers typed questions. Choice returns probabilities over options; Score evaluates an ordered rubric; Noul returns a yes/no probability. Questions in the same request are evaluated separately against the shared state.

TypeSafe describes its training method as **reinforcement learning for calibrated decisions (RLCD)**. Its [AI primer](https://docs.typesafe.ai/introduction/machine-learning-primer) explains the intended probability objective. Its [launch post](https://typesafe.ai/blog/introducing-system-one-models-and-jev) describes a distinct architecture and parallel sampling. Public material does not give us enough detail to reproduce that architecture, training data, or training objective. We are testing the hosted model's behavior, not claiming to understand its undisclosed internals.

The relevant fit is narrow: several factor decisions, a predefined answer space, and probabilities that code can combine. The main concern is equally relevant: TypeSafe's [1.13 limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13) warn about arithmetic, precise numerical inference, and option-order sensitivity. We therefore compute statistics and candidate forecasts in code and ask Jev to assess their reliability. We do not ask it to calculate correlations or reconstruct continuous regression coefficients from Score outputs.

The default is pinned to `jev-1.13.0`. The [model documentation](https://docs.typesafe.ai/models), checked on October 18, 2026, also lists `jev-1.14.0`; this should be a separate treatment. The API version is logged. No local Jev weights are included.

## Model formulation

There are two related experiments:

- **Observed signals:** engineered features are the factors. This is a regression with coefficients that change through gating.
- **Latent factors:** estimate common factors from a panel, then gate their contribution to a target forecast. The initial implementation uses PCA and factor-augmented regression. It is not yet a full state-space dynamic factor model.

A classical dynamic factor model has a measurement equation and a transition equation, for example:

```text
x_t = Lambda f_t + e_t
f_t = A f_(t-1) + u_t
```

Its loadings need not change over time: the dynamics may be in the latent factors. Our additional question concerns changing factor-to-target relationships.

The current harness fits a base forecast using three target-history features and K factors:

```text
base forecast = intercept + AR contribution + sum_i beta_i * factor_i
```

For factor i, Jev estimates probabilities over three **marginal actions**:

```text
suppress: multiplier 0
weaken:   multiplier 0.5
retain:   multiplier 1

g_i(t) = 0 * p(suppress) + 0.5 * p(weaken) + 1 * p(retain)
forecast = intercept + AR contribution + sum_i g_i(t) * beta_i * factor_i(t)
```

The question is: which candidate forecast will have the smallest squared error when changing only this factor's contribution and leaving the others at their fitted values? Code supplies all three candidates. After the outcome arrives, the winning action is observable, making multiclass Brier score and log loss meaningful. Exact ties prefer retain, then weaken.

This is a restricted shrinkage model: it cannot amplify or reverse a fitted contribution. Probabilities describe choices, not a Bayesian posterior over coefficients or a calibrated forecast distribution. Taking their weighted average is an experimental policy, not a claim that this is the optimal squared-error weight. Simultaneously applying marginal decisions can create interactions; evaluate the resulting forecast separately from each decision's calibration.

[Confidence](https://docs.typesafe.ai/confidence) is derived from Jev's output distribution. It is not an independent correctness probability. We do not multiply weights by confidence.

## Why compare against an LLM?

An LLM could interpret the same evidence and may reason better about complicated situations. Jev's proposed advantage is an efficient decision interface and useful probabilities; forecasting superiority is unproven.

Both get the same frozen state, questions, and candidate actions. The LLM uses TypeSafe's [official System One adapter](https://github.com/typesafe-ai/system-one-adapter-python) with native structured output and probability mode. We disable silent probability normalization and malformed-output correction. [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) also allow LLMs to follow a schema, so formatting alone is not a reason to expect Jev to win.

Report forecast error, gate calibration, latency, token usage, failures, and actual billed cost where available. SDK retries mean the request limit counts logical evaluations, not individual HTTP attempts. Token counts alone are not a bill. Accuracy and efficiency are separate outcomes. A direct LLM forecaster and an LLM that proposes features once are useful later controls, but they are not implemented in this first version.

## Dataset choice

**FRED-MD is the first real-data candidate.** It is a public monthly macroeconomic panel from the St. Louis Fed. [McCracken and Ng](https://doi.org/10.20955/wp.2015.012) designed it for macroeconomic research; the [official dataset page](https://www.stlouisfed.org/research/economists/mccracken/fred-databases) links fixed vintages and research finding useful predictive content in its factors.

There is a reason to try factors here: [Stock and Watson (2002)](https://www.princeton.edu/~mwatson/papers/Stock_Watson_JBES_2002.pdf) found factor-based forecasts outperforming several smaller conventional models on a historical US macroeconomic panel. That was a different panel, period, and evaluation. It motivates this choice; it does not promise that our setup, target, or Jev will win. We will not search datasets until we find a flattering result.

The first real-data configuration predicts transformed industrial production (`INDPRO`) one month ahead using a pinned September 2026 vintage, with evaluation origins in 2010–2024. Predictors and known target history are lagged by one month. Transform codes come from the file. For INDPRO, the target is `log(IP[t+h]) - log(IP[t+h-1])`, **not** cumulative h-month growth. This is a development specification, not a replication of the Stock–Watson horizon design.

**Important limitation:** a fixed vintage contains historical revisions that were unavailable at earlier forecast dates. A uniform lag does not reconstruct release calendars. Results are a revised-data retrospective experiment, not a real-time forecasting claim. Genuine historical-vintage evaluation is a required later stage.

**Synthetic changing-loadings data** is the mechanism test: we know which factors generate the target, give methods noisy observations, and withhold true regimes and coefficients. It checks whether the harness can expose changing relationships before we interpret macroeconomic results. Its designed factor structure makes it useful for debugging, not evidence of real-world generalization.

## What runs today

| Method | Purpose |
| --- | --- |
| Zero and persistence | Simple sanity checks on the transformed target |
| AR ridge | Target-history-only benchmark |
| Multivariate ridge | All eligible numeric predictors |
| Expanding factor regression | Factor compression without a gate |
| Rolling factor regression | Adaptation through a shorter estimation window |
| Exponentially weighted factor regression | Smoothly discount old observations |
| Random-walk coefficient Kalman filter | A conventional dynamic regression |
| Gradient-boosted trees | Nonlinear supervised baseline |
| Rule gate | Can a transparent diagnostic rule explain the gains? |
| Online multinomial logistic gate | Learns the same discrete action outcome from matured past cases |
| Jev / LLM gates | Same questions and information; opt-in hosted calls |

Hyperparameters are development defaults, not tuned winners. The first run is a working baseline, not a completed benchmark. The original roadmap is in the [archived protocol](LEGACY_PROTOCOL.md).

## Run it

Use Python 3.11 and [uv](https://docs.astral.sh/uv/). The lockfile pins resolved dependencies.

```bash
uv sync --frozen
uv run pytest
uv run jev-factor run --config configs/synthetic.json --output runs/synthetic-01

uv run jev-factor download-fred
uv run jev-factor run --config configs/fred_md.json --output runs/fred-01
```

Each run creates configuration, provenance, per-origin forecasts, per-seed metrics, and the exact states used for decisions. It refuses to overwrite a run. Downloaded data and API records are ignored by Git; no dataset is relicensed under the code license.

Hosted comparisons need credentials and the optional SDKs. Never put keys in Git. No keys were available during setup, so **no Jev or LLM forecasting results are claimed**.

```bash
uv sync --frozen --extra api
# Set TYPESAFE_API_KEY in your shell first.
uv run jev-factor run --config configs/synthetic.json --output runs/jev-pilot \
  --seeds 7 --max-origins 2 --methods factor_static gate_jev --max-api-calls 2

# Set the chosen provider's credential; choose an explicit model snapshot.
uv run jev-factor run --config configs/synthetic.json --output runs/llm-pilot \
  --seeds 7 --max-origins 2 --methods factor_static gate_llm --max-api-calls 2 \
  --llm-provider openai --llm-model YOUR_PINNED_MODEL_ID
```

The LLM adapter also supports `anthropic` and `gemini`. `--reverse-options` tests option-order sensitivity; `--anonymize` removes factor descriptions. Model requests fail visibly rather than becoming fabricated forecasts. Successful remote records include resolved models, usage and elapsed time; local tests verify the integration contract without spending API credits.

## What we want to conclude

We want evidence that a decision model adds predictive value **beyond existing adaptation methods**, or is a cheaper/faster substitute for an LLM doing the same job. We also want to identify the information it uses: numerical diagnostics, semantic descriptions, or a useful combination.

If the statistical gate matches Jev, we should prefer the simpler method for that setting. If Jev only helps with meaningful contextual inputs, that narrows the application. If it fails when relationships reverse, that exposes the limits of the shrinkage formulation. All are valid conclusions.

See [original protocol](LEGACY_PROTOCOL.md), [original source notes](LEGACY_SOURCES.md), and [initial run status](../reports/STATUS.md). Code: MIT. Jev is TypeSafe's product; this project is independent and is not endorsed by TypeSafe or the Federal Reserve.

The initial conventional runs are complete: adaptive coefficients help on the synthetic case, while zero growth is best in the first FRED-MD configuration. The latter is an unresolved dataset/specification issue, not evidence supporting the Jev hypothesis. Full scores and limitations are in the status report.
