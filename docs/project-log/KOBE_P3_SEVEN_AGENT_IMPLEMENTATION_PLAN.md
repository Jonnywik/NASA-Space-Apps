# Kobe P3 — seven-agent implementation plan

Planning baseline: 29 October 2026. Covers all seven tasks listed for Kobe in the Google Doc's Backend subtab, including the biomass, projection and briefing work that the revised timeline previously deferred. This is an implementation plan, not a claim that those features or real-data validations are complete.

## 1. Goal, baseline and execution model

Deliver a backend that ingests supported NISAR products, converts phase into LOS displacement, reconstructs motion histories and rates, performs calibrated biomass retrieval, prepares elevation/water-level inputs, publishes conditional future scenarios, and generates factual template briefings.

Baseline: `feature/before-after-slider`, local commit `1165f16`. Paired coherence extraction/change mapping already exists and passed 17 synthetic tests. It has no real-event validation yet. The API currently serves flood files only. No NISAR, biomass reference, motion, DEM or surge inputs are present. ASF/Earthdata access and credentials remain unavailable. These constraints block real-data completion, not contract design, implementation or synthetic verification.

### Agent configuration and ownership

| Role | Model / reasoning | Assigned task | Exclusive production ownership |
|---|---|---|---|
| Orchestrator | `gpt-6.1-sol` / `high` | Shared contracts, scheduling, review, API integration and release checks | Shared schemas, product catalog/publication utilities, central API registration and dependencies |
| Luna 1 — ingestion | `gpt-6-luna` / `max` | NISAR dataset integration | Ingestion adapters and ingest CLI |
| Luna 2 — phase | `gpt-6-luna` / `max` | Unwrapped phase to LOS displacement | Phase conversion, referencing and correction module/CLI |
| Luna 3 — series | `gpt-6-luna` / `max` | Multi-pair reconstruction and annual rates | Acquisition-network solver, regional/point summaries and motion CLI |
| Luna 4 — biomass | `gpt-6-luna` / `max` | GCOV biomass and Roots & Faults fusion | Vegetation features, calibrated retrieval, validation and fusion module/CLI |
| Luna 5 — terrain | `gpt-6-luna` / `max` | DEM and surge inputs | Elevation, datum and water-level preparation module/CLI |
| Luna 6 — projections | `gpt-6-luna` / `max` | Year-by-year projection calculations | Motion extrapolation, conditional exposure and projection module/CLI |
| Luna 7 — briefings | `gpt-6-luna` / `max` | Template briefing engine | Structured fact aggregation, templates and briefing module/CLI |

Luna dispatch settings are `model="gpt-6-luna"`, `reasoning_effort="max"`, and `fork_turns="none"`; each receives the approved contract and task brief explicitly.

Use seven distinct task agents overall. This environment permits seven active agents including the root, so at most six Luna agents run simultaneously. Never silently replace a requested model with another model. Configure the main chat to GPT-6.1 Sol/high before execution; this plan itself does not switch the chat's model.

Create `feature/kobe-p3-backend` from the committed coherence-pipeline baseline at execution start. The wider revised Phase 2 is not assumed complete. Use one shared workspace with exclusive module ownership; agents do not switch branches or commit independently. Only the orchestrator edits shared files or integrates commits. Preserve unrelated planning files.

Proposed organization: seven subpackages beneath `backend/processing/p3/`, one per workstream, with matching task-specific tests. Number new CLIs 10–16, retaining 07–09 for the remaining P2 work. Each agent writes its module documentation, unit tests and a handoff containing commands, source references, changed files, test evidence and blockers.

## 2. Common contracts and agent handoffs

The orchestrator establishes these contracts and tiny fixtures before implementation agents start. Subsequent contract changes go through the orchestrator and all affected consumers; no agent adds a second incompatible schema to make its tests pass.

### Inputs and normalized products

