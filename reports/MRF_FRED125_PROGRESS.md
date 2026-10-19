# FRED125 preparation and pilot: verified, full forecasts pending

October 19, 2026. This is an integrity/progress record, not a forecast result. The joint unemployment replication remains incomplete.

The [declaration and runner](../docs/FRED125_SENSITIVITY.md) were committed and pushed in `dbd43380e6401c8810b2b9294b9508fc4330416d` before this construction's actual-R pilot or full outcomes. Prior primary, ARRF, R-sign and conditional PCA125 results were already known and are recorded in its [configuration](../configs/mrf_fred125_sensitivity.json).

## What is verified

The full preparation reconstructs all six fitting windows and all 18 seed/refit jobs, using the checked FRED recipe on independently completed 125-series panels. It replaces only the 40 factor-lag columns and preserves every original non-factor entry, including the full indicator/MAF state and masked target values. The original primary artifact audit and independent-R FRED completion audit both repeat successfully.

The [preparation audit](mrf-fred125-preparation-audit.json) verifies all six complete matrices and independent linear fits, with maximum Python/R discrepancy below 1.5e-15. AR(4) is unchanged within 9.4e-17. Its zero completed forest jobs and 18 pending jobs describe the **pre-fit snapshot**, not live run status. Its manifest hash binds the prepared manifest and will not represent a later completed manifest.

The separate [actual-R pilot audit](mrf-fred125-pilot-audit.json) verifies two trees, seed 101, the 2002Q4 refit and eight forecast dates. Saved coefficients reproduce forecasts within 3.1e-16. It uses R 4.6.1 and pracma 2.4.6 with the pinned external author engine. This tests integration, not macro forecasting accuracy; pilot scores are deliberately withheld.

All 245 local tests pass, including 12 real-R contracts. The declaration commit's [GitHub checks also passed](https://github.com/Rafaelhajjar/jev-factor-forecasting/actions/runs/39231403760). The new synthetic contracts exercise exact non-factor preservation, timing, convergence/cap rejection, recipe/provenance guards, preparation-only behavior and the joint criterion. Synthetic contract scores are never research evidence. CI tests and the bounded smoke are not substitutes for the expensive full macro comparison.

## What is running and what remains

The separately prepared 100-tree run has been launched with all three original seeds, all six refits and all 48 evaluation dates. The runner's source and dependencies are frozen. Partial runs publish integrity checks only; full scores and source comparisons remain pending until every job completes and the final independent audit passes.

The final report must compare the new forest to its **own** fixed-factor comparator, retaining every seed and a separately labeled mean-prediction ensemble. The matching fixed-factor ratio must be within 0.03 of 0.83 and every individual forest ratio within 0.03 of 0.72. Do not combine an earlier linear score with a new forest or choose the best seed.

This is a composite preparation contrast, not a pure rank toggle. The monthly FRED functions and our causal future-row completion do not identify the missing quarterly author pipeline. No primary or earlier sensitivity output is replaced, and no Jev or LLM call is made. A completed forecast program alone cannot establish exact replication.
