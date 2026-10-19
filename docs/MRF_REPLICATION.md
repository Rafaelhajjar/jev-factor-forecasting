# MRF replication checklist and verified inputs

Inspected October 18, 2026, including the final article and its appendix. This is the first milestone of the [active research protocol](RESEARCH_PROTOCOL.md). Final-source reading and locating the archive are complete; reconciling every code setting and reproducing the paper are not. See the [appendix evidence and discrepancy register](APPENDIX_FINDINGS.md).

## Source versions

| Item | Reference | Status |
| --- | --- | --- |
| Published article | Goulet Coulombe (2024), JAE 39(3), 401–421, [DOI](https://doi.org/10.1002/jae.3030) | All 21 PDF pages read; main Section 3 and Tables 1–2 checked directly |
| Published supporting appendix | [Publisher PDF](https://onlinelibrary.wiley.com/doi/suppl/10.1002/jae.3030/supinfo/jae3030-sup-0001-Appendix.pdf) | All 32 PDF pages read; settings/algorithm and Tables 4–5 visually checked |
| Earlier manuscript | [arXiv 2006.12724](https://arxiv.org/pdf/2006.12724), displayed March 2021 draft | Historical context, no longer the specification authority |
| Journal replication data | [Data DOI](https://doi.org/10.15456/jae.2023321.0115060814) | Downloaded and inspected in local scratch space |
| Author's R implementation | [philgoucou/macrorf](https://github.com/philgoucou/macrorf), commit `bdb2ed435affb741aafdf78bab12c470ec6d55d0` | Candidate reference; algorithm and settings audit pending |
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

The quarterly file has separate `factors` and `transform` metadata rows. An initial CSV inspection found 255 fields per row, including the date field, but 248 observation columns with any nonempty values. The S&P names are split across header tokens near the tail, where six columns have no observation values. Record a verified name/metadata repair map rather than silently accepting ambiguous duplicate names or dropping a financial series.

The `factors` row's inclusion/exclusion semantics need to be checked against the reference algorithm. Treating every series as eligible for PCA could change the intended factor construction. The monthly file has a different metadata layout; the existing monthly loader is not a validated quarterly loader.

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

The [evidence register](APPENDIX_FINDINGS.md#7-remaining-discrepancies-to-resolve) records the extra HOUST target row, AR(12)-versus-AR(4) monthly denominator, A.2 sample lengths, TV-FAAR estimation schedule and exact parameter invocations. Archive parsing, factor eligibility, missing/outlier processing, PCA fit window and factor orientation are still required. Final-source access is no longer a blocker; exact numerical replication is not yet established.

## Required before adding Jev

- [x] Identify the published citation and accessible earlier manuscript.
- [x] Read the final 2024 article and publisher-supplied appendix, recording exact locations and evidence boundaries.
- [x] Resolve and inspect the journal's exact archive.
- [x] Record archive/member hashes and candidate reference-code revisions.
- [x] Name the first reported comparison cells and distinguish forecast-table timing from interpretation experiments.
- [ ] Resolve or explicitly qualify the source inconsistencies against pinned reference code.
- [ ] Lock target transformations, factor-eligible series, missing-value/outlier rules, PCA details and factor orientation.
- [ ] Lock forecast origin versus target dates, sample endpoints, target aggregation and estimation/tuning cadence.
- [ ] Lock reference hyperparameters, random seeds and implementation/library versions.
- [ ] Audit factors, state predictors and target lags for information timing at every origin.
- [ ] Run the linear benchmark and reference MRF without Jev; retain forecasts and coefficient decompositions.
- [ ] Compare reproduced cells using a tolerance fixed before inspecting differences; explain unresolved discrepancies.
- [ ] Build genuinely prequential development cases for the new policy, then freeze its prompt and candidate construction.

The protocol's main dates, lag structure and unemployment target are now supported by the final article, not provisional working-paper anchors. Exact data processing and effective code settings remain distinct unresolved tasks. Reading source results does not check any numerical-reproduction box.
