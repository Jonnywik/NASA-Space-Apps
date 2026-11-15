"""Calculate priority-zone exposure from flood rhythm and a ground-motion product."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from processing.p3.core import OUTPUT_ROOT
from processing.priority.zones import build_priority


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', default=str(OUTPUT_ROOT))
    parser.add_argument('--event', default='camanava_2026')
    parser.add_argument('--run-id', help='ground-motion run ID (default: current reviewed product)')
    parser.add_argument('--threshold-mm', type=float, help='explicit positive-away displacement threshold')
    parser.add_argument('--reference-mask', help='original reference mask, when the LOS pair used a mask raster')
    args = parser.parse_args(argv)
    try:
        result = build_priority(args.output_root, args.event, run_id=args.run_id,
                                threshold_mm=args.threshold_mm, reference_mask=args.reference_mask)
    except (OSError, ValueError, KeyError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2
    print(f"Priority mask written: {Path(args.output_root) / args.event / 'nisar' / 'priority_mask.tif'} ({result['dataKind']})")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
