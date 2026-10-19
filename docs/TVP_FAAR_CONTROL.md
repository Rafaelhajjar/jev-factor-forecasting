# Can the native time-varying factor regression match its unemployment cell?

Declared October 19, 2026, after the earlier primary, ARRF, factor-preparation and plain-control results, but **before this TV-FAAR control's actual-data pilot or full outcomes**. The [configuration](../configs/mrf_tvp_faar.json) and runner preserve the original primary inputs. This is a post-primary reconstruction, not a blind confirmation or an attempt to replace the still-failed FA-ARRF result.

## Problem, inputs, target

Main Table 2 of [Goulet Coulombe (2024)](https://doi.org/10.1002/jae.3030), PDF page 9, gives TV-FAAR an intercept, four target-history terms and two lags of each of two factors: **nine coefficients**, not FA-ARRF's five. Reuse those exact eight regressor columns from the original all-248 primary matrices. Do not substitute the later PCA125 or FRED125 preparation because of its test score.

Keep delta-log unemployment, the same 48 target dates in 2003Q1–2014Q4 and the six original expanding refits. Pass only training outcomes and the eight forecast regressor rows to the native estimator. It uses a driftless-random-walk endpoint coefficient for forecasts; freeze that endpoint within each two-year block. Forecast regressors still update at each origin.

Section 3 specifies two-year re-estimation, while Table 2's footnote and the later coefficient-analysis discussion mention 2007Q2. The latter context can help explain the different dates, but does not recover the missing per-table invocation. A single fit using data through 2007 cannot produce genuine OOS forecasts beginning in 2003. This forecast comparison follows Section 3's two-year rule; it does not treat full-sample smoothing or the 2007 interpretation experiment as the 48-date benchmark. The exact historical TV-FAAR caller remains unknown.

The appendix's Table 4, PDF page 31, reports TV-FAAR/AR(4) = **1.19** for unemployment h=1. Retain the original AR(4) denominator and the same absolute-ratio tolerance of 0.03. This is our diagnostic, not an author standard or statistical test. Matching this cell cannot establish FA-ARRF's 0.72, its nonlinear gain or exact source fidelity.

## What the author code actually does

The [author's code page](https://philippegouletcoulombe.com/code) links the public TVP package. We inspected its entire source and help file at commit [d2d52bb9e0126fb580fb8301f305035d3047b4b2](https://github.com/philgoucou/tvpridge/tree/d2d52bb9e0126fb580fb8301f305035d3047b4b2), dated July 1, 2021. It contains an estimator, not the 2024 quarterly runner.

The native entry point divides training X and y by sample SDs without demeaning, adds an intercept, cross-validates a ridge penalty, estimates a first coefficient path, updates observation weights using GARCH(1,1) and relative coefficient-innovation weights, cross-validates again, and refits. Preserve its defaults: 15 log-spaced candidates from exp(-6) to exp(20), initial-level penalty 0.1, five random folds, both weight exponents 0.75, zero-centered initial-level prior and second-stage CV enabled.

Both CV functions reset the R seed to 1071. They use random folds and a native dropout adjustment, not chronological validation. An outer three-seed ensemble would not supply three independent CV realizations. This control therefore has six native fits, one per refit, and no invented seed ensemble. Later extension-policy development still requires the protocol's chronological/prequential validation.

An important return-value boundary: the public result's lambdas field describes the first-stage selection, even when the second stage selects another value. Our read-only tracing captures **both actual selections and their candidate indices**, both CV score tables, fold assignments, coefficient paths, innovation weights, GARCH input/conditional SD/parameters and optimizer convergence code. Trace instrumentation records local values; it does not modify the external source file or estimation expressions.

GARCH optimizer warnings are not repaired by choosing a different algorithm, retrying, changing seeds or substituting weights. Retain the code for every refit and report arithmetic integrity separately from optimizer convergence. Verifying a volatility recursion does not prove that maximum-likelihood optimization converged.

## What must verify before interpretation?

Repeat the complete original primary artifact audit, including reconstruction of all six 1,041-column states and independent R linear checks. Pin the primary configuration, archive/source manifests, matrices/settings, model/refit/target grid, code and runtime. The native dependency stays external and GPL-3, not vendored under this project's MIT license.

An independent Python calculation derives the integrated random-walk covariance directly, rather than using the native augmented design. It reconstructs both coefficient paths, fitted values, the native CV scores and selected candidates, weight updates, the GARCH variance recursion and every forecast. Tolerance is 1e-7 in standardized units; candidate indices are exact, with only 2e-15 relative allowance for R/Python scalar serialization. Synthetic contracts include direct penalized normal equations and explicit augmented-basis CV as additional cross-checks.

The final quarterly auditor independently repeats **every complete native fit** and requires identical saved numerical artifacts, including both CV stages and final tuning metadata. It also checks original equation-row equality, forecast/origin timing, aggregates, metrics and the source-cell flag. Every loaded R namespace version and GARCH convergence code is retained. Current required package versions are pracma 2.4.6, fGarch 4052.93 and matrixcalc 1.0-6; transitive versions are recorded, not claimed to be the author's historical environment.

A one-refit/eight-date pilot reports integrity only. Preparation-only, reduced and incomplete runs suppress performance scores. Full scores require all six refits and all 48 dates.

## Reproduce

Complete the original primary reconstruction first. Install the pinned direct R dependencies in a project-local library; source installation may require C/Fortran build tools.

~~~bash
Rscript scripts/setup_tvp_r.R runs/r-library

uv run python scripts/tvp_faar.py run \
  --source-run runs/mrf-unemployment --output runs/tvp-pilot --max-refits 1
uv run python scripts/tvp_faar.py audit \
  --run runs/tvp-pilot --output reports/my-tvp-pilot.json --allow-partial

uv run python scripts/tvp_faar.py run \
  --source-run runs/mrf-unemployment --output runs/tvp-full
uv run python scripts/tvp_faar.py audit \
  --run runs/tvp-full --output reports/my-tvp-full-audit.json
~~~

The runner fetches/checks the pinned external TVP source. Use --prepare-only to save the input declaration without fitting/scoring, and --resume for an unchanged prepared run or verified checkpoints. An incomplete native fit is preserved and rejected rather than overwritten. No Jev, LLM or hosted forecasting calls occur.

The inspected article and appendix hashes remain a1ea26466f55425bafc1f76eed2c28d0cb77d9203b2b4eebf105b972fbaaa1ee and 665fac2b6a21b8f2b28442dfe60aec30aee542c3dac2876b322f4e249718fb1b. Relevant complete pages and the main specification-table visual were checked. Licensed PDFs and private correspondence are not redistributed.
