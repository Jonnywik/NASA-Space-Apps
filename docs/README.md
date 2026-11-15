# Tanaw documentation

Start with the [project README](../README.md) for what Tanaw is and how to run it.

## Core references
| Document | What it covers |
|---|---|
| [SUBMISSION_SCOPE.md](SUBMISSION_SCOPE.md) | The submission plan, the real NISAR findings (v6 / v6.1) and the story |
| [NISAR_RUNBOOK.md](NISAR_RUNBOOK.md) | How the NISAR products were found, processed and checked, with every result and correction |
| [API_CONTRACT.md](API_CONTRACT.md) | Backend endpoints, response shapes and shared constants |
| [HOSTING.md](HOSTING.md) | How the public demo is built and how to create the Hugging Face Space |

## Science and validation — [`science/`](science/)
- [VALIDATION.md](science/VALIDATION.md): NISAR vs OPERA DSWx-S1 comparisons and threshold sensitivity
- [SOURCE_REVIEW.md](science/SOURCE_REVIEW.md) and [HYPOTHESES_SOURCES.md](science/HYPOTHESES_SOURCES.md): literature and source notes
- [COHERENCE_PIPELINE.md](science/COHERENCE_PIPELINE.md), [DREI_P2_PIPELINE.md](science/DREI_P2_PIPELINE.md), [P3_PIPELINE.md](science/P3_PIPELINE.md): pipeline notes for the regional (Sentinel-1) layers

## Data — [`data/`](data/)
- [DATA_MANIFEST.md](data/DATA_MANIFEST.md): every dataset, its source, licence and checksum
- [DATA_PACKAGE.md](data/DATA_PACKAGE.md): the downloadable NISAR product package and how it was verified

## Design — [`design/`](design/)
- [DESIGN_SPEC_V2.md](design/DESIGN_SPEC_V2.md) and the [Mangrove mock-ups](design/v2-mangrove/)

## Screenshots — [`screenshots/`](screenshots/)
- [`current/`](screenshots/current/): the app on real NISAR data
- [`archive/`](screenshots/archive/): earlier versions (v1, and the v2 redesign on synthetic demo data)

## Submission — [`submission/`](submission/)
- [FIL_REVIEW.md](submission/FIL_REVIEW.md): Filipino strings for native review

## Project log — [`project-log/`](project-log/)
Coordination history between the team's AI agents (task lists, status reports, audits and proposals). Kept for transparency; not needed to use the app.
