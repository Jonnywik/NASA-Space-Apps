# Data manifest

Every dataset used by Tanaw is recorded here with its source, licence, version or date, when it was retrieved, what it is used for, and where its file hashes are kept. Rows are filled by the agent that owns the data. A row is only filled in once it has been checked; until then it says so.

## NISAR (catalogue check)

Collections found through NASA's Common Metadata Repository (CMR) on 15 Nov 2026. Status of every row below: **catalogue verified, files not yet read.**

| Dataset | Provider | CMR concept ID | Version | Notes |
|---|---|---|---|---|
| NISAR L2 GCOV (backscatter) | ASF DAAC | C2854338529-ASF | Provisional | |
| NISAR L2 GCOV (backscatter) | ASF DAAC | C3622241360-ASF | V1 | |
| NISAR L2 GUNW (interferograms) | ASF DAAC | C2854335566-ASF | Provisional | |
| NISAR L2 GUNW (interferograms) | ASF DAAC | C3622247503-ASF | V1 | |

Default track for the flood rhythm: track 133, descending, frame 081. The catalogue lists 10 provisional GCOV dates, 2026-06-23 to 2026-10-21, plus one V1 date, 2026-11-02. Exact acquisition dates and granule names are to be recorded by the owning agent in `backend/data/cache/nisar/` once files are read.

## Full manifest template

| Dataset | Provider | URL | Licence | Version / date | Retrieved at | Used for | Hash / manifest path |
|---|---|---|---|---|---|---|---|
| NISAR GCOV (Provisional and V1) | ASF DAAC | to be filled by the owning agent | to be filled by the owning agent | see table above | not yet retrieved (catalogue verified only) | Flood rhythm, flood masks | `backend/data/cache/nisar/` (to be written) |
| NISAR GUNW (Provisional and V1) | ASF DAAC | to be filled by the owning agent | to be filled by the owning agent | see table above | not yet retrieved (catalogue verified only) | Ground motion | `backend/data/cache/nisar/` (to be written) |
| NASA POWER daily rainfall | to be filled by the owning agent | to be filled by the owning agent | to be filled by the owning agent | to be filled by the owning agent | to be filled by the owning agent | Rainfall context | `backend/data/cache/climate/` (to be written) |
| Open-Meteo seasonal / ERA5 | to be filled by the owning agent | to be filled by the owning agent | to be filled by the owning agent | to be filled by the owning agent | to be filled by the owning agent | Seasonal outlook, comparison rainfall | `backend/data/cache/climate/` (to be written) |
| WorldPop population | to be filled by the owning agent | to be filled by the owning agent | to be filled by the owning agent | to be filled by the owning agent | to be filled by the owning agent | Exposure | `backend/data/cache/places/` (to be written) |
| OpenStreetMap buildings and places | to be filled by the owning agent | to be filled by the owning agent | to be filled by the owning agent | to be filled by the owning agent | to be filled by the owning agent | Exposure, place search | `backend/data/cache/places/` (to be written) |
| ESA WorldCover | to be filled by the owning agent | to be filled by the owning agent | to be filled by the owning agent | to be filled by the owning agent | to be filled by the owning agent | Land cover masks | `backend/data/cache/places/` (to be written) |
| Administrative boundaries (barangay, city) | to be filled by the owning agent | to be filled by the owning agent | to be filled by the owning agent | to be filled by the owning agent | to be filled by the owning agent | Place search, exposure | `backend/data/cache/places/` (to be written) |
| Sentinel-1 (regional context) | to be filled by the owning agent | to be filled by the owning agent | to be filled by the owning agent | to be filled by the owning agent | to be filled by the owning agent | Regional context only, not NISAR | to be filled by the owning agent |