- Event IDs come from the event registry; input manifests reference local provider files, verified product IDs, acquisition timestamps, sensor/band, polarization, orbit/frame, processing version, maturity, native units, CRS, grid and source hashes.
- Keep NISAR GUNW/GCOV and Sentinel-1 fallback adapters explicit. Existing 2022–2025 flood events cannot simply be relabeled as NISAR events. Register a separate NISAR pilot period only after actual coverage and acquisitions are verified.
- Do not silently combine sensors, tracks, frequencies, polarizations, product versions or maturity levels. A fallback is a compatible separately identified product with a substitution notice; it cannot supply a measurement it does not contain.
- GUNW normalization produces phase in radians, coherence, connected-component labels and available correction/geometry layers, plus wavelength and a verified phase-to-LOS sign convention. GCOV normalization produces identified covariance/backscatter terms, native quality masks and units.
- Product adapters read geolocation from the specific supported product specification/version. Reject unsupported layouts rather than choosing an arbitrary HDF5 array. Read rasters in windows/chunks.
- Preserve native analysis detail. Use separate product grids; align downstream combinations at no finer than their coarsest contributing resolution. Continuous arrays and categorical masks use appropriate distinct resampling. NaN/missing data never becomes zero movement or dry ground.

### Publication, status and units

Write immutable products beneath `data/output/<event>/p3/<product>/<runId>/`. Publish a validated manifest last; atomically update the current-product catalog pointer only after review requirements pass. Staging failures leave the prior pointer unchanged. Raw data, large derived rasters, credentials and downloaded models stay outside Git; commit small synthetic fixtures only.

Every manifest includes schema version, event, product, run ID, upstream run IDs, source hashes, algorithm/config versions, timestamps, data kind (`observed`, `derived`, `scenario`, `synthetic`), actual sensor provenance, units, native resolution, valid coverage, applied corrections, quality, warnings and asset hashes. Preserve synthetic lineage through every downstream product.

Track `implementationStatus` independently from `dataStatus`. Implementation is pending/verified; data is missing/needs-review/validated. A valid published empty detection is distinct from missing or failed data. Unknown numerical values are null with a reason. Scientific readiness is never inferred merely from file existence or passing synthetic tests.

Canonical units: radians for phase; metres for intermediate physical displacement/elevation/water levels; mm for displayed LOS displacement; mm/year for motion rate; Mg/ha for calibrated biomass; km² for area. LOS output is positive away from the satellite; vertical input is positive upward. Source-specific adapters explicitly record the conversion needed to reach those conventions.

### Minimal APIs integrated by the orchestrator

Keep current flood routes compatible. New read endpoints return published results; heavy processing remains in CLIs for this work package, avoiding a dependency on the unfinished P2 job service.

| Endpoint | Interface |
|---|---|
| `GET /api/v1/ground-motion` | Event and optional run ID; rate/displacement asset references, supported epochs, regional summaries, reference and quality. |
| `GET /api/v1/subsidence` | Compatibility alias for ground motion, with the same LOS semantics. |
| `GET /api/v1/ground-motion/point` | Event/run and longitude/latitude; native-cell center, displacement series, support, rate/fit statistics or a specific no-data reason. |
| `GET /api/v1/vegetation` | Event/run; calibrated biomass assets and regional metrics, or calibration-unavailable status. |
| `GET /api/v1/scenario-inputs` | Event/input run; elevation/water-level provenance, datum/epoch compatibility and missing prerequisites. |
| `GET /api/v1/projection` | Event, scenario ID, integer year; supported scenario assets, exposure metrics, assumptions and uncertainty definitions. |
| `GET /api/v1/briefing` | Event, product/run, registered region ID; deterministic paragraph, structured facts, provenance and template version. No free-form LLM prompt. |

Add product capabilities to event metadata without changing the meaning of the existing flood `ready` field. Return clear reason codes for data unavailable, review required, invalid year, unsupported product and outside coverage; unknown event remains 404. Asset URLs resolve through registered manifests, never arbitrary local paths or remote URLs. No frontend implementation is included.

## 3. The seven implementation work packages

### Luna 1 — NISAR integration

**Inputs:** Provider files and versioned source manifests. **Outputs:** normalized GUNW and GCOV products consumed by Lunas 2 and 4.

Implement HDF5 reading with `h5py`, plus an explicit ARIA NetCDF adapter using `xarray`/`netCDF4` for the documented fallback. Product, frequency and polarization selection are explicit. Validate dimensions, coordinate arrays, projection, units, wavelength, masks, pair chronology and processing provenance. Preserve NISAR correction layers and whether each has actually been applied. Read-only provider metadata lookup may run when network access exists; data acquisition failures produce a blocker record rather than a fake manifest.

A source profile supplies the documented sign convention and dataset mapping. Missing wavelength/sign cannot be filled with a guessed Sentinel-1 constant. Real sample inspection and the pinned provider specification must substantiate each supported production profile; synthetic HDF5 fixtures verify internal plumbing only.

