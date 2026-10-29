"""Publish detection frequency from normalized coherence-change products."""

import argparse
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from processing.change_frequency import build_frequency  # noqa: E402


def _parser():
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate compatible coherence-change masks into a fraction of valid comparisons "
            "with detected change. The frequency is descriptive, not an independent probability."
        ),
        epilog=(
            "Inputs are core product manifests with product='coherence-change', comparisonId, prePair, "
            "coPair, parameters, grid, sources, dataKind, sourceRunIds, and hash-verified "
            "changeMask/changeGeometry assets. Valid changeMask cells must be 0 or 1; nodata is ignored. "
            "Masks are aligned with nearest-neighbor resampling to the coarsest input resolution over "
            "the union extent. All input grids must use the same CRS. Pixels need at least two valid "
            "comparisons by default."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("event_id", help="registered event id shared by all input products")
    parser.add_argument(
        "--comparison", "--manifest", action="append", required=True, dest="manifests",
        metavar="PATH", help="normalized coherence-change manifest; repeat once per comparison",
    )
    parser.add_argument("--output-root", help="product root (default: backend/data/output)")
    parser.add_argument(
        "--minimum-observations", type=int, default=2,
        help="minimum number of valid comparison masks required for a frequency value (default: 2)",
    )
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        manifest_path = build_frequency(
            args.event_id,
            args.manifests,
            output_root=args.output_root,
            minimum_observations=args.minimum_observations,
        )
    except Exception as exc:  # Keep malformed input and publication failures concise for CLI users.
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(f"Published change-frequency manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
