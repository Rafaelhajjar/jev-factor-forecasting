# Jev + Macroeconomic Random Forests

Can Jev improve a Macroeconomic Random Forest's forecast by identifying when its factor contributions should be stronger or weaker?

This project now extends **Philippe Goulet Coulombe's [The Macroeconomy as a Random Forest](https://doi.org/10.1002/jae.3030), Journal of Applied Econometrics, 2024**. The first task is replication. The main experiment then adds Jev to the replicated model and tests whether it improves forecasts beyond the forest itself.

**Status:** the research plan has been refactored. The executable code still runs the original experimental scaffold. MRF replication and the new Jev extension are not implemented or evaluated yet. Existing results are preserved as preliminary work, not evidence for the new study.

## The idea we are building on

A Macroeconomic Random Forest (MRF) keeps a linear forecasting equation and learns how its coefficients change with the economic state:

```text
forecast = X(t)' beta(t)
beta(t)  = forest(S(t))
```

`X(t)` contains the terms whose contributions we want to interpret. `S(t)` contains the information used to determine their coefficients. These are different roles: a variable can help identify a regime without being an explicit term in the small forecasting equation.

Our starting point is the paper's factor-augmented model. The working-paper specification uses target-history terms and two common factors associated with real activity and leading indicators. Exact published-version details must be reconciled before replication is declared complete. [Working paper](https://arxiv.org/pdf/2006.12724), [implementation documentation](https://mrf-web.readthedocs.io/en/latest/).

## The main extension: MRF + Jev

We keep the replicated forest, its estimated factors, and its forecast as the reference. Jev receives a compact account of the current state, the two estimated factor contributions, their recent predictive evidence, and candidate adjustments calculated by code.

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

This is an extension of the forest's forecast. It can strengthen as well as suppress a factor, addressing a limitation of our earlier shrinkage-only idea. A joint menu accounts for both adjustments in one decision rather than assuming independent answers form a coherent joint choice.

The unmodified forest is inside the menu at `(1,1)`. A uniform distribution over the symmetric grid also recovers its forecast. The initial policy preserves the forest's coefficient signs and cannot restore an effect whose estimated coefficient is zero. Signed or additive adjustments are a later, separately evaluated extension.

Jev selects among precomputed alternatives. It does not estimate PCA factors, calculate correlations, or generate exact coefficients. Its output is a decision distribution, not a posterior over true economic effects. The 25-way task may still exceed its useful numerical judgment; that is a hypothesis to test.

## What we want to learn

1. Does the replicated MRF improve on the paper's linear benchmark in our implementation?
2. Does adding Jev improve on that same MRF?
3. Does Jev beat a small learned gate choosing from the same 25 alternatives?
4. Does economic meaning help, beyond anonymous numerical summaries?
5. Does Jev offer a useful accuracy/cost/latency tradeoff against an LLM given the same task?

The decisive comparison is **MRF + Jev versus original MRF**. Beating a fixed regression alone would not establish our contribution. Any later attempt to replace the forest is a separate experiment with a different claim.

## Data and first target

We located and inspected the journal's [replication-data archive](https://doi.org/10.15456/jae.2023321.0115060814). It contains `FREDQD_2019-03.csv` and `FREDMD_2018-01.csv` in levels. The archive contains data, not a complete reproduction script. Its files and hashes are recorded in the [replication checklist](docs/MRF_REPLICATION.md).

The planned first target is **quarterly unemployment, one quarter ahead**, with the target definition and timing taken from the version-checked paper setup. This choice is fixed now; it is not selected using our future Jev results. GDP and other targets/horizons follow only after the first pipeline is reproduced and frozen.

A fixed archived vintage permits retrospective replication. It does not establish that every observation was available at the historical forecast date. Historical-vintage evaluation and a prospective test remain separate stages.

## Comparisons and execution order

| Stage | Work | Completion requirement |
| --- | --- | --- |
| 1 | Reconcile paper versions, archive and author code | Lock exact data, transformations, factor construction, target and evaluation schedule |
| 2 | Reproduce linear and MRF forecasts | Explain numerical differences before adding Jev |
| 3 | Implement the common 25-candidate task | Validate timing, uniform recovery, shared evidence and prequential gate training |
| 4 | Compare original MRF, learned gate, Jev and LLM | Freeze prompts and settings before the complete retrospective comparison |
| 5 | Extend targets and collect stronger validation | Report robustness, availability and training-contamination limits |

The [research protocol](docs/RESEARCH_PROTOCOL.md) specifies the interventions, controls, evaluation and implementation tasks. A [machine-readable planning manifest](research/mrf_extension_plan.json) records the design; it is not an executable experiment configuration.

## What runs today

The existing Python code, `configs/synthetic.json`, and `configs/fred_md.json` remain the original smoke-test and baseline harness. Their three-action gate, monthly target, and four-factor setup do not implement the new study. See the [archived scaffold guide](docs/LEGACY_SCAFFOLD.md) and [initial results](reports/STATUS.md).

```bash
uv sync --frozen --extra api
uv run --frozen --extra api pytest

# Original scaffold only:
uv run jev-factor run --config configs/synthetic.json --output runs/legacy-smoke \
  --seeds 7 --max-origins 3
```

The earlier code passed 32 tests and GitHub CI. No Jev or LLM forecasting calls have been made. Model credentials are needed when the new integration reaches its API pilot; they are not needed for replication work.

Our code is MIT licensed. Author implementations and data retain their own licenses and attribution requirements. This independent project is not endorsed by Goulet Coulombe, TypeSafe or the Federal Reserve. [Sources and evidence boundaries](docs/SOURCES.md).
