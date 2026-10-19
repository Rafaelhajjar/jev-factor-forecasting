# Author-code audit and reconstruction boundary

Audited October 18-19, 2026. The public code settles how this version of the engine behaves. It does **not** recover the unpublished settings used to produce every paper table. The first unemployment run is therefore a documented reconstruction, not an exact replication claim.

## 1. What is actually available

The reference is the author's [R repository](https://github.com/philgoucou/macrorf/tree/bdb2ed435affb741aafdf78bab12c470ec6d55d0), commit `bdb2ed435affb741aafdf78bab12c470ec6d55d0`. It contains the model engine and function documentation, but no quarterly paper runner, factor-preparation script, simulation generator or table-generation code.

Engine `R/MRF_v210403.R` SHA-256:

```text
e052c0f12544a2bfb79974c07174b08116b7c80298de5905bdb3753732a7b631
```

The author's [MacroRF-1 documentation fork](https://github.com/philgoucou/MacroRF-1/tree/8157619249bbdda3d0e4c8ea694d7c9168f5949f) provides monthly PAYEMS tutorials. Their data, full-sample factor construction and lag choices differ from the quarterly experiment. They are examples, not the missing paper runner. The Ryan Lucas Python port is a cross-check, not an independent source of the original table settings. The journal archive supplies data and a README, not code.

The author's [Code & Data page](https://philippegouletcoulombe.com/code), checked October 19, 2026, points to these packages and invites email requests for raw code. That is a possible route to the missing pipeline, not evidence that we have obtained it or that the original scripts are publicly downloadable. No original runner has been recovered. Independent implementation proceeds under the assumptions below rather than waiting for external code.

