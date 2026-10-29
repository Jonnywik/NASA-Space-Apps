"""Reconstruct and publish a ground-motion time series from LOS-pair products."""

import argparse
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from processing.p3.series import build_series  # noqa: E402


def _parser():
    parser = argparse.ArgumentParser(
        description='Reconstruct acquisition displacements and annual rates from LOS-pair manifests.'
    )
    parser.add_argument('event_id', help='registered event id')
    parser.add_argument('--pair', action='append', required=True, dest='pairs',
                        help='LOS-pair manifest path; repeat for every acquisition pair')
    parser.add_argument('--output-root', help='product root (default: backend/data/output)')
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        manifest_path = build_series(args.event_id, args.pairs, output_root=args.output_root)
    except Exception as exc:  # Keep malformed inputs concise for command-line users.
        print(f'Error: {exc}', file=sys.stderr)
        return 2
    print(f'Published ground-motion manifest: {manifest_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
