# Native normalization also changes the OLS-prior intercept

Checked October 19, 2026, after the completed benchmark runs. This is an **initialization-only source diagnostic**, not a forecast experiment or a new preferred configuration. Twelve actual native initializations cover both scaling modes at all six original refits. No tree is fitted, no new forecast score is calculated, and every earlier result remains unchanged.

## What is the difference?

The [pinned author engine](https://github.com/philgoucou/macrorf/blob/bdb2ed435affb741aafdf78bab12c470ec6d55d0/R/MRF_v210403.R#L393-L400) scales all supplied rows, including the eight forecast rows. Our primary adapter deliberately overrides that helper with training-only moments. Both modes first apply the same outer training-only standardization and mask every future target; this diagnostic changes only the helper selection, in memory, inside an isolated process.

There is a second interaction. If the incoming equation prior has intercept a and slopes b, the correctly transformed intercept is:

```text
a_scaled = (a - mean_y + mean_X' b) / SD_y
```

The pinned function first rescales b and then uses those already-rescaled slopes in this intercept calculation. With approximately zero inner training means and unit SDs, as in our primary adapter, the distinction is negligible. With native all-row moments, the prior intercept no longer equals the OLS prior of the normalized training equation. Its slopes still agree. This is a verified algebraic boundary, not proof of the original author's table invocation or intent.

| Refit end | Native maximum state inner-SD difference from 1 | Native prior intercept minus normalized OLS |
| --- | ---: | ---: |
| 2002Q4 | 0.169649 | -0.000153757 |
| 2004Q4 | 0.326332 | -0.000023344 |
| 2006Q4 | 0.454861 | +0.000878671 |
| 2008Q4 | 0.746202 | +0.005296086 |
| 2010Q4 | 0.225745 | -0.000048938 |
| 2012Q4 | 0.349147 | -0.000128010 |

The intercept offsets are in the **native standardized target units**, not unemployment levels or forecast errors. Training-only source priors agree with normalized OLS within 3.4e-16. Replaying the literal source formula matches every captured prior; the mathematically correct transformation agrees with independent R QR OLS within 1.4e-15. Independent NumPy checks of all 1,042 centering/SD values and each equation prior agree within 5.4e-15 across all twelve cases.

## What does this establish?

Native all-row mode is not merely a harmless unit change, nor a clean test of normalization alone: ridge scaling and this prior conversion interact. It also uses covariates from later origins within the eight-quarter block. We do not assume those were available at the first origin, expose actual future outcomes, adopt this as the causal baseline, or silently repair the author source. No conclusion about the effect on forest accuracy follows without a separately declared forecast diagnostic. It does not explain the 0.72 source gap by itself.

The [numeric record](../reports/mrf-native-normalization-boundary.json) binds the unchanged primary manifest, every matrix/settings checksum, actual engine/adapter/probe checksums, captured priors and independent numerical discrepancies. The [CSV](../reports/mrf-native-normalization-boundary.csv) retains all twelve summaries. It is a boundary snapshot, not a forecast artifact audit or successful replication.

The [standalone R probe](../scripts/inspect_native_normalization.R) reuses the existing actual-adapter/native instrumentation and stops before noise injection or split search. It preserves all on-disk source/settings/input files and rejects existing output directories. Run it on one saved matrix as follows; repeat the two modes across the six refit directories to rebuild the check:

~~~bash
Rscript --vanilla scripts/inspect_native_normalization.R \
  data/raw/MRF_v210403.R \
  runs/mrf-unemployment/refit_00_2002Q4/masked_matrix.csv \
  runs/mrf-unemployment/refit_00_2002Q4/settings_seed_101.dcf \
  runs/r-library . runs/my-normalization-train train_only
# Use a fresh directory and native_all_supplied_rows for the other mode.
~~~

Three additional actual-R contracts check both modes, future-target masking, source/settings preservation, intercept-versus-slope behavior, no-overwrite and unsupported-mode rejection. The original source/caller and main numerical-gain questions remain open. No Jev, LLM or hosted forecasting call occurs.
