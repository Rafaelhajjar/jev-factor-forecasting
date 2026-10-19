# Initial experiment status

Verified October 18, 2026. This is an untuned development run, not a confirmatory result. Both supplied configurations completed with zero hosted-model API calls. The source revision is recorded in the run manifests. All 32 tests passed, including future-data perturbation checks and real SDK serialization/parsing using local fake transports.

## Synthetic changing-loadings experiment

Three fixed seeds, 60 forecast origins per seed, 180 forecasts per method. The observed-signal representation uses the four supplied signals; extra noisy measurements are available to multivariate ridge and trees. This setup intentionally makes a changing-coefficient model plausible.

| Method | RMSE |
| --- | ---: |
| Random-walk coefficient Kalman | 1.543567 |
| Exponentially weighted factor ridge | 1.707400 |
| Diagnostic rule gate | 1.858059 |
| Online learned gate | 1.932331 |
| Target-history AR ridge | 1.933577 |
| Expanding factor ridge | 1.935911 |
| Multivariate ridge | 1.949570 |
| Gradient-boosted trees | 2.055984 |
| Rolling factor ridge | 2.113304 |
| Persistence | 2.114738 |
| Zero | 3.197403 |

The Kalman baseline has about 20.3% lower pooled RMSE than the expanding factor regression. This is a descriptive result without a paired uncertainty interval. It demonstrates that an adaptive conventional model is a serious comparator. It does not demonstrate that Jev adds value. The learned gate begins cold and only trains as past evaluated cases mature.

## FRED-MD development experiment

Pinned September 2026 vintage; transformed INDPRO target; one-month point horizon; one-month availability lag; four PCA factors; 60 origins, every three months from January 2010 through October 2024. Predictions target the following month. Data are revised historical values, not a reconstruction of information available at each date.

| Method | RMSE, log-growth units |
| --- | ---: |
| Zero growth | 0.006872 |
| Gradient-boosted trees | 0.007572 |
| AR ridge | 0.008680 |
| Diagnostic rule gate | 0.009718 |
| Online learned gate | 0.009782 |
| Exponentially weighted factor ridge | 0.009783 |
| Expanding factor ridge | 0.010116 |
| Rolling factor ridge | 0.012119 |
| Persistence | 0.013522 |
| Multivariate ridge | 0.014474 |
| Random-walk coefficient Kalman | 0.023389 |

The zero-growth baseline is best in this configuration. This pilot **does not establish a factor forecasting advantage on this target/horizon**. FRED-MD remains a literature-motivated research candidate rather than a validated favorable benchmark for our exact setup.

The next dataset decision should follow the literature's longer-horizon aggregate-growth specifications, chronological validation, and historical vintages. Any such change after seeing these results is exploratory and must be reported as such. Do not silently replace this run with a better-looking one. The large Kalman error also warrants development-period tuning of Q/R and regularization, with no access to the final evaluation losses during selection.

## Hosted models

Jev and LLM forecasts have not been run because their API credentials were unavailable. The adapters passed local contract tests, but actual service access, numerical calibration, latency, cost, and forecasting quality remain unverified. There are no Jev/LLM scores in the tables and no mock results presented as real model results.

## Reproduction

```bash
uv sync --frozen --extra api
uv run --frozen --extra api pytest
uv run jev-factor download-fred
uv run jev-factor run --config configs/synthetic.json --output runs/synthetic-baseline
uv run jev-factor run --config configs/fred_md.json --output runs/fred-baseline
```

Published CSV summaries preserve all methods, per-seed metrics, exact configurations, and manifests. Shared preprocessing is excluded from the model timing column. Timings are local measurements and are not valid hosted-model latency comparisons. Raw FRED data, decision states and API caches stay local. No significance or universal ranking is claimed.
