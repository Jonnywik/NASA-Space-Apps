"""Publish a deterministic text briefing from a hash-checked P3 manifest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from processing.p3.briefing import generate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a deterministic P3 briefing JSON product.")
    parser.add_argument("event", help="registered event ID")
    parser.add_argument("--manifest", required=True, help="published product manifest JSON")
    parser.add_argument("--region-id", default="whole-event", help="whole-event or a registered regional summary ID")
    parser.add_argument("--year", type=int, help="required when selecting one year from a multi-year projection")
    parser.add_argument("--exposure", help="optional hash-checked exposure snapshot manifest")
    parser.add_argument("--output-root", help="product root (default: backend/data/output)")
    args = parser.parse_args(argv)
    try:
        path = generate(args.event, args.manifest, args.region_id, args.exposure, args.output_root, args.year)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Published briefing manifest: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
