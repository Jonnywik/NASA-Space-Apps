"""Convert a normalized GUNW phase pair to a referenced LOS displacement raster."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Running this script by path only puts the scripts directory on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from processing.p3.phase import convert


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reference radians of unwrapped GUNW phase and publish LOS displacement in millimetres."
    )
    parser.add_argument("event", help="registered event ID carried by the input manifest")
    parser.add_argument("--inputs", required=True, help="normalized GUNW input manifest")
    parser.add_argument("--config", required=True, help="reference and optional phase correction JSON config")
    parser.add_argument("--output-root", help="P3 output root (default: backend/data/output)")
    args = parser.parse_args(argv)

    try:
        convert(args.event, args.inputs, args.config, output_root=args.output_root)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
