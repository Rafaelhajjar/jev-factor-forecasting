# MRF replication checklist and verified inputs

Inspected October 18, 2026. This is the first milestone of the [active research protocol](RESEARCH_PROTOCOL.md). Locating inputs is complete; reproducing the paper is not.

## Source versions

| Item | Reference | Status |
| --- | --- | --- |
| Published article | Goulet Coulombe (2024), JAE 39(3), 401–421, [DOI](https://doi.org/10.1002/jae.3030) | Citation target verified |
| Accessible manuscript | [arXiv 2006.12724](https://arxiv.org/pdf/2006.12724), displayed March 2021 draft | Useful implementation anchors; not the final published text |
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

## Required before adding Jev

- [x] Identify the published citation and accessible earlier manuscript.
- [x] Resolve and inspect the journal's exact archive.
- [x] Record archive/member hashes and candidate reference-code revisions.
- [ ] Reconcile published article, appendix and earlier manuscript; name the exact result cells being replicated.
- [ ] Lock target transformations, factor-eligible series, missing-value/outlier rules, PCA details and factor orientation.
- [ ] Lock forecast origin versus target dates, sample endpoints, target aggregation and estimation/tuning cadence.
- [ ] Lock reference hyperparameters, random seeds and implementation/library versions.
- [ ] Audit factors, state predictors and target lags for information timing at every origin.
- [ ] Run the linear benchmark and reference MRF without Jev; retain forecasts and coefficient decompositions.
- [ ] Compare reproduced cells using a tolerance fixed before inspecting differences; explain unresolved discrepancies.
- [ ] Build genuinely prequential development cases for the new policy, then freeze its prompt and candidate construction.

Working-paper dates and lag orders in the protocol are provisional anchors. The verified archive filenames and hashes are actual observations from this inspection. Keeping that distinction is necessary for a faithful replication.
