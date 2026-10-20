# Qualified September 2018 MRF reconstruction

Declared October 20, 2026, before new-vintage MRF outcomes. The user explicitly
authorized advancing as a **qualified reconstruction**, despite the plain-RF
diagnostic miss and the missing original series. This does not retroactively
turn the RF criterion into a pass. The earlier March 2019 runs remain unchanged.

## Problem, inputs, target

Fit the paper's factor-augmented autoregressive random forest (FA-ARRF) to
delta-log quarterly unemployment at h=1, and compare it to its own fixed FA-AR
and direct AR(4). Keep the same September 2018 archive, preprocessing and
origin/target calendar as the [completed raw RF](../reports/RF_SEPTEMBER2018.md).
The original 248-series snapshot/caller has not been recovered; the served
archive has 247 series. This is not an exact-replication claim.

The small equation has an intercept, two target-history terms and one value of
each of the first two cross-sectional PCA factors: five varying coefficients.
The state has eight target-history observations, eight observations of each
of five cross-sectional factors, two observations of each raw indicator, two
moving-average factors for each indicator, and a trend. With 247 active series
it has **1,037 state columns**, not the old 1,041. The raw-RF comparison used
1,976 columns and is a distinct model, not a subset of the reported MRF results.

At origin o, the label is y[o+1]. Its eight observations are o through o-7.
First training target is 1961Q3 (origin 1961Q2). Forecast target dates are
2003Q1-2014Q4, with six expanding refits through 2002Q4,...,2012Q4. Fits use
only labels observed by their cutoff. New lagged observations enter between
refits without refitting the coefficient map.

## What stays fixed, and what is assumed?

Reuse the actual checksum-pinned external author R engine and original
training-only adapter. Keep the earlier MRF declaration's **100 trees**, seeds
101/202/303, block parameter 8, 75% native block subsampling, RWR 0.75, ridge
0.1, MLF 1, candidate-feature fraction 1/3, nominal parent size 10 and trend
push 1. Its native equation-dimension floor can raise the parent size. **Do not
apply plain ranger's 500-tree/min.node.size=3 settings to MRF.** They were not
provided as MRF settings. These inherited MRF values are explicit reconstruction
choices, not recovered per-table invocations.

Completion/outlier/PCA preparation uses all 247 series, fixed rank five and
10-IQR thresholds fitted through the last **training origin**, exactly as RF.
Every standardized raw lag must match the frozen RF matrix. Cross-sectional
factors use that training PCA; two per-series MAFs are fitted on the eight-lag
vectors of all aligned training rows. Their projections and signs are frozen
for later observations. PCA orientation is sklearn's convention, not a claim
about the missing original factor basis.

Keep OLS prior means, prior variances 100 for the intercept and 1 for slopes,
and the adapter's training-only moments/inner-standardization override. All
future target cells are masked before the R engine is called. The earlier
native-all-row, R-sign and PCA125 sensitivities are not stacked into this run.
Original preprocessing and runtime remain unknown.

## Comparators and interpretation

Fit AR(4) with an intercept on the same dates and labels, and verify it agrees
with the frozen RF run's AR(4). The matching fixed FA-AR has four target lags
and two observations of each of the first two factors. Compare MRF against
this **same-vintage, same-basis** fixed comparator; do not borrow an earlier
linear score to manufacture a larger gain.

Retain the earlier project diagnostic: matching FA-AR within 0.03 of 0.83,
and **every** forest seed within 0.03 of 0.72. The tolerance is ours, not a
statistical test or author standard. No ensemble rescue or outcome-guided
settings/seed changes. Even a numerical match cannot recover the original
snapshot/caller. Report the actual incremental gain over the matching FA-AR,
not just a comparison to AR(4), before considering Jev.

## Run and audit

Config: [mrf_september2018.json](../configs/mrf_september2018.json).
Runner: [mrf_september2018.py](../scripts/mrf_september2018.py).
From the repository root, substitute the pinned archive, external engine and
task-local R library paths:

```sh
uv run --frozen python scripts/mrf_september2018.py prepare --archive ARCHIVE --engine ENGINE --r-library R_LIBRARY --output runs/mrf-september2018-v1
uv run --frozen python scripts/mrf_september2018.py execute --archive ARCHIVE --engine ENGINE --r-library R_LIBRARY --output runs/mrf-september2018-v1 --workers 6
```

`execute` fits the full grid, audits it and generates local `result.md`,
`audit.json`, `predictions.csv` and `metrics.csv` after all fits complete. It
does not need another chat turn to start verification. `run` and `audit` remain
available separately. A failed native job or audit raises an error, not a pass.
No automatic external messages or publication are scheduled.

Preparation binds the RF manifest/audit/predictions, archived data, every
matrix/settings file, adapter, verification code and native engine. `run`
resumes only checksum-verified completed jobs. A separate `prepare --pilot`
creates a two-tree, one-seed, one-window preflight in a **fresh directory**;
its `audit --allow-partial` reports integrity only, never accuracy. Pilot
outcomes cannot establish the full result or select the full configuration.

The auditor reconstructs all six states from the archive, checks raw-RF input
pairing, every origin/target and future-target mask, independent base-R QR
versus Python linear forecasts, unchanged AR denominator, finite native
coefficients and their forecast decomposition, output hashes and runtimes.
It is an artifact audit, **not an independent refit of every full native tree**.
Synthetic checks separately compare MAF projections against covariance
eigendecomposition, exercise future-data independence and reject altered
declarations/partial-result promotion.

No Jev or LLM forecasting calls belong to this run. Licensed PDFs and private
correspondence are not redistributed.
