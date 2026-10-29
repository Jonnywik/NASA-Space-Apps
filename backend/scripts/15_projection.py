"""Publish reviewed annual LOS and conditional coastal exposure scenarios."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from processing.p3.projection import project  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Publish conditional projections for explicitly reviewed years 2026–2035. "
            "Provide --motion-manifest and --config. LOS-only scenarios may omit "
            "--terrain-manifest; water exposure requires compatible terrain inputs "
            "and reviewed vertical-motion evidence. See projection.py module docs "
            "for the exact JSON v1 schema and inference gate."
        )
    )
    parser.add_argument("event", help="registered event ID")
    parser.add_argument("--motion-manifest", required=True, help="published ground-motion product manifest")
    parser.add_argument("--terrain-manifest", help="optional prepared scenario-inputs manifest (required for exposure)")
    parser.add_argument("--config", required=True, help="reviewed projection scenario JSON; auxiliary rasters resolve relative to it")
    parser.add_argument("--output-root", help="product root (default: backend/data/output)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        path = project(
            args.event, args.motion_manifest, args.terrain_manifest,
            args.config, output_root=args.output_root,
        )
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Published projection manifest: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
