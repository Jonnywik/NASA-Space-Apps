# Independent validation source review

Reviewed 15 November 2026. Follow-up pixel checks supersede the initial catalogue-only review below.

Seventeen references were within two UTC calendar days of a selected pass. Their BWTR study windows were downloaded and checked against provider MD5 checksums: fourteen contained only fill, while three had usable pixels (G4361329706-POCLOUD, G4361778874-POCLOUD, G4408674689-POCLOUD). The three acquisitions were about 48 hours 15 minutes after NISAR, exceeding a strict 48-hour window. The scan and hashes are in `backend/data/cache/validation/reference_scan.json`; the actual comparisons, sensitivity, reproduction and limitations are in `VALIDATION.md`.

## OPERA DSWx-S1

[PO.DAAC's version 1 collection](https://podaac.jpl.nasa.gov/dataset/OPERA_L3_DSWX-S1_V1) describes Sentinel-1-derived surface water at 30 m, near-global land coverage, 6–12 day revisit, a record starting 1 December 2023, and forward production from September 2024. It maps open inland water bodies greater than 3 hectares and 200 m wide; it is not a ground-truth flood map. A 15 November CMR catalogue search returned 40 granules on tile T51PTS for the bbox and season; 17 were within two calendar days of 10 of the 11 NISAR passes. Pixel checks above narrowed these to three usable windows.

The collection provides a granule listing, download links and a suggested DOI citation. [PO.DAAC's access tutorial](https://forum.earthdata.nasa.gov/viewtopic.php?t=3895) requires an Earthdata Login account for scripted cloud access. NASA's [open-data guidance](https://wiki.earthdata.nasa.gov/spaces/ESDSWG/pages/378738424/A%2BPractical%2BGuide%2Bfor%2BOpen%2BFree%2BFAIR%2BNASA%2BEarth%2BScience%2BData%2BProducts) describes its open-data policy, but does not establish a specific licence for this product. Check collection and granule terms before reuse; the product contains modified Copernicus Sentinel data.

## PhilSA flood maps

[PhilSA's 3 September 2026 announcement](https://philsa.gov.ph/news/satellite-data-show-flood-extents-in-regions-1-2-3-4a-4b-car-and-ncr-due-to-enhanced-habagat/) links maps and shapefiles for 26, 30 and 31 August, including parts of NCR on 26 and 31 August. It describes a Sentinel-1 composite, warns that urban and vegetated flooding can be underestimated, and says the maps require ground validation. Exact CAMANAVA coverage, download accessibility, authentication and reuse terms were not verified; contact PhilSA or inspect the files and their terms before redistribution.

The checked-in track 140 A/frame 009 catalogue selection lists 22 August and 3 September as its adjacent GCOV dates. The published 26, 30 and 31 August map dates are at least three calendar days from either, outside `60_validation.py`'s two-day limit. A different track would need its own verified coverage and dates. Further, mapped flood extent and a total-water raster have different meanings: establish compatible flood-only classes, survey extent and valid dry areas before calculating a confusion matrix.

## Historical motion

[Eco et al. (2020)](https://www.jscimedcentral.com/public/assets/articles/environmentalscience-8-1068.pdf) is open access and reports historical 2003–2011 Envisat/ALOS InSAR results over CAMANAVA, including a maximum 4.2 cm/year subsidence rate. It is contextual evidence, not a coincident ground-truth raster; the article is copyrighted by its authors, so check figure and data reuse terms. Compare only qualitatively after checking reference areas, sign, geometry, period, and vertical versus line-of-sight motion. The paper cannot validate a 2026 four-month NISAR rate directly.

The repository's existing 2022–2025 Sentinel-1 event rasters are earlier regional context, not date-matched references for the 2026 NISAR season. WorldCover 2021 is a static land-cover reference, not independent observed 2026 flood evidence. No suitable already-present independent raster was identified.
