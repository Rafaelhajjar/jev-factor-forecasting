# Sources for the MRF + Jev extension

Reviewed October 18–19, 2026, after reading the final article and its publisher-supplied appendix. The [active protocol](RESEARCH_PROTOCOL.md) separates the source paper's method from our proposed extension. The [appendix evidence note](APPENDIX_FINDINGS.md) records exact source locations and remaining discrepancies. The [legacy source notes](LEGACY_SOURCES.md) preserve the initial scaffold's references.

## Research foundation

| Primary source | Use in this project | Evidence boundary |
| --- | --- | --- |
| [Goulet Coulombe (2024), JAE](https://doi.org/10.1002/jae.3030) | Final 21-page article read; Section 3 and Tables 1–2 establish main target, factor and timing design | Its results do not establish a Jev advantage; code-level preprocessing still needs verification |
| [Published supporting appendix](https://onlinelibrary.wiley.com/doi/suppl/10.1002/jae.3030/supinfo/jae3030-sup-0001-Appendix.pdf) | All 32 PDF pages read; A.2 mechanism tests, A.4/A.6 settings, A.7 monthly targets and Tables 4–5 checked | Some exact defaults remain unstated; text/table discrepancies are recorded rather than silently resolved |
| [Earlier working paper](https://arxiv.org/pdf/2006.12724) | Historical context only | No longer the authority for the current specification |
| [Journal data archive](https://doi.org/10.15456/jae.2023321.0115060814) | Exact deposited data and provenance | Archive contains data, not the entire experiment pipeline or historical release vintages |
| [Author's pinned R package](https://github.com/philgoucou/macrorf/tree/bdb2ed435affb741aafdf78bab12c470ec6d55d0) | Audited external engine; actual-R adapter and contracts | No original benchmark runner; engine defaults are not proof of each paper invocation |
| [Author's pinned TVP package](https://github.com/philgoucou/tvpridge/tree/d2d52bb9e0126fb580fb8301f305035d3047b4b2), linked from the [code page](https://philippegouletcoulombe.com/code) | Entire two-step ridge source/help inspected; external native adapter, both actual tuning stages and independent numerical/refit checks | Estimator only, not the 2024 caller; current GARCH optimizer warnings and the failed source-cell comparison remain explicit |
| [Author's documentation fork](https://github.com/philgoucou/MacroRF-1/tree/8157619249bbdda3d0e4c8ea694d7c9168f5949f) | Cross-check of usage and package parameters | Monthly PAYEMS tutorial differs from the quarterly paper benchmark |
| [Official FRED databases](https://www.stlouisfed.org/research/economists/mccracken/fred-databases) and [FRED-QD paper](https://www.stlouisfed.org/-/media/project/frbstl/stlouisfed/publications/review/pdfs/2021/01/14/fred-qd-a-quarterly-database-for-macroeconomic-research.pdf) | Metadata semantics, header identities and preparation conventions | Does not establish which completion rank or eligible panel the MRF runner used |
| [Python implementation documentation](https://mrf-web.readthedocs.io/en/latest/) | Portability comparison and implementation guidance | Do not assume identical predictions to the R reference |

The archive's [README](https://journaldata.zbw.eu/dataset/c48432e1-5a25-49f1-95b1-6c681f21e252/resource/57da9dba-6157-4e56-838a-f57358854ca7/download/readme.gc.txt) and the downloaded ZIP were inspected directly. File identities, checksums and parsing findings are recorded in [MRF_REPLICATION.md](MRF_REPLICATION.md). These are verified inputs. The [first full reconstruction](../reports/MRF_UNEMPLOYMENT_RECONSTRUCTION.md) has passed artifact checks but misses the published forest ratio; exact replication remains open.

The final PDFs were supplied through the user's downloads. The appendix SHA-256 is `665fac2b6a21b8f2b28442dfe60aec30aee542c3dac2876b322f4e249718fb1b`. PDFs, page renders and extracted full text are not committed. Table ratios in the documentation are attributed source facts, not locally reproduced scores.

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

The external TVP source has SHA-256 1cc6cce8fb7f3524469b37328519097908f56c56631b09bc6feb512402142a45 and declares GPL-3. It is downloaded separately, never copied into our MIT package. The [TV-FAAR declaration](TVP_FAAR_CONTROL.md) identifies reconstruction choices; the [completed result](../reports/MRF_TVP_FAAR.md) distinguishes arithmetic integrity, optimizer convergence and published-cell agreement.

Our code license does not replace upstream licenses. Keep external implementations distinct and honor their terms. In particular, the inspected author R package declares GPL-3; it must not be copied into this repository and relabeled MIT. Data reuse and distribution retain the archive's attribution and applicable series terms.

The earlier September 2026 FRED-MD snapshot and its checksum belong to the old monthly pilot. They are not substitutes for the paper's deposited data.