We also inspected the [arXiv v3 source archive](https://arxiv.org/src/2006.12724v3), submitted March 4, 2021 (archive SHA-256 `d9a3517db3d2a1a35ebe0f16eb6b82b7900129c741d0cd9805a1ae67becb2817`). It contains TeX, figures and rendered result tables, not the benchmark runner or DGP generator. The 400-fit/600-OOS prose versus 750-OOS caption discrepancy is present in the TeX itself, not an extraction artifact. Inactive older captions mentioning 1,000 trees and 80% subsampling are not evidence for the final paper's invocation and do not override its 75% scheme. The source bundle stays outside Git. The public R repository exposes only its single July 2021 `main` commit and no tagged earlier engine release; the paper's exact engine version remains unverified.

The R engine declares GPL-3. It is fetched separately, verified by checksum and called as an external dependency. We do not copy it into our MIT source tree or relicense it.

## 2. Defaults are not the paper's complete specification

These are effective defaults in the [top-level function, lines 2-10](https://github.com/philgoucou/macrorf/blob/bdb2ed435affb741aafdf78bab12c470ec6d55d0/R/MRF_v210403.R#L2-L10), unless noted otherwise.

| Item | Public engine | First reconstruction |
| --- | --- | --- |
| Tree count | 50 | 100, with seeds 101, 202 and 303 declared before forest results |
| Block parameter | 12 observations | 8, following the quarterly appendix |
| Subsampling | Option 2, rate 0.75 | Unchanged |
| Candidate-state fraction | 1/3 | Unchanged |
| Random-walk regularization | 0.75 | Unchanged |
| Ridge penalty | 0.1 | 0.1; the help usage and inner-function default instead say 0.01 |
| Minimum leaf/regressor fraction | 1 | Unchanged |
| Minimum parent size | Nominally 10 | Pass 10; the engine raises it to 12 for this five-coefficient equation |
| Trend push | 1 | Unchanged; a help-text suggestion of 4 is not the default |
| Ridge prior | No supplied mean: zero-centered shrinkage | Training OLS mean, following A.6; variances 100 for intercept and 1 for slopes are our explicit assumption |
| Fast RW mode | `TRUE` | Unchanged: RW terms enter terminal prediction but not split search |

The parent-size adjustment is in [lines 411-413](https://github.com/philgoucou/macrorf/blob/bdb2ed435affb741aafdf78bab12c470ec6d55d0/R/MRF_v210403.R#L411-L413). This is an effective implementation detail, not a reason to silently change the appendix's requested minimum. The block code uses random groups and a quantile cutoff; the nominal block parameter is not a guarantee that every realized contiguous group has length eight.

Keep the engine's split and terminal-regression machinery. In particular, terminal coefficients use all non-held-out rows routed to a leaf; the subsample also governs split construction and which neighboring observations can contribute. Replacing this with a standard tree's sampled-leaf regression would change the algorithm. See [terminal prediction, lines 850-889](https://github.com/philgoucou/macrorf/blob/bdb2ed435affb741aafdf78bab12c470ec6d55d0/R/MRF_v210403.R#L850-L889).

## 3. A timing issue we can test directly

The engine calls `standard(data)` inside each tree. The [standardization helper](https://github.com/philgoucou/macrorf/blob/bdb2ed435affb741aafdf78bab12c470ec6d55d0/R/MRF_v210403.R#L1124-L1133) fits moments on **all supplied rows**, including rows designated out of sample. The help explicitly asks callers to supply training and testing rows together. This makes handling at the adapter boundary important; it does not prove that the author's original table leaked outcomes, because that caller is unavailable.

Our adapter:

1. Replaces every held-out target before scaling or calling R. Ground truth stays outside the engine input.
2. Fits centering/scaling and an OLS prior on training rows only.
3. Overrides the engine's normalization helper in its isolated R environment to use training moments only. The downloaded file is unchanged, but this override is a deliberate behavioral deviation.
4. Checks that every forecast equals its intercept plus four coefficient-times-predictor contributions, then converts both forecasts and coefficients back to the original units.

Real-R contract tests verify held-out-target perturbation invariance, coefficient reconstruction, and invariance of the first forecast to changes in later forecast-row predictors. A diagnostic using native all-row scaling does change that first forecast. This is evidence of a dependency in the public interface, not an estimate of its effect on the paper's score.

Pre-standardizing inputs also keeps prior means in training-standardized units before the engine's own prior conversion. No claim of a corrected upstream implementation is needed. Native all-row mode exists only as an explicitly named diagnostic; it is not the primary experiment.

The public code's threshold-rank penalty is not generally invariant to reversing a predictor's sign. We therefore record PCA orientation rather than assume it is irrelevant: scikit-learn's largest-magnitude loading is positive. The [cross-language basis audit](PCA_BASIS_AUDIT.md) now verifies that Python and R agree up to signs on all 30 cross-sectional and 2,976 MAF components. On the current R build, 22 and 1,468 respectively have opposite signs. A synthetic real-engine contract confirms forecast sensitivity, but this does not establish the author's original basis or attribute our macro score gap to orientation. The primary state remains unchanged.

## 4. Quarterly archive and factor construction

The deposited CSV has 248 populated series, but split S&P header text creates six empty padding columns. We repair only the exact verified signature, reject any populated padding, and restore these four names at positions 245-248:

```text
S&P 500; S&P: indust; S&P div yield; S&P PE ratio
```

There is also a sample-start discrepancy: main Section 3 describes the panel as observed from 1960Q1, whereas the deposited quarterly file has 240 rows from 1959Q1 through 2018Q4. Our reconstruction uses the deposited history, begins the transformed panel at 1959Q3 and obtains the first complete eight-lag regression row at 1961Q3. This agrees with the stated estimation start, but the exact original trimming must still be confirmed from its runner.

The official [FRED-QD paper and appendix](https://www.stlouisfed.org/-/media/project/frbstl/stlouisfed/publications/review/pdfs/2021/01/14/fred-qd-a-quarterly-database-for-macroeconomic-research.pdf) identify the metadata flag as membership in the historical Stock-Watson factor subset, not a universal rule forbidding other series from MRF factors. The archive has 125 included and 123 excluded flags. This resolves the flag's meaning, **not** whether the MRF paper used that subset for PCA. We use all 248, declare that choice and retain the flags for a separately named sensitivity check.

UNRATE's panel transformation code is 2, a level difference. The MRF article explicitly logs unemployment before differencing. Our target is therefore delta log UNRATE while its indicator-panel entry retains the deposited code. Conflating these two roles would change the target or the state.

The official [FRED data preparation code](https://www.stlouisfed.org/research/economists/mccracken/fred-databases) provides useful conventions: transformation codes, a median +/- 10-IQR outlier rule, and iterative PCA completion preserving observed cells. It is not proof of the author's exact processing. Our first reconstruction uses:

- Training-only outlier thresholds, fixed-rank-five EM completion and five PCA factors; maximum 100 EM iterations, relative reconstruction threshold 1e-6.
- Frozen loadings between two-year refits. Each new row's missing entries are completed independently from its observed contemporaneous entries; later rows cannot revise an earlier state.
- Two univariate PCA moving-average factors from eight lags of each series, fitted on training design rows only.
- The source's rich-state structure: 8 target lags + 40 factor lags + 496 indicator lags + 496 MAFs + trend = 1,041 state columns when all series remain active.

The official routine can choose the completion rank by an information criterion and uses a different iteration cap. Fixed rank five is our reconstruction choice. Exact preprocessing, completion rank, loadings, sign convention and outlier handling remain unknown without the original runner.

## 5. Frozen first run and comparison rule

Executable settings: [configs/mrf_unemployment.json](../configs/mrf_unemployment.json). Training target dates begin 1961Q3; evaluation target dates are 2003Q1-2014Q4, with six training refits through 2002Q4, 2004Q4, ..., 2012Q4. Each fit serves the following eight one-step forecasts; new lagged observations enter the state without re-estimating the map.

Our explicit row convention is: the 2003Q1 forecast uses target lags and indicator observations through 2002Q4, with coefficients fitted using outcomes through 2002Q4; the 2003Q2 forecast incorporates 2003Q1 observations but keeps that coefficient map. The package's one-step tutorials likewise pair a current outcome with lag-one predictors, but they do not establish the original quarterly runner's exact first-row alignment. Training-row factor loadings are estimated using the full fitting sample available at that refit; those rows are not historical prequential forecasts and cannot be reused as such for Jev training.

AR(4), fixed FA-AR and FA-ARRF share evaluation dates and outcomes. The fixed FA-AR has four target lags and two lags of each of the first two factors; the FA-ARRF equation has two target lags and one lag of each factor. All five FA-ARRF coefficients, including the intercept, vary.

We declared seeds 101/202/303, 100 trees and an absolute RMSE-ratio difference of 0.03 before inspecting the full forest results. The tolerance is our diagnostic criterion, not an author standard or a statistical test. Publish every seed and label their mean-prediction ensemble separately; do not select a favorable seed. A near match cannot resolve unknown source settings by itself.

Every run saves data and source hashes, configuration, masked inputs, training representation summaries, forecast dates, coefficient paths and R/package versions. Resume refuses changed settings or source hashes. Partial pilots cannot satisfy the 48-quarter comparison.

## 6. What the public engine cannot resolve

The extra HOUST target row, monthly AR(12)/AR(4) denominator, A.2's 600/750 OOS discrepancy, exact neural settings and TV-FAAR table schedule cannot be inferred from a generic MRF engine. They remain open in the [appendix register](APPENDIX_FINDINGS.md#7-remaining-discrepancies-to-resolve). HOUST itself exists in the data with transformation code 5; that does not establish the intended table target or timing.

Do not tune the unemployment test period to hit 0.72. If reconstruction differs, preserve it and investigate the gap transparently. Exact replication needs the missing benchmark/generator scripts or authoritative clarification. Independent extension tooling can proceed without waiting, but a later evaluation against this baseline must be labeled an independent-reconstruction extension, not an extension of an exactly replicated 0.72 model. Prequential development and prompt-freezing remain prerequisites for hosted evaluation.

## 7. Whole-run verification

The separate `audit-mrf` command checks the data/engine/source hashes, every declared refit/seed/date, raw-level log-difference targets and all eight target lags, the held-out-target mask, freshly rebuilt state matrices, saved coefficients and aggregated scores. State reconstruction uses our same declared preparation implementation; it verifies saved inputs, not an independently recovered author pipeline. Base-R QR regression independently checks the Python SVD linear forecasts. The verifier and R checker are themselves hashed in its report.

The checker rejects incomplete runs unless explicitly asked for a progress audit. Such an audit withholds forest scores and a numerical pass. The full diagnostic requires fixed FA-AR and every individual declared forest seed to fall within the previously declared 0.03 absolute-ratio tolerance; the seed-mean ensemble is excluded from that pass rule. This rule was recorded before full forest results were inspected. Exact source fidelity is always a separate unresolved item, even if every score matches.

October 19 final checks: all 48 linear forecasts agree between R and Python within 1.5e-15. All six 1,041-column state matrices match recomputation within 3.6e-15, and their EM fits converge. All 18 forest jobs pass coefficient reconstruction within 2.5e-15. Forest/AR(4) ratios are 0.797325, 0.804184 and 0.806346; the declared numerical-agreement criterion fails. The [completed report](../reports/MRF_UNEMPLOYMENT_RECONSTRUCTION.md) preserves this result and separates integrity checks from source fidelity.
