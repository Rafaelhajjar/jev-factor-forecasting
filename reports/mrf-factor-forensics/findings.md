# Why does our MRF miss the crisis? Factor and preprocessing forensics

The strongest localized finding is a factor-definition problem worth investigating,
not a proven recovery of the original paper. The original benchmark is unchanged.

## What we found

At the 2008Q4 predictor observation used for the 2009Q1 forecast, our all-247 F2 is
+1.359 training SDs. A PCA-only change to the
historical 125-series subset gives -0.800
training SDs after aligning signs on training data. The training correlation is
0.944. This is not a cosmetic PCA sign flip:
the rare crisis observation differs substantially despite high ordinary correlation.

Under the original all-247 loadings, the 125-subset columns contribute
-1.007 to the raw F2 score, while the
122 other columns contribute +7.715.
Deflation/real-money movements offset housing and equity signals in this factor.
The membership grouping uses the vintage's actual flags; metadata descriptions
are exact-name matches from a separately dated official appendix, with unknown
names explicitly labeled rather than guessed.

Cleaning removes 10 observed extremes at this origin, replacing them
with low-rank estimates. Keeping future extremes but fixing all training values,
moments and loadings gives an F2 reading of
+2.756 training SDs.
This isolates future screening; the no-cleaning refit is a different experiment.
See the comparison plots rather than assuming cleaning caused the factor direction.

There is also a learned-map issue. In the original seed-101 crisis forecast, F1
contributes 6.132 log points, versus 11.410 for the same-equation static
OLS. The forest's lower F1 contribution outweighs its helpful intercept change.
F2 input construction and dynamic coefficient fitting therefore need to be
distinguished; changing a factor does not automatically repair the model.

## Factor-estimation timing is another live hypothesis

The explicitly NONCAUSAL control fits cleaning, completion and PCA using the
entire September-vintage history through 2018Q2. It retains all 247 series,
but changes the 2008Q4 F2 reading to
-0.964 pre-cutoff training
SDs, with training correlation
0.970 to the original F2.
Thus subset selection is not the only way to reverse this tail reading.
Factor-estimation timing can matter even with the full indicator panel.

The PCA-only full-vintage control on frozen old moments/completion has only
0.227 training correlation for
component 2, so its nominal F2 is not a close match to the original factor.
Do not interpret that comparison as a mere rescaling of one economic quantity.
No future-informed factor is adopted as a deployable benchmark, and no claim
is made that the paper used future data. The original caller is still missing.

The FRED-QD reference paper (McCracken and Ng, 2021, Section 3) explicitly
compares 125-series subset factors with factors using all series and observations;
it describes F2 as forward-looking in both. Consequently, the MRF paper's
economic label does not establish which eligibility or fitting window it used.
This reinforces the need to check the author's actual preparation rather than
choose whichever variant gives an attractive crisis reading.

## What passed

- All six frozen state matrices rebuild, without replacing them.
- All 247 raw transformations and missingness masks agree with independent base R.
- Crisis-window 10-IQR masks and thresholds agree with independent base R.
- All six sets of 247 MAF scores agree with independent covariance eigensystems.
- Crisis-window all-series and subset PCA scores/loadings agree with base R up to signs.
- All 247 crisis-window MAF loading pairs agree with base R up to signs.
- Source-recipe adaptive completion is independently checked in R for both panels.
- The original 2008Q4/seed-101/100-tree fit is replayed with storage only. Every
  saved forecast and coefficient matches; routed leaf partitions and coefficient
  accounting verify.

Maximum transformation discrepancy: 4.95e-10.
Maximum transformation discrepancy divided by max(1, absolute value):
4.78e-15; absolute errors are
largest on the federal-debt difference measured in large native units.
Maximum all-panel PCA score discrepancy: 7.11e-14.
Maximum R/Python MAF loading discrepancy: 6.62e-14.

Passing these checks establishes our arithmetic and the saved-input contract,
not the paper's original factor inputs or runner. PC2/PC3 are not nearly tied
in this training sample, weakening a simple numerical component-swap explanation.
Up-to-sign PCA agreement does not establish forecast invariance to signs in
this particular forest engine; the earlier basis audit documented that separate
source behavior. Here, comparison signs are fixed using training correlations.

## What this does not establish

We have not obtained the author's original factor series or preprocessing caller.
The historical 125 flags describe a Stock-Watson subset; they do not prove the
MRF paper selected that subset. The reference paper's economic labels cannot
be used to choose a convenient PCA or sign pattern after seeing test errors.
No new variant forest or alternative forecast-loss table is produced here.
All nine preparations are source-motivated, post-hoc diagnostic comparisons.
The two explicitly NONCAUSAL full-vintage controls use later predictor values,
including the UNRATE panel series, through 2018Q2. They are not fair benchmark
candidates or evidence that the original author used future data.
All-panel adaptive completion reaches the source's 50-iteration cap in the
2004Q4 and 2008Q4 refits; the 125-series versions converge. Capped outputs
are exposed as such, not presented as converged alternatives or used for forecasts.
The last-observed-origin variant uses already-known covariates, not future
unemployment labels. Signs and scaling use training observations only.

Next decisive check: obtain/identify the author's actual factor-construction
rule, or declare a separate factor-only forecast comparison with all other
state columns and forest settings frozen, its own matched static comparator,
and no promotion to an exact replication based on a favorable test score.
Independent confirmation would require data not used for this investigation.

[Open the ten-figure report](index.html), [audit](audit.json),
[factor snapshot](crisis-factor-snapshot.csv), [all factor scores](factor-variant-scores.csv),
[outlier cells](outlier-cells.csv), [F2 drivers](factor-drivers.csv),
[routed crisis leaves](crisis-routed-leaves.csv), [historical leaf support](crisis-leaf-support.csv).

Reproduce from the repository with:

```sh
uv run --frozen --extra plots python -m jev_factor.factor_forensics2018 audit
# First create the storage-only 2008Q4/seed-101 replay using scripts/trace_mrf2018.R
# and the corresponding frozen matrix/settings, writing to runs/mrf-factor-forensics/crisis-replay/replay.csv.
uv run --frozen --extra plots python -m jev_factor.factor_forensics2018 replay-audit
uv run --frozen --extra plots python -m jev_factor.factor_forensics2018 report
```

Sources: [paper](https://doi.org/10.1002/jae.3030),
[FRED-QD reference paper](https://www.stlouisfed.org/-/media/project/frbstl/stlouisfed/publications/review/pdfs/2021/01/14/fred-qd-a-quarterly-database-for-macroeconomic-research.pdf),
[FRED databases/code](https://www.stlouisfed.org/research/economists/mccracken/fred-databases),
[pinned author engine](https://github.com/philgoucou/macrorf/blob/bdb2ed435affb741aafdf78bab12c470ec6d55d0/R/MRF_v210403.R).
No Jev/LLM evaluation, parameter search, original-result replacement or outgoing messages.
