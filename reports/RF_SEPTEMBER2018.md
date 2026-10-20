# September 2018 plain RF: close, but the declared criterion still fails

October 20, 2026. The complete raw-indicator RF run and artifact audit finished:
36 fits, 18,000 trees, six refits and 48 target quarters. Primary RF/AR(4)
ratios are **0.983534, 0.971506 and 0.965598**, against the printed **1.00**.
Two seeds pass the declared +/-0.03 diagnostic; seed 303 misses. **The
all-seed criterion is false.** Do not relabel this as exact reproduction or
silently relax the threshold. No September-vintage MRF has run yet.

## What changed from the older work?

- Downloaded and checksum-pinned the official September 2018 FRED-QD member.
- Used the actual R `ranger` backend, 500 trees, min.node.size=3 and two-year refits.
- Implemented **plain RF**, not RF-MAF: 247 transformed indicators times eight
  observations = **1,976 features**. No extra factors, MAFs, trend or log-target lags.
- Kept delta-log unemployment as the target; the raw-panel UNRATE feature keeps
  the supplied difference-in-levels transform.
- Audited direct origin/target alignment. At origin 2002Q4 the label is 2003Q1,
  current-through-seven-old raw observations span 2002Q4 back to 2001Q1, and
  training labels end in 2002Q4. The last training origin is 2002Q3.

The old target-indexed L1:L8 construction is algebraically identical to
origin-indexed L0:L7 at h=1. We did **not** shift it an extra quarter. First
training target remains 1961Q3, with 166/174/182/190/198/206 fitting rows.
The original caller's first-target-versus-first-origin interpretation is still
unknown. Missing-value/outlier processing is fixed-rank-five and training-only,
fitted through each last training origin. It is an explicit assumption.

## All results, not a selected seed

| Model | RMSE | RMSE / matching AR(4) | Within 0.03 of 1.00? |
| --- | ---: | ---: | --- |
| Direct AR(4), intercept | 0.0335022029 | 1.000000 | Reference |
| Primary ranger defaults, seed 101 | 0.0329505593 | 0.983534 | Yes |
| Primary ranger defaults, seed 202 | 0.0325475882 | 0.971506 | Yes |
| Primary ranger defaults, seed 303 | 0.0323496520 | 0.965598 | **No** |
| Secondary appendix-style, seed 101 | 0.0306315147 | 0.914313 | No |
| Secondary appendix-style, seed 202 | 0.0299079479 | 0.892716 | No |
| Secondary appendix-style, seed 303 | 0.0306741251 | 0.915585 | No |

All methods use the same 48 outcomes, 2003Q1-2014Q4. The primary is not exactly
the rounded source cell either: none of its ratios rounds to 1.00. The 0.03
tolerance is our project diagnostic, not an author standard or statistical test.

The original mtry, sampling invocation, random seed and ranger version remain
unknown. The primary leaves unspecified choices at ranger defaults:
floor(sqrt(1976))=44 candidate variables and n bootstrap draws per tree.
The secondary was fixed **before outcomes** to make A.6's scope ambiguity
visible: floor(1976/3)=658 variables, 75% ordinary row subsampling without
replacement. It is not MRF block sampling and cannot rescue the primary.
No post-outcome tuning, seed replacement or averaging rule was used.

The raw RF is qualitatively near the AR benchmark. That useful observation does
not close the predeclared criterion or establish MRF's stronger nonlinear gain.

## Why 247 rather than 248 series?

The [Fed's official change log](https://www.stlouisfed.org/-/media/project/frbstl/stlouisfed/research/fred-md/fredqdchanges0324.pdf)
states that S&P: indust was removed from **all vintages** in April 2024.
Our currently served September 2018 archive therefore lacks one series that was
available before that removal. This is a documented data-fidelity difference,
**not proof that the omitted series explains any forecast discrepancy**.

The historical member is 238 quarters, 1959Q1-2018Q2. Member SHA-256:
`44fdb5914a25a560648fccc71f85d2ae02bbe0bebae199ec6d3dbdbc7ae5a1a7`.
The [declaration and commands](../docs/SEPTEMBER2018_RF.md) record its enclosing
archive pin. No later-vintage series was appended. The other paper's public
GLSS archive contains a March 2019 quarterly CSV, not an independent original
September 2018 copy. Bounded legacy endpoint and exact-name/code searches did
not recover the unmodified 248-series September file. A current direct URL
returned HTML despite HTTP 200 and was **not used as data**.

## Verification and provenance

Declaration commit `f7adc69df599f7fd49abbd1b7cea244ec45fa37b` precedes the
new macro outcomes. Every prepared matrix and settings file is checksum-bound.
The audit rebuilds all six windows from the archive with **zero difference**,
checks every origin/target record, and verifies AR(4) using independent NumPy
least squares against base-R QR in every job.

Every one of the 18,000 stored trees is independently traversed. Its terminal
means are reconstructed from sampled training outcomes and in-bag weights;
per-tree and forest-average predictions agree. Held-out labels never enter
forest fitting, sampling, terminal values or preprocessing. Actual-ranger
synthetic tests also perturb them and reproduce identical predictions.
Independent base-R rescoring agrees on all seven methods to at most 2.3e-16
in ratio units. The current full local suite passed **466 tests**, including
actual R MRF/TVP/ranger and optional neural contracts. Runtime is R 4.6.1,
ranger 0.18.0, Rcpp 1.1.2 and RcppEigen 0.3.4.0.2, not the historical runtime.

A formatter-only source-list change was then committed in
`0cd536741645ab0c5ede1c82051461877b759c3b`. Python AST equality was verified;
no fitting code or settings changed. V1's provenance remains bound to its
original source commit. The fresh v2 repeat and audit are **complete**. All
six prepared windows, all 36 settings, every prediction, every complete saved
RDS forest and its runtime metadata reproduce byte-for-byte. The two audit
outcomes are identical apart from the explicitly different orchestrator hash.
This is 36 distinct cases refitted twice, not 72 independent experiments.

- [Full current audit](rf-september2018-audit.json).
- [Original v1 audit, preserved](rf-september2018-v1-audit.json).
- [Historical-source and deterministic-repeat checks](rf-september2018-repeat-audit.json).
- [All 336 forecasts](rf-september2018-predictions.csv), seven methods times 48 dates.
- [Metrics](rf-september2018-metrics.csv) and [independent R rescore](rf-september2018-base-r-rescore.csv).

Current audited manifest SHA-256:
`f55bb3212c0c9a6889363f52ca605462efb738e36227b150c49a1bc5e5a67ca1`.
Prediction CSV SHA-256:
`e27c526f9a7fbe81da216ec114de702ef3a991e5e766e3fd55d72ff2adbf649e`.
The declaration's CI initially exposed a list-formatting failure; the following
commit fixes it. Local lint/format checks pass. The corrected CI's Python/API
and neural jobs have passed; its expanded actual-R job is still running at
this report's publication. Do not equate pending CI with a successful check.

## Next decision

The requested order was plain RF first, then MRF. Under the strict gate, the
first step remains unresolved. Either recover the missing original snapshot
and invocation details, or explicitly authorize MRF as a **qualified
reconstruction**, without claiming the RF paper cell has been reproduced.
Do not propagate plain-RF's 500-tree/min.node.size=3 settings to MRF: its
linear-leaf engine has different parameters and constraints.

The earlier March 2019 runs and every original source-cell failure are unchanged.
No Jev or LLM forecasting calls have run.
