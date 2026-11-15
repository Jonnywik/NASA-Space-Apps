# Validation status

Three comparisons use real NISAR GCOV and OPERA DSWx-S1 pixels. They describe agreement between satellite products, not ground-truth flood accuracy. No ground-motion sign or pattern comparison is available.

| NISAR UTC | OPERA UTC | Gap | Joint cells | Agreement | F1 | IoU |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 2026-09-15 21:30:31 | 2026-09-17 21:46:11 | 48 h 15 m 40 s | 466,248 | 0.8712 | 0.7291 | 0.5737 |
| 2026-10-09 21:30:31 | 2026-10-11 21:46:11 | 48 h 15 m 40 s | 466,248 | 0.8499 | 0.6662 | 0.4994 |
| 2026-11-02 21:30:32 | 2026-11-04 21:46:11 | 48 h 15 m 39 s | 466,248 | 0.8750 | 0.7386 | 0.5855 |

All three are **near matches exceeding 48 hours**, although they meet the two-calendar-day gate. Confusion counts, precise provenance and checksums are in `backend/data/cache/validation/comparison_*_near_match.json`. NISAR total open water is reconstructed from HH/HV and the fixed rule; OPERA total water may include inundated vegetation. The comparison includes coastal and permanent water, and class 0 may include land-cover-masked areas; it does not measure transient flood-only accuracy. Conditions can change between overpasses and SAR sensors can share errors.

Reclassifying both NISAR thresholds by -1, 0 and +1 dB yields half-or-more areas of **0.0230, 0.3721 and 0.3588 km²**, respectively, using the same dilated WorldCover mask. Permanent water is recalculated at each threshold, so the area need not increase monotonically. These are sensitivity scenarios, not confidence intervals.

## Independent flood evidence

- NASA JPL, [OPERA DSWx product suite](https://www.jpl.nasa.gov/go/opera/products/dswx-product-suite/), [dataset DOI](https://doi.org/10.5067/OPDSWS1-L3V1), and [product specification](https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-docs/web-misc/opera/D-108761_OPERA_DSWx_S1AB_ProductSpec_Rev_A.pdf): 17 date-matched granules were checked, 14 all fill and 3 usable. BWTR 0 and 1 map to non-water and water; excluded classes are nodata. Product reuse terms should be checked at the distribution record.
- Philippine Space Agency, [31 August 2026 flood extent maps](https://philsa.gov.ph/news/satellite-data-show-flood-extents-in-regions-1-2-3-4a-4b-car-and-ncr-due-to-enhanced-habagat/), published 3 September 2026: maps and shapefiles are linked for parts of NCR and other regions, using a three-image Sentinel-1 composite; the agency says they need ground validation and may underestimate urban flooding. Exact study-area coverage and reuse licence have not been verified. The selected track 140 catalogue dates do not match the published map dates within the script's two-day limit. Flood extent also needs a compatible flood-only target, not a total-water mask. See [source review](SOURCE_REVIEW.md).

## Published ground motion

Eco, Rodolfo, Sulapas, Morales Rivera, Lagmay et al. (2020), [Disaster in Slow Motion: Widespread Land Subsidence in and Around Metro Manila, Philippines Quantified By InSAR Time-Series Analysis](https://www.jscimedcentral.com/journal-article-info/JSM-Environmental-Science-and-Ecology/Disaster-in-Slow-Motion:-Widespread-Land-Subsidence-in-and-Around-Metro-Manila,-Philippines-Quantified-By-Insar-Time-Series-Analysis-5350), *JSM Environmental Science & Ecology* 8(1):1068. The paper reports at least 2–4.2 cm/year for Manila, CAMANAVA and other named areas using PSInSAR, with Envisat 2003–2010 and ALOS PALSAR-1 2007–2011. These historical rates cannot be directly equated with a four-month NISAR line-of-sight displacement. There is currently no observed T2 result to compare in sign or pattern; reference area, viewing geometry, period and vertical versus LOS motion must be considered before any qualitative comparison.

## Reproduction and limits

`processing.validation.metrics.compare_rasters` accepts normalized binary water rasters (0 dry, 1 water, explicit nodata); it requires matching CRS and north-up grids, resamples by nearest neighbour to the coarser existing grid, and excludes invalid pixels. Overall agreement, F1, IoU and confusion counts use the jointly valid cells. Empty denominators return null. This is point-sampled agreement, not area-weighted and not a ground-truth accuracy claim. DSWx classes must first be interpreted and normalized using the actual product specification, including excluded classes; NISAR water must be compared with water, not a flood-only mask.

From `backend/`, set `EARTHDATA_TOKEN`, then run `python scripts/61_opera_comparison.py --scan` and `python scripts/61_opera_comparison.py`. The first checks all date-matched BWTR windows; the second verifies checksums, recreates normalized masks, compares all three passes and computes sensitivity without altering the published NISAR product. It checks the baseline against the canonical rhythm and binds results to its manifest hash. The validation API refuses results when that manifest is absent or has changed. Raw downloads stay local and gitignored.

`sensitivity()` excludes invalid pixels represented by NaN and uses the canonical product's verified dB assets, rule, mask and permanent-water settings. The canonical manifest SHA-256 is `b947b54d84f77372536c6202c7e8ac4af2768be2b673a47d8a2ecef2819fedbc`; the mask SHA-256 is `6b029bf1d77e2c7462b3a9070db04a02393033a6aa5d7ef252b665f135fda222`.
