"""Normalize one locally available, explicitly profiled NISAR or ARIA product."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from processing.p3.ingestion import ingest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize one local GUNW HDF5/ARIA NetCDF or GCOV HDF5 product using exact source-profile paths."
    )
    parser.add_argument("event", help="registered event identifier")
    parser.add_argument("--inputs", required=True, help="versioned source manifest JSON; relative product paths resolve beside it")
    parser.add_argument("--output-root", help="published product root (default: backend/data/output)")
    args = parser.parse_args(argv)
    try:
        manifest = ingest(args.event, args.inputs, output_root=args.output_root)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
