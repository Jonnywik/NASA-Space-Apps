"""
Script 21: prepare (and optionally run) the GUNW chain for NISAR ground motion (N3) with scripts 10, 11 and 12.

It reads the script-19 manifest and writes, for event camanava_2026:
  - one script-10 source manifest per GUNW pair (ingest_<ref>_<sec>.json)
  - one script-11 reference config (reference_<stack>.json)
  - run_gunw_chain.sh, which runs 10 -> 11 for every pair and then 12
into data/raw/nisar/gunw_chain/<stack>/ (git-ignored: it holds machine-specific paths and hashes).

Steps on the laptop (see docs/NISAR_RUNBOOK.md):
    python scripts/21_nisar_gunw_chain.py --manifest data/cache/nisar/nisar_manifest_t032_D_f081_m4005.json --download --max-pairs 2
    python scripts/21_nisar_gunw_chain.py --manifest ... --fill-hashes --phase-sign <+1|-1> --reference-bbox W S E N
    bash data/raw/nisar/gunw_chain/t032_D_f081/run_gunw_chain.sh        # or add --execute here

Things this script refuses to guess: the sign convention of the unwrapped phase (--phase-sign) and the stable reference area
(--reference-bbox). Without them the written configs make scripts 10/11 stop with a clear message, and --execute refuses to run.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from processing.nisar_flood import gunw_chain, remote  # noqa: E402
from processing.nisar_flood.constants import BACKEND_DIR, STUDY_BBOX  # noqa: E402

RAW_GUNW = BACKEND_DIR / "data" / "raw" / "nisar" / "gunw"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--manifest", required=True, help="CMR manifest JSON written by script 19")
    p.add_argument("--out-dir", help="default: data/raw/nisar/gunw_chain/<stack>")
    p.add_argument("--raw-dir", default=str(RAW_GUNW), help="where GUNW .h5 files are (or will be downloaded)")
    p.add_argument("--max-pairs", type=int, help="only the first N pairs")
    p.add_argument("--download", action="store_true", help="download the GUNW files (~2.2 GB each; needs EARTHDATA_TOKEN)")
    p.add_argument("--fill-hashes", action="store_true", help="compute SHA-256 of local files and read CRS and window from them")
    p.add_argument("--phase-sign", type=int, choices=[-1, 1], help="+1 if positive unwrapped phase means motion away from the satellite, -1 if toward. Check the product spec.")
    p.add_argument("--corrections-applied", action="append", default=[], help="name of a correction the product already applied (repeatable)")
    p.add_argument("--ionosphere-sign", choices=["same_as_phase", "opposite_phase"], help="register the ionosphere phase screen as an available correction")
    p.add_argument("--reference-bbox", type=float, nargs=4, metavar=("W", "S", "E", "N"), help="stable reference area (lon/lat) chosen by a person")
    p.add_argument("--gunw-base", default=gunw_chain.GUNW_BASE)
    p.add_argument("--gunw-pol", default=gunw_chain.GUNW_POL)
    p.add_argument("--execute", action="store_true", help="run 10 -> 11 -> 12 in-process once nothing is blocking")
    p.add_argument("--output-root", help="P3 output root (default: data/output)")
    args = p.parse_args(argv)

    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text())
    sel = manifest["selection"]
    label = f"t{sel['track']:03d}_{sel['direction']}_f{sel['frame']:03d}"
    out_dir = Path(args.out_dir) if args.out_dir else BACKEND_DIR / "data" / "raw" / "nisar" / "gunw_chain" / label
    raw_dir = Path(args.raw_dir)
    rows = manifest["gunw"][:args.max_pairs] if args.max_pairs else manifest["gunw"]

    if args.download:
        token = remote.get_token()
        if not token:
            print("error: EARTHDATA_TOKEN is not set. See docs/NISAR_RUNBOOK.md, step 1.", file=sys.stderr)
            return 2
        for i, row in enumerate(rows, start=1):
            print(f"[{i}/{len(rows)}] {row['referenceDate']} -> {row['secondaryDate']}  {(row['sizeBytes'] or 0) / 1e9:.2f} GB")
            try:
                remote.download(row["url"], raw_dir, token, expected_md5=row.get("md5"), expected_size=row.get("sizeBytes"),
                                progress=remote.print_progress)
            except (remote.AuthError, remote.RemoteError) as exc:
                print(f"\nerror: {exc}", file=sys.stderr)
                return 2
            print()

    paths = gunw_chain.gunw_paths(args.gunw_base, args.gunw_pol)
    try:
        summary = gunw_chain.write_chain(
            manifest, out_dir, raw_dir, paths=paths, phase_sign=args.phase_sign, corrections_applied=args.corrections_applied,
            ionosphere_sign=args.ionosphere_sign, fill_hashes=args.fill_hashes,
            reference_bbox=tuple(args.reference_bbox) if args.reference_bbox else None, max_pairs=args.max_pairs, bbox=STUDY_BBOX)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {len(summary['ingestConfigs'])} ingest configs, {summary['referenceConfig']} and {summary['shellScript']} in {out_dir}")
    if summary["chainGaps"]:
        print("WARNING: pairs do not chain without gaps:", summary["chainGaps"])
    problems = gunw_chain.blocking_problems(summary)
    for problem in problems:
        print("  to do:", problem)
    if not args.execute:
        print("Run the chain with:  bash", out_dir / "run_gunw_chain.sh", "(from the backend folder), or re-run this script with --execute")
        return 0
    if problems:
        print("error: refusing to --execute while the items above are open.", file=sys.stderr)
        return 2

    from processing.p3.ingestion import ingest
    from processing.p3.phase import convert
    from processing.p3.series import build_series
    root = args.output_root
    los = []
    for name in summary["ingestConfigs"]:
        gunw_manifest = ingest(gunw_chain.EVENT, out_dir / name, output_root=root)
        los.append(str(convert(gunw_chain.EVENT, gunw_manifest, out_dir / summary["referenceConfig"], output_root=root)))
        print("  pair done:", name)
    print("Ground-motion manifest:", build_series(gunw_chain.EVENT, los, output_root=root))
    print("Review it and promote it (scripts/17_review_product.py) before the P3 API will serve real data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
