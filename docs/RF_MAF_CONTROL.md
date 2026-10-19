# What should the plain-forest control actually test?

October 19, 2026. Source definitions and a plain-forest building block are now checked and implemented. **The quarterly RF-MAF runner, full declaration and macro forecast comparison are not yet implemented.** No new macro forecast loss was calculated in this stage. The failed FA-ARRF replication and every earlier result remain unchanged.

## Problem, inputs, target

The next control asks whether a conventional forest can forecast the same quarterly unemployment target from the same rich state. It is not another factor-preparation sensitivity.

In [Goulet Coulombe (2024)](https://doi.org/10.1002/jae.3030), main Table 2 (PDF page 9, printed page 409) distinguishes RF-MAF from both ordinary raw-indicator RF and MRF. RF-MAF applies a plain forest to the full state S(t). That state includes the target lags, time, individual indicator lags, cross-sectional factor lags and per-series moving-average factors in Table 1. Plain RF instead uses eight lags of the transformed raw indicators. These are not interchangeable feature sets.

AR+RF is another distinct control: first fit an AR(2), then apply the rich-state forest to the remaining target component. Its future forecast adds the AR forecast and forest residual prediction. The AR(2) coefficients must be fitted on each training window only; future actual outcomes cannot enter residual construction. This second-stage runner is still pending.

The [publisher appendix](https://onlinelibrary.wiley.com/doi/suppl/10.1002/jae.3030/supinfo/jae3030-sup-0001-Appendix.pdf), Table 4 (PDF page 31, printed page 70), reports unemployment h=1 RMSE/AR(4) ratios of 0.85 for RF-MAF and 0.84 for AR+RF. These are source targets, not our results. Source significance stars are not transferred to project estimates. A.6, PDF pages 16-17, states an untuned reference, quarterly nominal parent size 10 and 75% subsampling; it discusses one-third candidate-feature sampling without identifying every original invocation detail.

## Why a separate building block?

The [pinned native MRF engine](https://github.com/philgoucou/macrorf/blob/bdb2ed435affb741aafdf78bab12c470ec6d55d0/R/MRF_v210403.R) rejects an empty linear equation. It also estimates terminal coefficients from all non-held-out observations routed to a leaf and has MRF-specific regularization and split machinery. The real-R rejection contract now confirms that an empty X does not run a plain RF-MAF. Removing factor slopes or relabeling an existing MRF output would not implement this control.

The separate `PlainBlockForest` primitive fits squared-error CART trees and averages their predictions. Each leaf uses only the rows retained for that tree. It has no MRF ridge/RW prior, jitter, rank preference or full-training leaf regression. A synthetic omitted-row perturbation verifies that excluded target values do not enter the terminal means.

Its sampling law independently reconstructs the native random-group/quantile procedure: sort randomly assigned group labels, attach exponential group weights, and retain rows above a strict row-weight quantile. The nominal block parameter is eight, as in the frozen quarterly reconstruction. Groups are contiguous but randomly sized, and the realized retained fraction need not equal 75%. Empty draws fail; there is no hidden redraw. Base-R contracts verify group-count truncation and the cutoff on identical supplied weights, **not** equivalence of R and NumPy random sequences.

Primitive defaults are 100 trees, seed 101, nominal subsampling 0.75, candidate-feature fraction 1/3, minimum parent 10 and minimum leaf one, with unrestricted depth and no pruning. These are explicit reconstruction choices, not recovered RF-MAF per-table settings. The local backend is scikit-learn 1.9.1, not the author's unidentified plain-RF backend. Its [documented CART semantics](https://scikit-learn.org/stable/modules/generated/sklearn.tree.DecisionTreeRegressor.html) include float32 feature conversion and a valid-split search that may inspect beyond the configured candidate-feature count. The primitive fits no scaler internally. These numerical/implementation differences must remain visible in any comparison.

## What is verified, and what comes next?

The tests use actual sklearn fits on synthetic data. They check deterministic sampling, whole-group selection, sampled-leaf means, prediction averaging, future-row independence, input validation and failed-refit handling. Four new real-R contracts cover the cutoff/dimension checks and the native empty-equation rejection. They are integration evidence, not macro forecasting evidence.

Before any full comparison, add a separate executable declaration and runner that bind the frozen original all-248 primary state matrices, target masks, 48 dates, six refits and all three declared seeds. Retain the original primary construction rather than select a later sensitivity using its test score. Declare scaling, backend, tree settings, seed semantics and the named source-cell diagnostic before its outcomes. Verify all matrices, sampled-row provenance, leaf means, per-tree averaging and saved aggregates; suppress partial scores. A plain-forest comparator match would not close the still-failed FA-ARRF joint criterion or recover missing author settings.

The inspected PDFs have SHA-256 `a1ea26466f55425bafc1f76eed2c28d0cb77d9203b2b4eebf105b972fbaaa1ee` (article) and `665fac2b6a21b8f2b28442dfe60aec30aee542c3dac2876b322f4e249718fb1b` (appendix). Complete relevant pages were read and the benchmark tables/settings visually inspected. Licensed PDFs and private correspondence are not redistributed.