**Checks:** Known fixture groups/coordinates, missing groups, unsupported versions, frequency/polarization differences, masked values, corrupt metadata and round-trip georeferencing. No authentic NISAR pilot is published without actual product evidence.

### Luna 2 — Phase to LOS displacement

**Inputs:** Luna 1 GUNW manifest; a recorded reference region and correction configuration. **Outputs:** one referenced LOS displacement-difference raster per acquisition pair, validity/quality layers and conversion metadata.

Convert using `dAway = phaseToAwaySign × wavelength × phase / (4π)` in metres; convert to mm once on export. Verify sign against a known source-convention example. Remove the valid reference-region median for each pair. Default to coherence >=0.3 and at least five valid reference pixels; keep these configurable and recorded. Restrict a pair to the connected component that supports its reference region. Reject an absent or ambiguous reference instead of mixing independently unwrapped components.

Preserve exact correction state. Default to provider data as delivered, with unapplied corrections disclosed; an explicit correction configuration subtracts only verified, compatible phase-screen terms and records each operation. Never automatically subtract a layer that was already applied. Reference stability remains an evidence requirement for real observations.

**Checks:** Known wavelength/phase/sign, radians versus degrees rejection, conversion to mm, reference subtraction, invalid/low-quality pixels, disconnected components and double-application protection.

### Luna 3 — Time series and annual rates

**Inputs:** Luna 2 pair differences using a consistent source profile, spatial reference and grid. **Outputs:** connected acquisition histories, per-pixel rate/support/residual rasters, point queries and regional summaries.

Treat interferograms as differences between acquisition epochs. Build the acquisition graph and solve the reference-epoch-constrained linear system with least squares; do not blindly sum pairs or treat them as cumulative observations. Earliest supported epoch is temporal zero. Disconnected epochs remain unavailable. Group common validity patterns and process tiles to avoid allocating an unbounded image-by-network matrix.

Use equal weights unless compatible measurement variances are available, in which case use inverse-variance weights. Fit against elapsed years using 365.2425 days/year. Publish an annualized rate only at pixels with >=6 connected acquisition epochs spanning >=90 days; these are engineering floors, not proof of long-term representativeness. Shorter valid series may publish displacement alone. Preserve gaps and flag short-span/seasonal limitations.

Return fit residuals, epoch count, observation span and applicable standard errors, without treating coherence as a probability or fit error as complete geophysical uncertainty. Region summaries use valid-cell medians and support counts; time-series spread is not a confidence interval. No vertical subsidence label is inferred from LOS alone.

**Checks:** Recover a known synthetic network and rate; redundant/reversed edges, gaps, disconnected networks, irregular dates, reference consistency, masked cells, spatial aggregation and rate-publication thresholds.

### Luna 4 — GCOV biomass and Roots & Faults

**Inputs:** Luna 1 covariance terms, independent biomass-reference observations, plot geometry/date metadata and documented train/validation splits. **Outputs:** validated model artifact, calibrated biomass raster, applicability mask, validation report and optional regional fusion table with Luna 3 motion.

The initial supported retrieval uses positive HHHH and HVHV power terms converted to dB, a standardized two-feature ridge regression predicting `log1p(AGB)`, and inverse transformation to Mg/ha. Fix ridge alpha=1 with an unpenalized intercept. Keep the model family explicit/versioned. Different polarizations need their own calibrated profile; do not silently replace a required channel.

Aggregate radar features over matched reference plots. Require declared spatially independent training and validation groups, at least ten usable training plots and five validation plots, full-rank features and matching units; these are implementation floors, not a scientific adequacy guarantee. Never randomly split neighboring pixels and call that independent validation. Reference timing mismatch and model acceptance limits must be documented in the calibration manifest. Publish validation bias/RMSE and range; do not invent a universal accuracy threshold. No calibration manifest, independent validation or agreed acceptance limits means no quantitative biomass publication.

Mask predictions outside the calibrated feature range. A zero biomass estimate is not a stand-in for missing data. Fusion joins independently supported biomass and motion regional metrics with source dates/resolution disclosed; it reports association, not causation or a combined invented hazard score.

**Checks:** Known synthetic calibration recovery, unit conversions, missing terms, nonpositive power, invalid splits, insufficient reference data, domain masking and explicit uncalibrated status. Real calibration and its independent assessment remain required.

