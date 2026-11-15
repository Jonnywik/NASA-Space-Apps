"""
Script 20: NISAR flood rhythm for CAMANAVA (N1, N2, N4, N5), from the script-19 manifest.

Steps: read the study window of each GCOV pass (HH, HV) -> dB -> one fixed water rule ->
permanent water -> flood rhythm, possible flooded vegetation, polarization RGB -> PNG/GeoTIFF/manifest.

Typical laptop run (see docs/NISAR_RUNBOOK.md):
    export EARTHDATA_TOKEN=...            # never commit this
    python scripts/20_nisar_flood_rhythm.py --manifest data/cache/nisar/nisar_manifest_t032_D_f081_m4005.json \\
        --max-dates 2 --calibrate         # first, a 2-date trial
    python scripts/20_nisar_flood_rhythm.py --manifest ... --rule-file data/output/camanava_2026/nisar/water_rule.json

Local files instead of remote reads:
    python scripts/20_nisar_flood_rhythm.py --manifest ... --local-dir data/raw/nisar/gcov

Output: data/output/camanava_2026/nisar/  (replaces the previous product, synthetic or real)
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from processing.nisar_flood import pipeline, remote, water  # noqa: E402
from processing.nisar_flood.constants import (  # noqa: E402
    DEFAULT_HH_THRESHOLD_DB, DEFAULT_HV_THRESHOLD_DB, DEFAULT_LAYOUT, DEFAULT_MIN_VALID_PASSES,
    DEFAULT_PERMANENT_FRACTION, DEFAULT_VEGETATION_LANDCOVER_CLASSES, DEFAULT_VEGETATION_MARGIN_DB, STUDY_BBOX, GcovLayout)
from processing.nisar_flood.gcov import LayoutError  # noqa: E402


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--manifest", required=True, help="CMR manifest JSON written by script 19")
    p.add_argument("--out-dir", default=str(pipeline.OUTPUT_DIR), help="product folder (default: data/output/camanava_2026/nisar)")
    src = p.add_argument_group("where the pixels come from")
    src.add_argument("--local-dir", help="folder holding <granule title>.h5 files; default is to read remotely from the URLs in the manifest")
    src.add_argument("--allow-download", action="store_true", help="if a remote range read fails, download the whole file to data/raw/nisar/")
    src.add_argument("--max-dates", type=int, help="only the first N dates (trial runs)")
    src.add_argument("--dates", help="comma-separated YYYY-MM-DD subset")
    src.add_argument("--no-cache", action="store_true", help="ignore cached windows in data/raw/nisar_windows/")
    src.add_argument("--dry-run", action="store_true", help="list what would be read and exit")
    rule = p.add_argument_group("water rule (one rule for all dates)")
    rule.add_argument("--hh-threshold", type=float, default=DEFAULT_HH_THRESHOLD_DB, help="HH dB below which a pixel can be water")
    rule.add_argument("--hv-threshold", type=float, default=DEFAULT_HV_THRESHOLD_DB, help="HV dB below which a pixel can be water")
    rule.add_argument("--calibrate", action="store_true", help="derive both thresholds from the Manila Bay box on the passes read, then record them")
    rule.add_argument("--rule-file", help="reuse a saved rule (water_rule.json) so later runs use the same thresholds")
    rule.add_argument("--speckle-window", type=int, default=3, help="boxcar size (px) applied to linear power; 1 = off")
    perm = p.add_argument_group("permanent water, rhythm, vegetation")
    perm.add_argument("--permanent-fraction", type=float, default=DEFAULT_PERMANENT_FRACTION)
    perm.add_argument("--min-valid-passes", type=int, default=DEFAULT_MIN_VALID_PASSES)
    perm.add_argument("--permanent-mask", help="optional GeoTIFF of known permanent water (value > 0)")
    perm.add_argument("--landcover", help="optional GeoTIFF of ESA WorldCover classes to restrict possible flooded vegetation")
    perm.add_argument("--landcover-classes", default=",".join(str(c) for c in DEFAULT_VEGETATION_LANDCOVER_CLASSES))
    perm.add_argument("--veg-margin-db", type=float, default=DEFAULT_VEGETATION_MARGIN_DB)
    lay = p.add_argument_group("HDF5 layout (verify on the first real file)")
    lay.add_argument("--layout-base", default=DEFAULT_LAYOUT.base)
    lay.add_argument("--layout-hh", default=DEFAULT_LAYOUT.hh)
    lay.add_argument("--layout-hv", default=DEFAULT_LAYOUT.hv)
    lay.add_argument("--layout-mask", default=None, help="optional validity dataset name under the base group (value > 0 is valid)")
    lay.add_argument("--coordinates-are", choices=["center", "edge"], default=DEFAULT_LAYOUT.coordinates_are)
    lay.add_argument("--crs-fallback", default=None, help="CRS to use if the file has no EPSG attribute, e.g. EPSG:32651")
    lay.add_argument("--layout-verified", action="append", default=[], metavar="EVIDENCE",
                     help="record that dataset paths/units/CRS were checked on a real file; give the evidence text (repeatable)")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text())
    layout = GcovLayout(base=args.layout_base, hh=args.layout_hh, hv=args.layout_hv, mask=args.layout_mask,
                        coordinates_are=args.coordinates_are, crs_fallback=args.crs_fallback)
    dates = [d.strip() for d in args.dates.split(",")] if args.dates else None

    rows = manifest["gcov"]
    if dates:
        rows = [r for r in rows if r["date"] in dates]
    if args.max_dates:
        rows = rows[:args.max_dates]
    sel = manifest["selection"]
    print(f"Stack {sel['track']} {sel['direction']} frame {sel['frame']} mode {sel['mode']}: {len(rows)} pass(es)")
    for w in manifest.get("warnings", []):
        print("  manifest warning:", w)
    if args.dry_run:
        for r in rows:
            print(f"  {r['date']}  {r['maturity']:<11} {(r['sizeBytes'] or 0) / 1e9:5.2f} GB  {r['title']}")
        return 0

    token = None if args.local_dir else remote.get_token()
    if not args.local_dir and not token:
        print("error: EARTHDATA_TOKEN is not set (and no --local-dir given). See docs/NISAR_RUNBOOK.md, step 1.", file=sys.stderr)
        return 2
    try:
        passes = pipeline.passes_from_cmr_manifest(
            manifest, max_dates=args.max_dates, dates=dates, local_dir=Path(args.local_dir) if args.local_dir else None,
            token=token, allow_download=args.allow_download, layout=layout, speckle_window=args.speckle_window,
            reuse_cache=not args.no_cache)
        rule = water.WaterRule(args.hh_threshold, args.hv_threshold)
        if args.rule_file:
            rule = pipeline.load_rule(Path(args.rule_file))
        analysis = pipeline.analyse(
            passes, bbox=STUDY_BBOX, rule=rule, calibrate=args.calibrate, permanent_fraction=args.permanent_fraction,
            min_valid_passes=args.min_valid_passes, permanent_mask_path=Path(args.permanent_mask) if args.permanent_mask else None,
            landcover_path=Path(args.landcover) if args.landcover else None,
            landcover_classes=[int(c) for c in args.landcover_classes.split(",") if c],
            vegetation_margin_db=args.veg_margin_db)
    except (remote.AuthError, remote.RemoteError, LayoutError, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    verification = ({"layout": "verified", "evidence": args.layout_verified} if args.layout_verified
                    else {"layout": "unverified", "evidence": []})
    extra = [] if args.layout_verified else [
        "HDF5 dataset paths, units and CRS have not been verified on a real file for this run (use --layout-verified after checking)."]
    track = {k: sel[k] for k in ("track", "direction", "frame", "mode")}
    track["bboxCoverageFractionCatalogue"] = sorted({r.get("bboxCoverageFraction") for r in manifest["gcov"] if r.get("bboxCoverageFraction") is not None})
    source = {"name": pipeline.SOURCE_INFO["name"], "url": pipeline.SOURCE_INFO["url"],
              "version": sorted({r["collectionShortName"] + " " + str(r.get("productVersion")) for r in manifest["gcov"]
                                 if r["date"] in {p.date for p in passes}}),
              "cmrManifest": manifest_path.name,
              "cmrManifestSha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(), "cmrRetrievedAt": manifest["retrievedAt"]}
    provenance = {"layout": layout.__dict__, "speckleWindow": args.speckle_window,
                  "permanentWaterMaskSha256": hashlib.sha256(Path(args.permanent_mask).read_bytes()).hexdigest() if args.permanent_mask else None,
                  "accessModes": sorted({p.source["access"]["mode"] for p in passes}), "options": {k: v for k, v in vars(args).items() if k != "manifest"}}
    out_dir = Path(args.out_dir)
    path = pipeline.export_product(analysis, out_dir, data_kind="observed", source=source, extra_warnings=extra,
                                   provenance=provenance, verification=verification, track=track)
    pipeline.save_rule(out_dir / "water_rule.json", analysis.rule)
    print("\nWrote", path)
    print(f"  rule: HH < {analysis.rule.hh_db} dB and HV < {analysis.rule.hv_db} dB ({analysis.rule.calibration.get('status')})")
    for p, s in zip(analysis.passes, analysis.pass_stats):
        print(f"  {p.date}: flooded {s['floodedKm2']:.2f} km2, valid {s['validFraction']:.0%} of the study area")
    print(f"  flooded on half or more of valid passes: {analysis.rhythm_stats['halfOrMoreKm2']:.2f} km2")
    for w in analysis.warnings:
        print("  WARNING:", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
