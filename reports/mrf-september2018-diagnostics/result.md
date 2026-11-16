# Qualified September 2018 MRF: completed and audited

All 18 native fits (100 trees each), six refits and 48 target quarters are verified.
This is a qualified reconstruction, not a recovered original author pipeline.
The earlier plain-RF source-cell criterion remains failed; the user authorized
advancing with that limitation. The served archive has 247 series, not the original 248.

## Results

| Model | RMSE | RMSE / AR(4) |
| --- | ---: | ---: |
| AR4 | 0.0335022029 | 1.000000 |
| FA_AR | 0.0279188616 | 0.833344 |
| FA_ARRF_seed101 | 0.0285599278 | 0.852479 |
| FA_ARRF_seed202 | 0.0277706877 | 0.828921 |
| FA_ARRF_seed303 | 0.0275980952 | 0.823770 |

Joint source-cell diagnostic: **fails**.
It requires the matching fixed FA-AR within 0.03 of 0.83 and every individual
MRF seed within 0.03 of 0.72. This is a project diagnostic, not a statistical test.
A numerical match would not establish exact replication. No ensemble rescues a miss.

MRF RMSE reductions versus its own matching fixed FA-AR:

- Seed 101: -2.296%.
- Seed 202: 0.531%.
- Seed 303: 1.149%.

## What is checked?

States are rebuilt from the checksum-pinned archive and paired with the frozen
RF preprocessing/calendar. The AR denominator is unchanged from that RF run.
Independent base-R QR checks the linear forecasts. Native coefficients are finite
and reconstruct every forecast; all completed outputs and runtimes are bound.
This is not an independent refit of every full native tree.

[Audit record](audit.json), [predictions](predictions.csv), [metrics](metrics.csv).

No Jev/LLM forecasts were made. Earlier results and failure flags remain unchanged.
Original preprocessing, factor orientation, settings and runtime remain qualified.
