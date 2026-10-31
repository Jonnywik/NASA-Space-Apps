"""Prepare aligned P3 elevation and water-level scenario inputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Running as a script adds only backend/scripts to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from processing.p3.terrain import CompatibilityError, prepare_inputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate and align local DEM, coastal-mask and water-level inputs for P3 scenarios."
    )
    parser.add_argument("event", help="event ID used in the published product path")
    parser.add_argument("--inputs", required=True, help="scenario input JSON; raster paths resolve relative to this file")
    parser.add_argument("--output-root", help="product root (default: backend/data/output)")
    args = parser.parse_args(argv)
    try:
        manifest = prepare_inputs(args.event, args.inputs, output_root=args.output_root)
    except CompatibilityError as exc:
        print(json.dumps(exc.report, indent=2, sort_keys=True), file=sys.stderr)
        return 2
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
