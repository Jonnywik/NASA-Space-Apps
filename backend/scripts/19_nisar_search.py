"""
Script 19: ask NASA's catalogue (CMR) which NISAR GCOV and GUNW granules cover CAMANAVA.

No login is needed and nothing large is downloaded. The result is a small manifest
(title, date, time, URL, size, checksum, collection, maturity) that scripts 20 and 21 read.

Run it (from the backend folder):
    python scripts/19_nisar_search.py                          # contract default stack 133 D, frame 81, mode 4005
    python scripts/19_nisar_search.py --track 32 --direction D --frame 81
    python scripts/19_nisar_search.py --track 140 --direction A --frame 9

The manifest lands in data/cache/nisar/. The printout lists EVERY stack that touches the
bbox with how much of the bbox its catalogue footprint covers, so you can choose.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from processing.nisar_flood import cmr  # noqa: E402
from processing.nisar_flood.constants import (  # noqa: E402
    BACKEND_DIR, DEFAULT_DIRECTION, DEFAULT_FRAME, DEFAULT_MODE, DEFAULT_TRACK, STUDY_BBOX)

CACHE_DIR = BACKEND_DIR / "data" / "cache" / "nisar"


def manifest_name(track, direction, frame, mode):
    return f"nisar_manifest_t{track:03d}_{direction}_f{frame:03d}_m{mode or 'any'}.json"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bbox", type=float, nargs=4, metavar=("W", "S", "E", "N"), default=list(STUDY_BBOX))
    parser.add_argument("--track", type=int, default=DEFAULT_TRACK, help="relative orbit / track number")
    parser.add_argument("--direction", choices=["A", "D"], default=DEFAULT_DIRECTION)
    parser.add_argument("--frame", type=int, default=DEFAULT_FRAME)
    parser.add_argument("--mode", default=DEFAULT_MODE, help="observation mode, e.g. 4005 (use 'any' for all)")
    parser.add_argument("--out", help="manifest path (default: data/cache/nisar/<generated name>)")
    parser.add_argument("--from-cmr-json", help="offline test hook: a JSON file of canned CMR responses {collection: response}")
    args = parser.parse_args(argv)
    mode = None if args.mode == "any" else args.mode

    fetch_json = None
    if args.from_cmr_json:
        canned = json.loads(Path(args.from_cmr_json).read_text())
        def fetch_json(url):  # noqa: E306
            for collection, body in canned.items():
                if collection in url:
                    return body
            return {"hits": 0, "items": []}

    try:
        found = cmr.search(args.bbox, fetch_json=fetch_json)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    manifest = cmr.build_manifest(args.bbox, found, track=args.track, direction=args.direction,
                                  frame=args.frame, mode=mode)

    out = Path(args.out) if args.out else CACHE_DIR / manifest_name(args.track, args.direction, args.frame, mode)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=1) + "\n")

    print(f"Stacks touching the bbox {tuple(args.bbox)} (coverage = share of the bbox inside the catalogue footprint):")
    for row in manifest["trackSummary"]:
        cov = row["bboxCoverageFraction"]
        cov_text = f"{cov['min']:.0%}" if cov and cov["min"] == cov["max"] else (f"{cov['min']:.0%}-{cov['max']:.0%}" if cov else "?")
        count = f"{row['dates']} dates" if row["product"] == "GCOV" else f"{row['pairs']} pairs"
        print(f"  {row['product']} track {row['track']:>3} {row['direction']} frame {row['frame']:>3} mode {row['mode']}: "
              f"{count:>9}, {row['firstDate']}..{row['lastDate']}, coverage {cov_text}, ~{row['typicalSizeGB']} GB each")
    sel = manifest["selection"]
    print(f"\nSelected stack {sel['track']} {sel['direction']} frame {sel['frame']} mode {sel['mode']}: "
          f"{len(sel['gcovDates'])} GCOV dates, {sel['gunwPairs']} GUNW pairs")
    print("  dates:", ", ".join(sel["gcovDates"]))
    total = sum(r["sizeBytes"] or 0 for r in manifest["gcov"])
    print(f"  full GCOV download would be {total / 1e9:.1f} GB; the windowed read fetches a few percent of that")
    for warning in manifest["warnings"]:
        print("WARNING:", warning)
    print("Wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
