# What the published appendix changes

Read October 18, 2026. This note records evidence from the final article and its [publisher-supplied appendix](https://onlinelibrary.wiley.com/doi/suppl/10.1002/jae.3030/supinfo/jae3030-sup-0001-Appendix.pdf), not results produced by this project. Both PDFs were read; the settings and results tables were also visually checked. The PDFs stay outside the public repository.

The appendix PDF has 32 pages, printed pages 40–71. Its internal labels are `Table 3`, `Table 4`, `Table 5` and `Figures 10–29`; the published article sometimes refers to appendix items using A-prefixed numbers. Use section, PDF page and visible caption together when locating a result.

Appendix SHA-256: `665fac2b6a21b8f2b28442dfe60aec30aee542c3dac2876b322f4e249718fb1b`.

## 1. A concrete first replication target

Appendix Table 4, PDF page 31, printed page 70, reports these quarterly unemployment results at horizon one. Values are **RMSE divided by AR(4) RMSE**, rounded to two decimals, not absolute errors or Jev results.

| Model | Reported ratio |
| --- | ---: |
| AR(4), reference denominator | 1.00 |
| Fixed factor-augmented AR | 0.83 |
| Plain RF | 1.00 |
| RF with moving-average factors | 0.85 |
| AR followed by residual RF | 0.84 |
| Factor-augmented MRF (FA-ARRF) | 0.72 |
| Autoregressive MRF (ARRF) | 0.90 |
| Time-varying factor AR (TV-FAAR) | 1.19 |
| Neural network | 0.80 |

This fixes the first comparison cells. It also sets a demanding reference: the reported FA-ARRF gain over AR(4) is about 28%; our question is whether Jev adds anything **beyond FA-ARRF**, not whether it can recover that original gain. Do not infer significance from the size of a ratio or copy published significance stars onto new results.

The forest is not universally best. Table 4 reports TV-FAAR at 0.78 versus FA-ARRF at 0.89 for unemployment six quarters ahead, and NN at 0.88 versus FA-ARRF at 0.97 for GDP two quarters ahead. These become predeclared secondary comparisons against strong conventional competitors, not reasons to change the primary target after Jev runs.

## 2. The forest settings are clearer, but not fully specified

Appendix A.4 and A.6, PDF pages 14 and 16–18, establish:

| Setting | What the appendix actually says |
| --- | --- |
| RF hyperparameter tuning | Main reported RFs were not tuned; a separate reduced exercise investigated tuning |
| Resampling | Block subsampling; 75% subsampling rate |
| Block length | Two years: 8 quarterly or 24 monthly observations |
| Minimum parent node size | 10 quarterly, 15 monthly |
| Ridge prior mean | OLS coefficients |
| `mtry` | Discusses 1/3 as the suggested regression fraction and sensitivity to alternatives; exact paper invocation still needs a code check |
| Tree count | About 100 usually sufficient for a mean forecast; 200–300 suggested for stable tree-dispersion bands; not a declaration of the exact count in every reported run |
| RWR, RL, MLF and trend push | Meanings explained, but exact settings for each reported model still require reference-code verification |

The replication must preserve the untuned reference rather than search for forest settings that make its printed score look better. Any tuned competitor is a separately named model. Main-text two-year re-estimation changes the estimation sample; it does not mean that RF hyperparameters were re-tuned every two years.

The forest's two-year training blocks are **not automatically the right block length for our paired forecast-loss bootstrap**. That inference choice must be selected and frozen separately using development data.

## 3. Use the appendix's data-rich mechanism tests

Appendix A.2 and Table 3, PDF pages 8, 11–12 and 18, are closer to our question than a generic switching-series demo.

Two observed regressors, X1 and X2, enter a small linear equation. Separately, two autocorrelated latent state drivers generate 100 noisy state series: 50 measurements per driver. One driver governs some coefficient changes; the other is irrelevant. These state drivers must not be confused with the two regressors in the forecasting equation. Target lags and time are added to the state. The stated signal-to-noise ratio is 2/3.

| DGP | Intercept | X1 coefficient | X2 coefficient | Residual variance |
| --- | --- | --- | --- | --- |
| 1 | Switching | Switching | Switching | Constant |
| 2 | Constant | Random walk | Random walk | Constant |
| 3 | Constant | Latent driver directly | Slow time change | Constant |
| 4 | Constant | Switching | Slow time change | Constant |
| 5 | Constant | Switching | Structural break | Constant |
| 6 | Constant | Constant | Constant | Stochastic volatility |

DGP 6 is particularly important: changing noise should not be mistaken for changing factor relevance. Random walks and breaks test limits rather than guarantee that an unannounced future change can be anticipated.

Keep two tracks distinct:

1. **Source replication:** recover the author's actual generator, conditioning convention and sample lengths before claiming to reproduce Figure 15.
2. **Our controlled extension:** explicitly use 1,000 observations per path, 400 initial fitting observations, 200 chronological development observations and 400 locked test observations. Plan 50 predeclared simulation seeds for numerical controls. Freeze an identical, budgeted subset of test origins/seeds for Jev and the LLM before hosted evaluation. This extra development split is our design, not the paper's.

Add zero-coefficient and sign-reversal stress tests as our own cases. The initial nonnegative multiplier menu cannot revive an exactly zero contribution or reverse its sign. Report that limitation, not a supposed failure of the underlying decision model alone.

## 4. Strengthen the benchmark set

A.2 compares MRF with OLS, rolling OLS, plain RF, PCA-interaction OLS, Lasso interactions, NN and a **macro neural network (MNN)**. MNN uses a small linear equation with neural time-varying coefficients, making it a useful architectural comparator; it is not an LLM.

The stated neural settings are batch size 32, Adam, standardized continuous inputs, learning rate 0.001, at most 100 epochs, early stopping on the omitted 15%, and an average of 10 fits with 85% subsampling. NN has five hidden layers of 100 ReLU units. MNN has four 100-unit layers followed by five neurons attached to each coefficient. Audit the meaning of that final attachment and the ensemble/validation implementation before coding it. Main Table 2 points to A.2 for the real-data NN architecture; a new MNN real-data benchmark would be our extension.

Preserve these reference settings in the reproduction track. For our new selector training, use chronological development validation. Do not label an altered validation scheme an exact reproduction.

The main selector experiment additionally needs a constant bounded-multiplier control, a transparent rule, a classification-trained selector and a loss-trained selector. Constant mixtures must be allowed, not only a single grid action: Jev's probability average can produce mean multipliers between grid points. This prevents ordinary constant recalibration being misrepresented as dynamic judgment.

## 5. Monthly inflation is a defined secondary task

A.7, PDF pages 17 and 19–20, uses FRED-MD and horizons 1, 3, 9, 12 and 24 months. The target is **average transformed growth over the next h months**, not the single monthly outcome at t+h. In particular, 12-month inflation means the average monthly inflation over the next year; unit scaling and the transformation must be matched before any conversion to annualized inflation.

Prespecify monthly CPI inflation at h=12 as the first monthly extension. Table 5, PDF page 32, reports FA-ARRF 0.67, ARRF 0.73, Tiny ARRF 0.67, RF-MAF 0.79, and FAAR 1.21 relative to its stated reference denominator. At h=24, Tiny ARRF is 0.55 while FA-ARRF is 0.69: the factor-augmented version is not always the best MRF variant. Retain the no-factor and simple inflation benchmarks, including the Atkeson–Ohanian-style moving averages, rather than compare only to a weak fixed factor model.

This is an overlapping-horizon task. Training outcomes become usable only after the entire future window is observed and available, and adjacent forecast losses are not independent.

## 6. Interpretation and structural change

- A.5 distinguishes out-of-bag VI, held-out OOS VI, and coefficient-specific VI. The published OOS VI and surrogate trees are retrospective explanations. They cannot select Jev's inputs or write its state cards at historical forecast dates. Recompute any selection using only past development data.
- Small surrogate trees are suggestive and unstable; don't turn their cutoffs into timeless economic laws. Group-level summaries and perturbation checks are more defensible than asserting one named indicator is the cause.
- A.7.1 compares coefficient maps fitted through 1995, 2007 and 2019. It shows why cyclical state dependence and changes to the mapping itself are different. Our robustness study therefore separates a frozen coefficient map, periodic re-estimation, and a rule using matured forecast errors. No method is expected to anticipate an independent, unobserved structural break.
- Tree dispersion, Jev action probabilities, and target predictive uncertainty are three different objects. None can be relabeled as the others without a separately validated construction.

## 7. Remaining discrepancies to resolve

| Issue | Evidence | Required action |
| --- | --- | --- |
| Target count | Main Section 3 names five quarterly targets; Table 4 also contains HOUST, giving six target groups | Keep five named targets as the core matrix and record HOUST as an additional audit row; verify its transformation before adding it |
| Monthly denominator | A.7 describes AR(12), while Table 5's note says AR(4) and a separate AR4 column is not identically 1 | Identify the actual denominator in the reference pipeline; store source ratios without silently renormalizing |
| Monthly series count | A.7 describes 134 indicators; the deposited file's effective eligible panel still needs reconciliation | Audit archive columns, transformations, missingness and factor eligibility |
| A.2 sample lengths | Prose says 1,000 total / 400 fitted / 600 OOS; Figure 15 caption says 50 simulations with 750 OOS forecasts | Resolve against generator/reference code; do not report either as an achieved replication |
| Exact neural/forest settings | Some are recommendations, descriptions or defaults, not per-result invocations | Record effective parameters and source revision for every replicated cell |
| TV-FAAR timing | Published Table 2 has a footnote mentioning a single 2007Q2 estimate, whereas Section 3 describes two-year re-estimation and interpretation figures use a different setup | Separate forecast tables from coefficient-anatomy experiments; verify the actual TV-FAAR table schedule |

The subsequent [author-code audit](AUTHOR_CODE_AUDIT.md) establishes engine defaults and interface behavior, and the quarterly loader/adapter are now implemented. The inspected public repositories contain no paper runner or simulation generator, so the discrepancies above cannot all be resolved from that engine. The full unemployment reconstruction is running under explicitly declared assumptions. Exact numerical reproduction remains a gate in the [updated protocol](RESEARCH_PROTOCOL.md); source reading or successful execution alone does not satisfy it.
