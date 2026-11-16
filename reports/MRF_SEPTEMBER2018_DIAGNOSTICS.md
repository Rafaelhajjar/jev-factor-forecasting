# Inside the September 2018 MRF

[Open the 31-figure report](mrf-september2018-diagnostics/index.html).
The local `standalone.html` contains the images in one file; the local
`mrf-diagnostics.zip` contains the report, PNG/SVG figures and diagnostic data.

## What happened?

The model learned changing coefficients, but those changes did not reproduce
the paper's improvement. All 18 fits finished and passed the complete artifact
audit: six refits, three seeds, 100 trees each, and 48 target quarters.

| Model | RMSE / AR(4) |
| --- | ---: |
| Fixed FA-AR | 0.833344 |
| MRF, seed 101 | 0.852479 |
| MRF, seed 202 | 0.828921 |
| MRF, seed 303 | 0.823770 |
| Same-equation static OLS, exploratory | 0.818514 |
| Paper MRF, reference only | 0.72 |

The joint source-cell criterion still fails. The static OLS diagnostic is new
and post-hoc: it uses the MRF's intercept, two target lags and two lagged
factors. It is not the source's larger fixed FA-AR equation, and it does not
replace a declared benchmark.

Every MRF seed has lower mean absolute error than fixed FA-AR and the static
control. That is useful, but does not recover the primary RMSE result: large
misses are penalized more heavily when errors are squared.

The forest helps before 2008. Its large relative miss in 2009Q1 and weaker
results afterward offset that benefit. All seeds underpredict the sudden rise
in unemployment at that quarter. These plots locate the failure; they do not
prove overfitting, identify a causal mechanism, or establish why the original
paper differs.

## What is plotted?

1. How training works, the local objective, expanding calendar, state size,
   factor-preparation convergence counts and outlier counts.
2. Scores versus the paper, actual/forecast changes, the crisis close-up,
   one-step unemployment levels, rolling RMSE, calendar subperiods and scatterplots.
3. Residuals, quarter-by-quarter losses, cumulative excess loss, costly
   quarters, error-versus-forecast plots, error distributions and autocorrelation.
4. All five coefficient paths, forecast contributions, dynamic-versus-static
   adjustments and training PCA loadings.
5. Seed stability and performance across the six refit blocks.
6. A separately instrumented first-window replay: training/test MSE versus
   trees averaged, per-target prefix forecasts, individual-tree distributions,
   leaf depth/support, and actual split-variable usage.

Each figure has a caption stating the scope, units and important limitations.
The report includes machine-readable predictions, coefficients, contributions,
training curves, per-tree predictions, leaf paths, split counts and checksums.

## What the training curve means

This is a random forest with local regularized linear equations, not a neural
network trained over epochs. A useful curve is the MSE after averaging trees
1 through B, for B = 1,...,100. It need not decrease monotonically.

The original adapter did not save per-tree training logs. The diagnostic replay
uses the first refit (through 2002Q4), seed 101, and the unchanged 100-tree
settings. It changes only `keep.forest=TRUE` and post-fit exports. Every final
forecast **and coefficient** must agree with the original saved output within
1e-12 before replay plots can be generated. No original adapter, engine,
prediction, setting, or failed agreement flag is overwritten.

Training MSE is in-sample. The next eight quarters are an already-observed
test block, not a fresh validation sample. The curves are descriptive and are
not used to choose tree count. Differences in sample difficulty also matter.

The author's `pred.given.tree` fits leaf equations using all training rows in
the leaf, not just rows selected to construct splits. Rows omitted from split
selection therefore do not give a strictly held-out target prediction. The
report does **not** relabel those native arrays as clean OOB validation.

In the terminal fit, neighboring y and X rows are multiplied by RWR or RWR².
Thus their squared-error weights are RWR² and RWR⁴, not RWR and RWR².
With the OLS prior, the standardized leaf penalty is
`0.1 * (beta-beta_OLS)' diag(0.01,1,1,1,1) (beta-beta_OLS)`.
The fast split search omits neighbor augmentation and applies the source's
split-rank weighting to the candidate residual SSE. There is no single global
epoch loss minimized by the entire ensemble.

## Reading limits

- The archive has 247 indicators versus the original 248; the complete author
  caller is unavailable. This is a qualified, fixed-vintage retrospective
  reconstruction, not an exact or real-time replication.
- The target is delta log UNRATE. Charts multiply this by 100 into log points;
  those are not percentage-point changes in the unemployment rate.
- Level plots are observed previous-quarter UNRATE times exp(predicted log
  change), not a recursive forecast path. Main scores remain in log changes.
- PCA bases are refitted; signs/rotations and individual factor coefficients
  are not invariant across refits. Contributions are accounting, not causality.
- Three-seed spread and 100-tree dispersion are not calibrated predictive
  uncertainty. Shared model error can remain large when spread is small.
- Split frequency is not permutation importance. Large/correlated feature
  groups have different opportunities to be selected.
- Subperiods, expensive-quarter rankings, and the static control are post-hoc.
  Nothing is retuned or selected on these 48 test outcomes.

## Reproduce locally

Install the plotting extra with `uv sync --frozen --extra plots` (add `--extra
api --extra nn` to retain those optional environments). With the complete
frozen run and its checksum-pinned external engine/data available:

```sh
uv run --frozen --extra plots python -m jev_factor.diagnostics2018 replay \
  --run runs/mrf-september2018-v1 \
  --trace runs/mrf-september2018-trace-v1 \
  --r-library /absolute/path/to/task-local/r-library

uv run --frozen --extra plots python -m jev_factor.diagnostics2018 report \
  --run runs/mrf-september2018-v1 \
  --trace runs/mrf-september2018-trace-v1 \
  --output reports/mrf-september2018-diagnostics
```

The shareable report can be opened without the raw archive, R, a running
server, hosted models, or an internet connection. Rebuilding the experiment
still requires the original declared inputs; its manifest contains local paths.
The large replay RDS stays local under ignored `runs/`. The separately sourced
GPL author engine is not vendored or relicensed.

[Original completed result](mrf-september2018-diagnostics/result.md),
[original full audit](mrf-september2018-diagnostics/audit.json),
[diagnostic provenance](mrf-september2018-diagnostics/diagnostics.json),
[frozen protocol](../docs/SEPTEMBER2018_MRF.md).

No Jev/LLM forecast evaluation has run, and no new external messages are sent.
