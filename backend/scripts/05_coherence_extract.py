"""Extract and align paired InSAR coherence rasters for a registered event."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Running this file as ``python scripts/05_coherence_extract.py`` puts only the
# scripts directory on sys.path, so add backend to make processing importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from processing.coherence_io import extract_pair


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate paired coherence products and write aligned coh_pre/coh_co GeoTIFFs."
    )
    parser.add_argument("event", help="registered event ID, for example carina_2024")
    parser.add_argument("--inputs", required=True, help="pair manifest JSON (relative sources resolve from this file)")
    parser.add_argument("--resolution", type=float, help="optional output pixel size in metres; cannot be finer than native default")
    parser.add_argument("--output-dir", help="destination directory (default: data/output/<event>)")
    parser.add_argument("--overwrite", action="store_true", help="replace this extractor's existing output files")
    args = parser.parse_args(argv)

    try:
        extract_pair(
            args.event,
            args.inputs,
            output_dir=args.output_dir,
            resolution=args.resolution,
            overwrite=args.overwrite,
        )
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
