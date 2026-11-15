# Data manifest

The manifests linked below record retrieved metadata and cached products. Timestamps are UTC. Raw downloads are not necessarily included in the repository. Source licences below are as recorded in the caches; missing licence information has not been independently checked.

## NISAR source granules

[CMR catalogue manifest](../../backend/data/cache/nisar/nisar_manifest_t140_A_f009_m4005.json), retrieved 2026-11-14 16:25:29 UTC, selects track 140 ascending, frame 009, GCOV mode 4005 and GUNW mode 4000. Study windows of 11 GCOV granules were read for the open-water product; nine GUNW windows were examined but no motion product was produced. The manifest records exact identifiers, versions and catalogue checksums; catalogue checksums do not establish that entire remote files were downloaded or independently verified. See the [runbook](../NISAR_RUNBOOK.md).

| Collection | Provider | CMR concept ID | Use | Licence |
|---|---|---|---|---|
| GCOV Provisional / V1 | ASF DAAC via [NASA CMR](https://cmr.earthdata.nasa.gov/search) | C2854338529-ASF / C3622241360-ASF | Flood and backscatter | Not recorded in cache |
| GUNW Provisional / V1 | ASF DAAC via [NASA CMR](https://cmr.earthdata.nasa.gov/search) | C2854335566-ASF / C3622247503-ASF | Line-of-sight motion | Not recorded in cache |

The [SME2 manifest](../../backend/data/cache/nisar/soil_moisture/manifest.json) records nine exact product IDs from `NISAR_L3_SME2_PROVISIONAL_V1`; it was generated 2026-11-15 04:36:21 UTC. Individual retrieval times are not recorded. The provisional 200 m soil-moisture product is not served by the API.

## IMERG and OPERA

- **Round 5 (15 Nov, coordinator):** 10 more OPERA DSWx-S1 references (Sentinel-1C, 10:06 UTC, tile T51PTS, 27 Jun – 25 Oct 2026), each 24.3 h before a NISAR track 32 D pass, retrieved from PO.DAAC with provider MD5 checks by `scripts/63_cross_track.py`. Granule ids, times and scores are in [cross_track.json](../../backend/data/cache/validation/cross_track.json). IMERG for the 18:24 passes: [imerg_passes_t032D.json](../../backend/data/cache/climate/imerg_passes_t032D.json). NISAR track 32 D GCOV manifest: [nisar_manifest_t032_D_f081_m4005.json](../../backend/data/cache/nisar/nisar_manifest_t032_D_f081_m4005.json).

- [NASA GPM IMERG Late Run](https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGHHL_07/summary), `GPM_3IMERGHHL` V07, DOI 10.5067/GPM/IMERG/3B-HH-L/07: the [pass cache](../../backend/data/cache/climate/imerg_passes.json) was retrieved 2026-11-15 05:16:57 UTC and summarizes half-hourly 0.1-degree rain before each pass. Granule-level retrieval records are not retained there.
- [OPERA DSWx-S1 V1](https://podaac.jpl.nasa.gov/dataset/OPERA_L3_DSWX-S1_V1), collection `C2949811996-POCLOUD`, tile `T51PTS`: a 2026-11-15 catalogue check found 40 granules in the area, with dates within two calendar days of 10 NISAR passes. Seventeen date-matched references were checked; 14 were all fill and three usable. The three references below were retrieved and provider MD5 verified on 2026-11-15; each is about 48 hours 15 minutes after the corresponding NISAR pass. See the linked comparison records for checksums and precise generation times. DSWx is a separate Sentinel-1 surface-water product, not ground truth; the comparison is total water, not flood accuracy. Details and threshold sensitivity are in [validation](../science/VALIDATION.md).

| CMR granule | Exact OPERA product, version 1.0 | Comparison record |
|---|---|---|
| `G4361329706-POCLOUD` | `OPERA_L3_DSWx-S1_T51PTS_20260917T214554Z_20261012T223352Z_S1D_30_v1.0` | [15 September](../../backend/data/cache/validation/comparison_20260915_near_match.json) |
| `G4361778874-POCLOUD` | `OPERA_L3_DSWx-S1_T51PTS_20261011T214554Z_20261013T061017Z_S1D_30_v1.0` | [9 October](../../backend/data/cache/validation/comparison_20261009_near_match.json) |
| `G4408674689-POCLOUD` | `OPERA_L3_DSWx-S1_T51PTS_20261104T214554Z_20261109T201952Z_S1D_30_v1.0` | [2 November](../../backend/data/cache/validation/comparison_20261102_near_match.json) |

## Retrieved caches

The [places manifest](../../backend/data/cache/places/manifest.json) records source URLs, raw and derived SHA-256 hashes, and product paths; the [climate manifest](../../backend/data/cache/climate/manifest.json) records query parameters and cached-file SHA-256 hashes. These are provenance records, not proof of independent scientific validation.

| Dataset | Source and licence as recorded | Version or period | Retrieved UTC | Use |
|---|---|---|---|---|
| Administrative boundaries | [HDX COD-AB Philippines](https://data.humdata.org/dataset/cod-ab-phl); CC BY-IGO | valid 2025-02-13, v03; metadata modified 2026-05-28 | 2026-11-14 16:14:02 | City and barangay search and exposure |
| Population | [WorldPop Philippines](https://hub.worldpop.org/geodata/summary?id=36130); CC BY 4.0 | 2020 constrained 100 m BSGM | 2026-11-14 16:14:22 | Estimated population exposure |
| Land cover | [ESA WorldCover](https://esa-worldcover.org/en/data-access); CC BY 4.0 | 2021 v200, tile N12E120, 10 m | 2026-11-14 16:15:51 | Land-cover context |
| Buildings | [HOT OSM export](https://data.humdata.org/dataset/hotosm_phl_buildings); ODbL 1.0, © OpenStreetMap contributors | 2026-10-12 snapshot | 2026-11-14 16:16:18 | Building exposure; completeness unknown |
| Daily rainfall | [NASA POWER](https://power.larc.nasa.gov/api/temporal/daily/point); licence not recorded | PRECTOTCORR, 1991-01-01 to 2026-11-14, point 14.7 N, 120.96 E | 2026-11-14 16:25:20 | Rainfall context |
| Daily historical rainfall | [Open-Meteo archive](https://archive-api.open-meteo.com/v1/archive); licence not recorded | ERA5, 2000-01-01 to 2026-11-14, same point | 2026-11-14 16:23:27 | Historical comparison |
| Seasonal outlook | [Open-Meteo seasonal API](https://seasonal-api.open-meteo.com/v1/seasonal); licence not recorded | ECMWF SEAS5, same point; query details in manifest | 2026-11-14 16:25:51 | Conditional outlook |
| Catalogue availability | NASA CMR and Landsat STAC; licences not recorded | NISAR GCOV, Sentinel-1 and Landsat C2 L2 catalogue queries | 2026-11-14 16:25:58 | Timeline availability, not image analysis |
| Sentinel-1 context | Source and licensing for existing historical outputs require per-event verification | 2022–2025 events | Not established here | Separate C-band context, not NISAR |

WorldPop is a 2020 modelled estimate; source resolution and dates differ across layers. NASA POWER can overestimate dry-season rainfall locally. Cached data availability and licences should be rechecked before redistribution or submission.

## Exact NISAR product identifiers

Identifiers are copied from the cached manifests above; collection versions and checksums remain available there.

### GCOV

- `NISAR_L2_PR_GCOV_023_140_A_009_4005_DHDH_A_20260623T213035_20260623T213109_P05023_N_F_J_001`
- `NISAR_L2_PR_GCOV_024_140_A_009_4005_DHDH_A_20260705T213034_20260705T213109_P05023_N_F_J_001`
- `NISAR_L2_PR_GCOV_025_140_A_009_4005_DHDH_A_20260717T213034_20260717T213108_P05023_N_F_J_001`
- `NISAR_L2_PR_GCOV_027_140_A_009_4005_DHDH_A_20260810T213032_20260810T213107_P05023_N_F_J_001`
- `NISAR_L2_PR_GCOV_028_140_A_009_4005_DHDH_A_20260822T213032_20260822T213106_P05023_N_F_J_001`
- `NISAR_L2_PR_GCOV_029_140_A_009_4005_DHDH_A_20260903T213032_20260903T213106_P05023_N_F_J_001`
- `NISAR_L2_PR_GCOV_030_140_A_009_4005_DHDH_A_20260915T213031_20260915T213106_P05023_N_F_J_001`
- `NISAR_L2_PR_GCOV_031_140_A_009_4005_DHDH_A_20260927T213031_20260927T213106_P05023_N_F_J_001`
- `NISAR_L2_PR_GCOV_032_140_A_009_4005_DHDH_A_20261009T213031_20261009T213106_P05023_N_F_J_001`
- `NISAR_L2_PR_GCOV_033_140_A_009_4005_DHDH_A_20261021T213032_20261021T213106_P05036_N_F_J_001`
- `NISAR_L2_PR_GCOV_034_140_A_009_4005_DHDH_A_20261102T213032_20261102T213106_P05036_N_F_J_001`

### GUNW

- `NISAR_L2_PR_GUNW_023_140_A_009_024_4000_SH_20260623T213035_20260623T213109_20260705T213034_20260705T213109_P05023_N_F_J_001`
- `NISAR_L2_PR_GUNW_024_140_A_009_025_4000_SH_20260705T213034_20260705T213109_20260717T213034_20260717T213108_P05023_N_F_J_001`
- `NISAR_L2_PR_GUNW_025_140_A_009_027_4000_SH_20260717T213034_20260717T213108_20260810T213032_20260810T213107_P05023_N_F_J_001`
- `NISAR_L2_PR_GUNW_027_140_A_009_028_4000_SH_20260810T213032_20260810T213107_20260822T213032_20260822T213106_P05023_N_F_J_001`
- `NISAR_L2_PR_GUNW_028_140_A_009_029_4000_SH_20260822T213032_20260822T213106_20260903T213032_20260903T213106_P05023_N_F_J_001`
- `NISAR_L2_PR_GUNW_029_140_A_009_030_4000_SH_20260903T213032_20260903T213106_20260915T213031_20260915T213106_P05023_N_F_J_001`
- `NISAR_L2_PR_GUNW_030_140_A_009_031_4000_SH_20260915T213031_20260915T213106_20260927T213031_20260927T213106_P05023_N_F_J_001`
- `NISAR_L2_PR_GUNW_031_140_A_009_032_4000_SH_20260927T213031_20260927T213106_20261009T213031_20261009T213106_P05023_N_F_J_001`
- `NISAR_L2_PR_GUNW_032_140_A_009_033_4000_SH_20261009T213031_20261009T213106_20261021T213032_20261021T213106_P05036_N_F_J_001`

### SME2

- `NISAR_L3_PR_SME2_023_140_A_009_4005_DHDH_A_20260623T213035_20260623T213109_P05023_N_F_J_001`
- `NISAR_L3_PR_SME2_024_140_A_009_4005_DHDH_A_20260705T213034_20260705T213109_P05023_N_F_J_001`
- `NISAR_L3_PR_SME2_025_140_A_009_4005_DHDH_A_20260717T213034_20260717T213108_P05023_N_F_J_001`
- `NISAR_L3_PR_SME2_027_140_A_009_4005_DHDH_A_20260810T213032_20260810T213107_P05023_N_F_J_001`
- `NISAR_L3_PR_SME2_028_140_A_009_4005_DHDH_A_20260822T213032_20260822T213106_P05023_N_F_J_001`
- `NISAR_L3_PR_SME2_029_140_A_009_4005_DHDH_A_20260903T213032_20260903T213106_P05023_N_F_J_001`
- `NISAR_L3_PR_SME2_030_140_A_009_4005_DHDH_A_20260915T213031_20260915T213106_P05023_N_F_J_001`
- `NISAR_L3_PR_SME2_031_140_A_009_4005_DHDH_A_20260927T213031_20260927T213106_P05023_N_F_J_001`
- `NISAR_L3_PR_SME2_032_140_A_009_4005_DHDH_A_20261009T213031_20261009T213106_P05023_N_F_J_001`
