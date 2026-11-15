"""Script 24: save only the study-area window of each NISAR GUNW pair, instead of downloading 2.3 GB files.

For every GUNW row in a script-19 manifest, this reads (by HTTP range requests, needs EARTHDATA_TOKEN)
the coordinates, projection and the HH unwrappedPhase / coherenceMagnitude / connectedComponents /
ionospherePhaseScreen layers inside the study bbox (plus a margin), plus the frequencyA centreFrequency, and
writes them to <raw-dir>/<granule title>.h5 with the same internal paths. Script 21 and scripts 10-12 then
treat these files like the originals. Each subset records its source URL, MD5 of the full granule and the
window in HDF5 attributes; it is a windowed copy, so its own SHA-256 differs from the full granule.

Usage (from backend/):
    python scripts/24_nisar_gunw_subset.py --manifest data/cache/nisar/nisar_manifest_t140_A_f009_m4005.json
"""
import argparse
import json
import sys
from pathlib import Path

import h5py
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from processing.nisar_flood import remote  # noqa: E402
from processing.nisar_flood.constants import STUDY_BBOX  # noqa: E402
from processing.nisar_flood.gcov import _read_crs  # noqa: E402
from processing.nisar_flood.constants import GcovLayout  # noqa: E402
from processing.nisar_flood.geo import window_for_bbox  # noqa: E402
from processing.nisar_flood.gunw_chain import GUNW_BASE, GUNW_POL, local_name  # noqa: E402

BACKEND = Path(__file__).resolve().parent.parent
LAYERS = ("unwrappedPhase", "coherenceMagnitude", "connectedComponents", "ionospherePhaseScreen")
FREQ = "/science/LSAR/GUNW/grids/frequencyA/centerFrequency"


def copy_attrs(src, dst):
    for k, v in src.attrs.items():
        if k in ("DIMENSION_LIST", "REFERENCE_LIST", "CLASS", "NAME"):
            continue
        try:
            dst.attrs[k] = v
        except (TypeError, ValueError):
            pass


def subset(row: dict, out_dir: Path, pad: int) -> Path:
    out = out_dir / local_name(row)
    if out.exists():
        print(f"  exists: {out.name}")
        return out
    with h5py.File(remote.HttpRangeFile(row["url"]), "r") as src:
        x = src[f"{GUNW_BASE}/xCoordinates"][...]
        y = src[f"{GUNW_BASE}/yCoordinates"][...]
        layout = GcovLayout(base=GUNW_BASE, projection="projection", x="xCoordinates", y="yCoordinates")
        crs, _ = _read_crs(src, layout)
        rows, cols, _, _ = window_for_bbox(x, y, crs, STUDY_BBOX, pad=pad)
        tmp = out.with_suffix(".part")
        with h5py.File(tmp, "w") as dst:
            g = dst.require_group(GUNW_BASE)
            for name, arr in (("xCoordinates", x[cols]), ("yCoordinates", y[rows])):
                d = g.create_dataset(name, data=arr)
                copy_attrs(src[f"{GUNW_BASE}/{name}"], d)
            for name in ("projection", "xCoordinateSpacing", "yCoordinateSpacing"):
                if f"{GUNW_BASE}/{name}" in src:
                    d = g.create_dataset(name, data=src[f"{GUNW_BASE}/{name}"][()])
                    copy_attrs(src[f"{GUNW_BASE}/{name}"], d)
            pg = g.require_group(GUNW_POL)
            for name in LAYERS:
                s = src[f"{GUNW_BASE}/{GUNW_POL}/{name}"]
                d = pg.create_dataset(name, data=s[rows, cols], compression="gzip")
                copy_attrs(s, d)
            if FREQ in src:
                d = dst.create_dataset(FREQ, data=src[FREQ][()])
                copy_attrs(src[FREQ], d)
            dst.attrs["tanawSubsetOf"] = row["title"]
            dst.attrs["tanawSourceUrl"] = row["url"]
            dst.attrs["tanawSourceMd5"] = row.get("md5") or ""
            dst.attrs["tanawWindow"] = json.dumps({"rowStart": rows.start, "rowStop": rows.stop,
                                                   "colStart": cols.start, "colStop": cols.stop, "crs": str(crs)})
        tmp.rename(out)
    print(f"  wrote {out.name} ({out.stat().st_size / 1e6:.1f} MB, window {rows.stop - rows.start}x{cols.stop - cols.start})")
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--manifest", required=True)
    p.add_argument("--raw-dir", default=str(BACKEND / "data" / "raw" / "nisar" / "gunw"))
    p.add_argument("--pad", type=int, default=16, help="extra 80 m pixels around the study bbox")
    a = p.parse_args(argv)
    remote.get_token()  # fails early with a clear message if EARTHDATA_TOKEN is missing
    m = json.loads(Path(a.manifest).read_text())
    out_dir = Path(a.raw_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, row in enumerate(m["gunw"], 1):
        print(f"[{i}/{len(m['gunw'])}] {row['referenceDate']} -> {row['secondaryDate']}")
        subset(row, out_dir, a.pad)


if __name__ == "__main__":
    main()
