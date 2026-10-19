# Sources and evidence boundaries

Reviewed October 18, 2026. Links below are primary vendor documentation, the dataset publisher, or original research. Public source material is cited, not copied wholesale.

| Source | What it supports | What it does not establish |
| --- | --- | --- |
| [TypeSafe launch post](https://typesafe.ai/blog/introducing-system-one-models-and-jev) | Vendor description of architecture, parallel outputs, RLCD and workflow evaluations | Independent forecasting performance, full architecture, or reproducible training |
| [Introduction](https://docs.typesafe.ai/introduction) | State plus typed independent questions; Choice/Score/Noul | Hidden factor inference or numerical correlation estimation |
| [AI primer](https://docs.typesafe.ai/introduction/machine-learning-primer) | Vendor's intended calibration objective | A public mathematical specification of the full loss or training recipe |
| [Models](https://docs.typesafe.ai/models) | Versioned IDs, model configuration and request-level customization | Task-specific fine-tuning or stable behavior of moving aliases |
| [1.13 limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13) | Numerical/semantic limitations and order sensitivity | That every limitation has disappeared in later versions |
| [Choice](https://docs.typesafe.ai/primitives/choice), [API](https://docs.typesafe.ai/api), [confidence](https://docs.typesafe.ai/confidence) | Request/response contract and confidence derived from probabilities | Calibration on our financial/economic outcomes or a coefficient posterior |
| [Autoresearch cookbook](https://docs.typesafe.ai/cookbooks/autoresearch_feature_discovery) | A related design: use TypeSafe outputs as inputs to a conventional supervised model | Evidence for this time-series gating hypothesis |
| [Official LLM adapter](https://github.com/typesafe-ai/system-one-adapter-python) | A common typed-task interface for comparisons with LLM providers | Equal latency, equal reasoning budgets, or equal accuracy |
| [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) | An LLM can be constrained by JSON Schema | Probability calibration or forecast accuracy |
| [FRED-MD publisher](https://www.stlouisfed.org/research/economists/mccracken/fred-databases) | Official monthly macroeconomic panel and archived vintages | That a fixed revised vintage is a historical real-time information set |
| [McCracken and Ng, FRED-MD](https://doi.org/10.20955/wp.2015.012) | Dataset motivation and relationship to factor forecasting research | Universal superiority for every target, period, or transformation |
| [Stock and Watson, 2002](https://www.princeton.edu/~mwatson/papers/Stock_Watson_JBES_2002.pdf) | Historical evidence motivating large-panel factor forecasting | A result for this newer panel, sample, horizon, or Jev |
| [Raftery, Karny and Ettler, 2010](https://sites.stat.washington.edu/raftery/Research/PDF/Karny2010.pdf) | Dynamic model averaging as an established adaptive forecast framework | That typed decision models improve its predictions |
| [Koop and Korobilis, 2012](https://eprints.gla.ac.uk/59746/) | An original macroeconomic forecasting application of dynamic model averaging | That our proposed gate or first INDPRO setup reproduces their results |

## Interpretation

The new contribution under investigation is using a general typed decision model as a factor gate with observable action labels. Factor models, changing coefficients, probabilistic forecast combinations, and language-based model selection are established ideas. Novelty is not assumed; a broader literature review is required before claiming a first result.

Jev's published workflow evaluations do not replace a forecasting backtest against realized outcomes. Vendor cost/speed claims are not copied into our results table. All hypotheses about transfer to time-series prediction are ours, not established properties of Jev.

## Data provenance

Pinned file: [September 2026 FRED-MD](https://www.stlouisfed.org/-/media/project/frbstl/stlouisfed/research/fred-md/monthly/2026-09-md.csv).

```text
SHA-256 d6e239038afbdbf4667c2a63c13c942817bc196fedab4355cd7e0d353ecdd65d
```

Download verifies this digest and the transform row. Raw observations are not committed. The repository's MIT license applies to its code, not upstream data or hosted-model access. Review upstream series terms before redistributing data.
