# Does another public reconstruction resolve the unemployment gap?

Checked October 19, 2026. **No: the inspected reconstruction does not match our two required unemployment cells and is not the missing author caller.** Its existence is useful context, not a reason to weaken the criterion or change the live experiment.

The author's [code page](https://philippegouletcoulombe.com/code) still links the generic R/Python engines and offers raw code by email. A bounded search also found NanyeonK's independent macroforecast package. We inspected its complete quarterly driver at commit **3c193e24a10ac1fa92fc65f92fe493e654e1508a**, without importing it or running its models.

## Inputs and reported result

Its [driver](https://github.com/NanyeonK/macroforecast/blob/3c193e24a10ac1fa92fc65f92fe493e654e1508a/scripts/replication/mrf_2024_pipeline/run_table4.py) loads the 2020-01 vintage, sets 50 trees/block parameter 12/seed 42, and requires an external feature cache. These differ from our deposited vintage and frozen settings. The exact cached features were not recovered or verified in this audit.

Its [checked-in scalar results](https://github.com/NanyeonK/macroforecast/blob/3c193e24a10ac1fa92fc65f92fe493e654e1508a/scripts/replication/mrf_2024_pipeline/results/g2_UR.json) report h=1 FA-AR = **0.924** versus 0.83 and FA-ARRF = **0.872** versus 0.72. Both miss our existing 0.03 tolerance. These are their reported, rounded numbers—not independently rescored forecasts. Different data/settings prevent interpreting this as an apples-to-apples contest with our implementation.

## Timing boundary

The inspected driver pairs target lags with a forward-shifted label. On a complete quarterly grid, its row 2003Q1 has latest target-history predictor 2002Q4 and h=1 label 2003Q2. Our locked first case instead forecasts target 2003Q1 from origin 2002Q4. This illustrates a different alignment; missing cached inputs prevent verifying the external run's actual scored-date coverage. It does not establish the author's unknown original indexing or prove ours correct by comparison.

Separately, a fresh full-page/visual check of the [final article](https://doi.org/10.1002/jae.3030), Section 3 on printed page 408 (PDF page 8), confirms that its RMSE sums over target dates t in OOS, comparing y(t) with the forecast made at t-h. Table 2 on printed page 409 uses lag-one/lag-two target terms for FA-ARRF. This is primary-source support for our locked target-date interpretation of the stated evaluation window, not merely a convention inferred from another package. It does not authenticate the missing original caller or explain the score gap; the source formula is not a recovered executable script.

The [static audit record](../reports/mrf-independent-driver-source-audit.json) records the pinned files/checksums, literal settings, source-line locations, reported scalar discrepancies and explicitly conditional date illustration. No external model was executed, no code was copied into our package, no raw forecast result was reproduced, and neither our baseline nor the live native-helper run changed. A broad qualitative replication label is not proof that this particular benchmark has been recovered.
