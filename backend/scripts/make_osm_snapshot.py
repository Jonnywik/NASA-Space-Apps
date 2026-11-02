#!/usr/bin/env python3
"""Make a dated OSM building snapshot for scripts/08_building_exposure.py.

Run from backend/ with the venv active (needs: pip install osmnx>=2):

  python scripts/make_osm_snapshot.py --bbox 120.80 14.80 120.90 14.90 ^
         --out data/work/osm/pilot --data-kind <VALUE FROM THE CODE> --completeness partial

--bbox is WEST SOUTH EAST NORTH in degrees (lon/lat). Start SMALL (about 0.1 x 0.1 degrees);
big areas can time out and use a lot of RAM.

It writes <out>/buildings.geojson and <out>/snapshot.json. The snapshot.json field names follow
backend/DREI_P2_PIPELINE.md; if 08 complains about a key, fix the JSON by hand (or send Adz the error).
Data (c) OpenStreetMap contributors (ODbL) - credit them wherever the numbers are shown.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("W", "S", "E", "N"))
    p.add_argument("--out", required=True)
    p.add_argument("--data-kind", required=True, help="exact dataKind value the backend accepts for real data")
    p.add_argument("--completeness", choices=["complete", "partial", "unknown"], default="partial")
    p.add_argument("--source-date", default=datetime.now(timezone.utc).date().isoformat())
    a = p.parse_args()
    w, s, e, n = a.bbox
    if not (w < e and s < n):
        sys.exit("bbox must be WEST SOUTH EAST NORTH with west < east and south < north")
    if (e - w) * (n - s) > 0.05:
        print("WARNING: that area is big. If the download times out, use a smaller bbox.")

    import osmnx as ox
    import geopandas as gpd
    if int(ox.__version__.split(".")[0]) < 2:
        sys.exit("Need osmnx 2.x:  pip install -U osmnx")

    print("Downloading buildings from OpenStreetMap (can take a few minutes)...")
    g = ox.features_from_bbox(bbox=(w, s, e, n), tags={"building": True}).reset_index()
    g = g[g.geometry.geom_type.isin(["Polygon", "MultiPolygon"]) & g["element"].isin(["way", "relation"])]
    g = g[~g.geometry.is_empty & g.geometry.notna()].copy()
    out = gpd.GeoDataFrame(
        {"osmType": g["element"].astype(str).values, "osmId": g["id"].astype("int64").values},
        geometry=g.geometry.values, crs="EPSG:4326")
    out = out[out["osmId"] > 0].drop_duplicates(subset=["osmType", "osmId"])
    if out.empty:
        sys.exit("No buildings came back for that box. Check the numbers (WEST SOUTH EAST NORTH).")

    folder = Path(a.out)
    folder.mkdir(parents=True, exist_ok=True)
    gj = folder / "buildings.geojson"
    out.to_file(gj, driver="GeoJSON")
    sha = hashlib.sha256(gj.read_bytes()).hexdigest()
    cfg = {
        "schemaVersion": "1.0",
        "dataKind": a.data_kind,
        "sourceDate": a.source_date,
        "source": f"OpenStreetMap contributors via Overpass API (osmnx {ox.__version__})",
        "provenance": f"Downloaded {datetime.now(timezone.utc).isoformat(timespec='seconds')} with scripts/make_osm_snapshot.py",
        "geojsonPath": gj.name,
        "geojsonCrs": "EPSG:4326",
        "sha256": sha,
        "coverage": {
            "geometry": {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]},
            "crs": "EPSG:4326",
            "completeness": a.completeness,
        },
    }
    (folder / "snapshot.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"{len(out)} buildings saved. Wrote {gj} and {folder / 'snapshot.json'}")
    print(f"completeness = {a.completeness}. Only say 'complete' if you checked OSM against another source.")


if __name__ == "__main__":
    main()
