# September 2018 plain-RF reconstruction

Declared October 20, 2026, before computing this path's macro forecast losses.
The earlier March 2019 results, code and configs remain unchanged.

## Problem, inputs, target

First test the plain RF unemployment h=1 cell in appendix Table 4: RMSE divided
by the matching direct AR(4) RMSE, printed as **1.00**. This is **not** the
RF-MAF cell (0.85), AR+RF (0.84), or FA-ARRF (0.72). Main Table 2 specifies
eight observations of each stationarity-transformed raw indicator for plain RF.
Do not include target-log-change lags, factors, MAFs or a trend as extra RF features.
The panel UNRATE feature retains its supplied difference-in-levels transform;
the forecast target is the paper's difference in log unemployment.

Use the [St. Louis Fed historical FRED-QD archive](https://www.stlouisfed.org/research/economists/mccracken/fred-databases),
member `FRED-QD_2018m09.csv`. Archive SHA-256:
`56c5ff7ae60c9ed1468a4219bdda2a3f41644a16e1e1a7520cc38779d03df1df`.
Member SHA-256:
`44fdb5914a25a560648fccc71f85d2ae02bbe0bebae199ec6d3dbdbc7ae5a1a7`.
It contains 247 series, 1959Q1-2018Q2, not the paper's stated 248.
Keep the file intact; do not append later-vintage series to force the dimension.
This is a fixed-vintage retrospective exercise, not a historical-release backtest.
The other paper's public GLSS archive contains March 2019 FRED-QD, so that
archive does not independently corroborate a September 2018 quarterly snapshot.

## Date alignment

At origin `o`, predictors contain `x[o],...,x[o-7]`; the direct label is
`delta_log_UNRATE[o+h]`. AR(4) has an intercept and
`y[o],...,y[o-3]`. Fit only pairs whose label is observed by the refit cutoff.
For h=1, this is identical to target-date-indexed L1:L8, not a reason to shift
the old model's observations forward by another quarter.

| Quantity | First forecast |
| --- | --- |
| Target date | 2003Q1 |
| Origin/current predictor date | 2002Q4 |
| Oldest raw indicator date | 2001Q1 |
| Latest training label | 2002Q4 |
| Latest training origin | 2002Q3 |

Keep first training **target** 1961Q3 (origin 1961Q2), expanding estimation,
48 target dates 2003Q1-2014Q4, and six refits eight quarters apart. The original
caller's interpretation of the first training date remains unrecovered.
Between refits the coefficient map is fixed; newly observed predictors enter.
Synthetic contracts check direct h=1/2/4/6/8 label construction, the final
forecast row, and future-covariate/target perturbation invariance.

## Settings and unresolved choices

Use actual **R ranger, 500 trees, min.node.size=3**, and two-year refits.
`min.node.size` is the minimum size for splitting, not a minimum terminal size;
leave `min.bucket=1`. See the [package documentation](https://imbs-hl.github.io/ranger/reference/ranger.html).
The original ranger version, seed, mtry and sampling arguments are not recovered.
Do not silently describe those unspecified arguments as verified author settings.

Freeze seeds 101/202/303 and two separately labeled variants:

| Variant | Candidate variables | Sampling | Role |
| --- | --- | --- | --- |
| ranger_defaults | floor(sqrt(p)) | Bootstrap, n draws | Primary: retain defaults for unspecified arguments |
| appendix_style | floor(p/3) | 75% of rows without replacement | Fixed secondary: ambiguity about A.6's scope |

Both use variance splits, unlimited depth and one R thread. The secondary has
ordinary ranger row subsampling, **not** the MRF engine's block sampler. It is
not asserted to be the original plain-RF invocation, nor selected by test error.
No grid search, seed selection or ensemble rescue is permitted.

Missing values still need a stated reconstruction rule. Reuse the existing
fixed-rank-five completion and 10-IQR outlier treatment, fitted only on training
origin rows. Transform each later row independently with frozen parameters.
Do not use the resulting factors as plain-RF features. These preprocessing
choices remain assumptions, not recovered original code.

## Run and verify

Install `ranger` into a task-local R library with
`Rscript scripts/setup_ranger_r.R R_LIBRARY`. This path pins ranger 0.18.0;
the local runtime is R 4.6.1, Rcpp 1.1.2 and RcppEigen 0.3.4.0.2, not claimed
to be the original historical runtime. Record the actual R/ranger runtime.
From the repository root, with the archive and R library paths substituted:

```sh
uv run --frozen python scripts/rf_september2018.py prepare --archive ARCHIVE --output runs/rf-september2018-v1 --r-library R_LIBRARY
uv run --frozen python scripts/rf_september2018.py run --archive ARCHIVE --output runs/rf-september2018-v1 --r-library R_LIBRARY
uv run --frozen python scripts/rf_september2018.py audit --archive ARCHIVE --output runs/rf-september2018-v1 --r-library R_LIBRARY
```

Each refit saves the raw/AR matrices, explicit origin/target table, masked future
labels and exact settings. Freeze checksums before fitting. The audit rebuilds
all inputs from the pinned archive, independently checks AR(4) with NumPy versus
base-R QR, traverses every saved forest tree and checks sampled/weighted terminal
means against training outcomes. RDS model artifacts remain ignored in `runs/`.

The diagnostic gate is the existing project tolerance of 0.03 absolute ratio:
**every primary seed** must be within 0.03 of 1.00. It is not an author-supplied
criterion, an exact rounded-cell reproduction, or a statistical test. The
secondary cannot rescue it. Only after this primary check passes do we proceed
to MRF on this vintage. A plain-RF match cannot establish MRF reproduction.
If it misses, report the miss and retain the outstanding data/preparation and
invocation questions; do not search for a setting that produces 1.00.

Sources: [Goulet Coulombe (2024)](https://doi.org/10.1002/jae.3030), main
Section 3/Tables 1-2 and appendix A.6/Table 4. Licensed PDFs and private
correspondence are not redistributed.