### Luna 5 — DEM and surge input preparation

**Inputs:** DEM/DSM, quality masks, acquisition/reference epochs, tide/surge or total-water-level inputs, vertical datum definitions and any required transformation grids. **Outputs:** aligned scenario-input package with a compatibility report.

Normalize horizontal geometry, metres and nodata. Record whether terrain heights represent ground or surface features. Copernicus GLO-30 is a surface model; do not describe its pixels as precise road or building-ground elevations. Keep native elevation uncertainty and source dates.

Require DEM and water levels in a common vertical datum and epoch. Apply a documented transformation only when the necessary offsets/grids are supplied; matching horizontal CRS is insufficient. Keep tide, mean water level and surge components separate to prevent double-counting, or accept a declared total-water-level input. Support prepared water-level rasters or dated scalar levels; this task consumes a documented model's outputs rather than building a hydrodynamic solver.

Require a reviewed elevation baseline at the projection epoch; an older DEM cannot be relabeled current without a documented adjustment. Supply a coastal connectivity seed/barrier mask for later exposure screening. Missing datum conversion, baseline history or water-level semantics yields an incomplete-input report, not an inundation product.

**Checks:** Datum/units/epoch mismatch, nodata, known vertical offset, double-counted water components, resolution alignment and provenance of every adjustment.

### Luna 6 — Future-year calculations

**Inputs:** Luna 3 motion, Luna 5 compatible elevation/water inputs, and a versioned scenario configuration. **Outputs:** per-year motion/exposure rasters, polygons, regional metrics and model card served by the projection endpoint.

Implement two separately enabled calculations:

- LOS extrapolation: hold the selected LOS rate constant from its reference epoch, without labeling it vertical motion.
- Conditional water exposure: `z(y) = z(base) + vVertical × elapsedYears`; classify valid cells at/below the scenario water level, keeping only cells connected to the supplied coastal seeds through permitted cells.

Water exposure requires independently supported vertical motion, or a reviewed vertical-only inference with incidence geometry and explicit negligible-horizontal-motion assumption. For the latter, convert positive-away LOS to positive-up vertical with `vVertical = -vAway / cos(incidence)`, rejecting invalid geometry. It is disabled by default. No automatic LOS-to-DEM substitution is allowed.

Intended years are 2026–2035, restricted to the scenario's supported baseline/horizon. Reject unsupported years rather than clamping. Show the measurement span alongside the scenario horizon and require the permitted horizon to be declared in the reviewed scenario configuration. Prepared low/central/high scenarios use supplied parameter sets; no fabricated water levels or confidence percentages. Export assumptions and available uncertainty terms; label interval types precisely. Compare baseline/future and future/future using consistent native support. Exposure metrics come from supplied asset/population snapshots; unavailable sources yield null metrics.

**Checks:** Zero-rate baseline, sign/unit conversion, known threshold exposure, isolated inland depression, barrier/nodata behavior, missing vertical evidence, unsupported years, and consistent per-year geometry/statistics. Describe static screening as a conditional scenario, not a flood forecast.

### Luna 7 — Template briefing engine

**Inputs:** Published metric/run manifests, registered regions and available OSM/exposure snapshots. **Outputs:** deterministic text plus the exact structured facts used, template version and source lineage.

Build separate templates for observations, motion, vegetation and scenarios. Each states region, observation/projection dates, measured or modeled values, valid coverage, sources and limitations. Deduplicate mapped assets when aggregating provided footprints; distinguish asset overlap from damage and exposure from confirmed affected population. Missing exposure remains unavailable. An empty detection is reported within its valid coverage, never as proof of safety.

No external LLM is required in this task. Do not generate numbers, causal explanations, closure status or recommendations absent from the structured inputs. Region names/source text are escaped and treated as data. Stable inputs produce stable text; timestamps live in metadata rather than changing the factual paragraph on every call.

**Checks:** Known input facts, missing metrics, zero versus unavailable, mixed synthetic/observed lineage, scenario wording, duplicate assets, stale/mismatched upstream runs, text escaping and deterministic output.

## 4. Orchestration, integration and verification

### Execution waves

