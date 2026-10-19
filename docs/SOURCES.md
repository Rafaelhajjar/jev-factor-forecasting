# Sources for the MRF + Jev extension

Reviewed October 18, 2026. The [active protocol](RESEARCH_PROTOCOL.md) separates the source paper's method from our proposed extension. The [legacy source notes](LEGACY_SOURCES.md) preserve the initial scaffold's references.

## Research foundation

| Primary source | Use in this project | Evidence boundary |
| --- | --- | --- |
| [Goulet Coulombe (2024), JAE](https://doi.org/10.1002/jae.3030) | Main research foundation: forest-driven changing coefficients | Its results do not establish a Jev advantage |
| [Accessible working paper](https://arxiv.org/pdf/2006.12724) | Provisional model, factor and timing details for the replication audit | It is an earlier draft; reconcile the published version before claiming reproduction |
| [Journal data archive](https://doi.org/10.15456/jae.2023321.0115060814) | Exact deposited data and provenance | Archive contains data, not the entire experiment pipeline or historical release vintages |
| [Author's R package](https://github.com/philgoucou/macrorf) | Candidate reference MRF implementation | Exact paper settings and result reproduction remain to be checked |
| [Python implementation documentation](https://mrf-web.readthedocs.io/en/latest/) | Portability comparison and implementation guidance | Do not assume identical predictions to the R reference |

The archive's [README](https://journaldata.zbw.eu/dataset/c48432e1-5a25-49f1-95b1-6c681f21e252/resource/57da9dba-6157-4e56-838a-f57358854ca7/download/readme.gc.txt) and the downloaded ZIP were inspected directly. File identities, checksums and parsing findings are recorded in [MRF_REPLICATION.md](MRF_REPLICATION.md). These are verified inputs; model replication remains pending.

## Jev interface and comparison

| Primary source | Use | Evidence boundary |
| --- | --- | --- |
| [Choice documentation](https://docs.typesafe.ai/primitives/choice) | Bounded options with probabilities; the documented option limit accommodates our 25 candidates | A valid output does not mean numerical judgment or calibration transfers to macroeconomic forecasts |
| [Jev 1.13 limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13) | Keep arithmetic in code and test order sensitivity | We must evaluate the proposed joint task rather than assuming it is easy for Jev |
| [Confidence documentation](https://docs.typesafe.ai/confidence) | Confidence is derived from an answer distribution | Do not treat it as independent correctness evidence or forecast-interval coverage |
| [Models](https://docs.typesafe.ai/models) | Pin a version and retain the responding model ID | No fine-tuning, hosted access or forecasting capability is implied by this plan |
| [Official LLM adapter](https://github.com/typesafe-ai/system-one-adapter-python) | Matched typed-task LLM control | Model settings, representations, latency and costs still need measurement |

RLCD and other vendor training descriptions remain context, not evidence that the method works here. The five-level adjustment grid, joint action distribution, uniform-recovery control and all claimed benefits of adding Jev are our research proposals.

## Attribution and data handling

Our code license does not replace upstream licenses. Keep external implementations distinct and honor their terms. In particular, the inspected author R package declares GPL-3; it must not be copied into this repository and relabeled MIT. Data reuse and distribution retain the archive's attribution and applicable series terms.

The earlier September 2026 FRED-MD snapshot and its checksum belong to the old monthly pilot. They are not substitutes for the paper's deposited data.
