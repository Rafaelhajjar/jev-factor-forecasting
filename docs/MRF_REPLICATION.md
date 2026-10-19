# MRF replication checklist and verified inputs

Inspected October 18–19, 2026, including the final article, appendix and pinned author engine. This is the first milestone of the [active research protocol](RESEARCH_PROTOCOL.md). The full quarterly reconstruction has completed and passed its artifact audit, but it misses the published forest ratio and is not an exact replication. See the [completed result](../reports/MRF_UNEMPLOYMENT_RECONSTRUCTION.md), [code audit](AUTHOR_CODE_AUDIT.md) and [appendix discrepancy register](APPENDIX_FINDINGS.md).

## Source versions

| Item | Reference | Status |
| --- | --- | --- |
| Published article | Goulet Coulombe (2024), JAE 39(3), 401–421, [DOI](https://doi.org/10.1002/jae.3030) | All 21 PDF pages read; main Section 3 and Tables 1–2 checked directly |
| Published supporting appendix | [Publisher PDF](https://onlinelibrary.wiley.com/doi/suppl/10.1002/jae.3030/supinfo/jae3030-sup-0001-Appendix.pdf) | All 32 PDF pages read; settings/algorithm and Tables 4–5 visually checked |
| Earlier manuscript | [arXiv 2006.12724](https://arxiv.org/pdf/2006.12724), displayed March 2021 draft | Historical context, no longer the specification authority |
| Journal replication data | [Data DOI](https://doi.org/10.15456/jae.2023321.0115060814) | Downloaded and inspected in local scratch space |
| Author's R implementation | [philgoucou/macrorf](https://github.com/philgoucou/macrorf), commit `bdb2ed435affb741aafdf78bab12c470ec6d55d0` | Engine audited and called externally; no paper runner in the repository |
| Python implementation | [RyanLucas3/MacroRandomForest](https://github.com/RyanLucas3/MacroRandomForest), commit `8069107d6e1f92e8ef9fade782dfda97f8bd66d8` | Candidate cross-check; not assumed numerically identical |

The journal archive redirected to [ZBW Journal Data](https://journaldata.zbw.eu/dataset/the-macroeconomy-as-a-random-forest-replication-data). Its README says that observations are in levels and need the appropriate transformations. The ZIP contains CSVs and a README, not a complete experiment runner. Do not confuse an implementation package with a full replication package.

## Verified files

Archive [download](https://journaldata.zbw.eu/dataset/c48432e1-5a25-49f1-95b1-6c681f21e252/resource/9c8c1313-bb06-4bd1-83ac-be22b0cc12ed/download/the-macroeconomy-as-a-random-forest-replication-data.zip):

```text
archive SHA-256
5b31cd2ad184ffc8d1710433fbc34a5ac110f8b4bfa69f3c1400fdd828a9de8c

FREDQD_2019-03.csv SHA-256
69226fbe297c09fdbf011c7c09e9c3abf04db1b1dfbba203b51291b825a00335

FREDMD_2018-01.csv SHA-256
9ed47f32eb54b9539662bb940cea352ac2fac8bc558de017317c753f794a9f00
```

The quarterly file has separate `factors` and `transform` metadata rows: 255 fields per row, including date, but 248 populated observation columns. The S&P names are split across header tokens near the tail, where six columns have no observations or metadata. The dedicated loader now repairs the exact verified signature, preserves all 248 series and rejects populated padding. It validates dates, transformations and archive/member checksums.

The `factors` row identifies the historical Stock-Watson subset: 125 included and 123 excluded series. It does not determine whether the MRF author used all series for PCA. The first reconstruction explicitly uses all 248, with training-only fixed-rank-five completion/PCA; original factor eligibility and preprocessing remain unresolved. The monthly loader remains a separate path. See the [data audit](AUTHOR_CODE_AUDIT.md#4-quarterly-archive-and-factor-construction).

Raw archive files remain outside Git. The [planning manifest](../research/mrf_extension_plan.json) stores provenance without relicensing or redistributing the observations.

The appendix download has SHA-256 `665fac2b6a21b8f2b28442dfe60aec30aee542c3dac2876b322f4e249718fb1b`. Neither the licensed article PDF nor the appendix PDF is committed.

## Confirmed source specification

- Primary target: first difference of log unemployment, one quarter ahead. Do not substitute unemployment level or percentage-point change.
- FA-ARRF design: intercept, two target-history terms, and one value from each of two PCA factors, with five time-varying coefficients. Preserve the exact origin/target indexing in reference code.
- State: eight target lags, time, two lags of FRED-QD indicators, eight lags of five PCA factors, and two MAFs obtained from eight lags of each indicator.
- Expanding estimation from 1961Q3; evaluation target dates 2003Q1–2014Q4; direct horizons 1/2/4/6/8 quarters; two-year main re-estimation cadence. SETAR/STAR use their separately specified iterated procedure.
- A.6 says the main RF hyperparameters are untuned. A.4/A.6 specify 75% block subsampling, two-year blocks, minimum parent size 10 quarterly / 15 monthly and OLS ridge prior means. Confirm remaining effective settings from code; don't mistake tree-count recommendations or a suggested mtry for per-run facts.
- First Table 4 cells (unemployment h=1), ratios to AR(4): FA-AR 0.83, FA-ARRF 0.72, RF-MAF 0.85, ARRF 0.90, AR+RF 0.84, TV-FAAR 1.19, NN 0.80. Keep source values and our future reproduced estimates in separate columns.
- Monthly A.7 targets average transformed outcomes across the next h months, not the transformed value at t+h. The denominator and exact monthly panel still need reconciliation.

## Source/code issues still open

The [evidence register](APPENDIX_FINDINGS.md#7-remaining-discrepancies-to-resolve) records the extra HOUST target row, AR(12)-versus-AR(4) monthly denominator, A.2 sample lengths and TV-FAAR schedule. The generic engine does not resolve those discrepancies. It does establish actual defaults, an effective parent-size floor and all-row standardization. Our adapter's training-only normalization, OLS prior variances and factor processing are explicit reconstruction choices, not recovered paper settings.

`configs/mrf_unemployment.json` freezes 100 trees, seeds 101/202/303 and an absolute ratio tolerance of 0.03 before full forest results. That diagnostic tolerance is ours, not a statistical test. The full 48-quarter fixed FA-AR/AR(4) ratio is 0.812577, compared with the source's rounded 0.83. Forest ratios are 0.797325, 0.804184 and 0.806346, all outside tolerance from 0.72. The full numerical criterion fails. Artifact integrity passes for all 18 jobs; unknown source settings remain unresolved rather than inferred from these scores.

## Required before adding Jev

- [x] Identify the published citation and accessible earlier manuscript.
- [x] Read the final 2024 article and publisher-supplied appendix, recording exact locations and evidence boundaries.
- [x] Resolve and inspect the journal's exact archive.
- [x] Record archive/member hashes and candidate reference-code revisions.
- [x] Name the first reported comparison cells and distinguish forecast-table timing from interpretation experiments.
- [x] Resolve or explicitly qualify the source inconsistencies against pinned reference code.
- [x] Lock a documented reconstruction's target, factor panel, completion, outlier and PCA conventions without claiming they are the missing original runner.
- [x] Lock reconstruction origin/target dates, endpoints and two-year refit cadence.
- [x] Declare reconstruction settings/seeds/tolerance and record actual R/package versions per job.
- [x] Add past-only factor/state/target handling and real-engine future-perturbation contracts.
- [x] Retain a qualified-reconstruction boundary; exact original processing and per-table invocation remain unknown.
- [x] Run the linear benchmark and reference MRF without Jev; retain forecasts and coefficient decompositions.
- [x] Compare cells using the predeclared tolerance and report its failure without attributing an unverified cause.
- [ ] Reproduce the published nonlinear gain; current independent reconstruction does not meet this milestone.
- [ ] Build genuinely prequential development cases for the new policy, then freeze its prompt and candidate construction.

The protocol's dates, lag structure and target are supported by the final article. The full result now establishes a working independent baseline, not recovery of the original pipeline. Independent extension tooling may proceed under that label, while exact replication and strong-comparator work remain explicit open milestones. An eight-quarter, two-tree smoke test still checks execution only, not the published score.

The [ARRF diagnostic](ARRF_DIAGNOSTIC.md) now completes the paper's simpler forest equation on the exact existing state matrices. Its ratios 0.892599, 0.894426 and 0.901878 all agree with the source's 0.90 under the declared tolerance; all 18 jobs and saved aggregates pass artifact checks. This adds a named benchmark without changing the failed primary result or selecting settings on its test loss. It does not close the FA-ARRF replication requirement. See the [completed diagnostic report](../reports/MRF_ARRF_DIAGNOSTIC.md).