1. **Bootstrap — orchestrator:** Create the branch, schemas, module skeletons, contract fixtures and test command. Resolve/pin compatible `h5py`, `xarray`, `netCDF4` and API-test dependencies in the existing Python environment. Record unavailable provider access without exposing secrets.
2. **Independent work — Lunas 1, 4, 5 and 7:** Start ingestion, biomass, terrain and briefing implementations against frozen fixtures. Luna 4's real inputs wait for Luna 1; Luna 7 uses fixture product manifests until upstream outputs exist.
3. **Phase conversion — Luna 2:** Start once Luna 1's normalized contract is frozen; integrate with its actual adapter output after the ingestion checks pass.
4. **Series — Luna 3:** Start from Luna 2's accepted difference contract; integrate after conversion checks pass.
5. **Projections — Luna 6:** Start from accepted motion and terrain contracts; integrate after Lunas 3 and 5 pass. Luna 4 fusion can now consume motion results. Luna 7 then validates real cross-product inputs where available.
6. **Integration — orchestrator:** Register APIs, run the full chain and regress existing P2 functionality. Return defects to the owning Luna agent. Release a slot before scheduling a seventh child if concurrency reaches six.

Independent agents may continue while another waits on data. Do not merge incompatible early outputs or unblock an agent by silently modifying its input schema. A blocked real-data task does not block implementation against accurately labeled fixtures.

### Review checkpoints

Each agent reports: exact module/CLI interfaces, test command and outcome, artifact names/hashes, source-profile assumptions, known limitations, and implementation/data status separately. The orchestrator independently reviews code and numerical claims, checks ownership conflicts, and rejects fake examples published as observations.

Required verification layers:

- Agent-specific numerical and geospatial tests described above.
- Contract tests between every producer/consumer and API tests for ready, empty, unavailable, outside-coverage, bad-year and mismatched-run cases.
- Synthetic end-to-end chain: HDF5 input → normalization → pair displacement → known temporal network/rate → compatible scenario inputs → annual geometry → briefing. Test a separate known biomass calibration chain and fusion join.
- Regression: the existing 17 coherence tests and current flood/event/overlay API behavior still pass.
- Operational checks: bounded-memory tiled processing on a recorded fixture, staged-write failure recovery, immutable run lineage, path validation and no credentials/raw files in Git.
- Real validation: inspect actual supported products, reference/sign/corrections, held-out biomass evidence, datum/baseline alignment, and scenario assumptions. Start with one genuine NISAR pilot AOI/period. Validate historical Sentinel-1 events separately where products exist.

The orchestrator stages only reviewed implementation files, tests, small fixtures and documentation. Commit integrated task groups after their checks pass. Push, PR creation or deployment is a later explicit delivery step; no real-data completion claim accompanies a code-only commit.

## 5. Completion criteria, blockers and sources

**Implementation complete:** All seven CLIs/modules and their API integration work against shared schemas; numerical, contract, end-to-end and regression checks pass; manifests, method cards and operator instructions explain availability and uncertainty.

**Real-data complete:** Suitable provider products have been retrieved and reviewed; motion sign/reference/corrections and temporal support are substantiated; biomass calibration passes its declared independent acceptance limits; projection datums, baseline and vertical interpretation are supported. Blocking prerequisites are recorded per product. Passing fixture tests does not satisfy this milestone.

Known blockers: provider access/authentication, actual NISAR acquisition coverage, sufficient motion history, stable reference evidence, independent biomass calibration data, compatible elevation/water-level datums and epochs, and exposure snapshots. The orchestrator cannot create provider credentials or change network policy through the currently exposed read-only environment tools. It must not bypass policy or invent missing inputs.

No calendar duration is promised before data availability and task estimates are reviewed. Implementation waves proceed now when authorized; real-data timelines depend on external inputs and processing queues.

Sources:

- [Project research and Backend assignments](https://docs.google.com/document/d/1GMTLeCqXxD09z3JLqv_QOgCJtMgEoLRh1Jcqb9eN8u4/edit).
- [ASF NISAR GUNW guide](https://hyp3-docs.asf.alaska.edu/nisar-docs/gunw/): product phase units and correction-state considerations.
- [ASF NISAR GCOV guide](https://nisar-docs.asf.alaska.edu/gcov/): calibrated covariance/backscatter products, supporting retrieval rather than direct biomass measurements.
- [NISAR data availability](https://nisar-docs.asf.alaska.edu/availability-overview/): actual product availability must be checked for the chosen AOI and dates.
- [Copernicus DEM specification](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM): surface-model interpretation, source epochs, vertical datum and units.
