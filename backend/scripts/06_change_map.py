"""Create a coherence decrease mask and map from a prepared event pair."""

import argparse
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from processing.coherence_change import ChangeMapError, create_change_map  # noqa: E402


def _native_resolutions(sources):
    found = []
    if not isinstance(sources, dict):
        return found
    for pair_name in ("pre", "co"):
        pair = sources.get(pair_name)
        resolution = pair.get("nativeResolutionMetres") if isinstance(pair, dict) else None
        if isinstance(resolution, dict):
            try:
                x_resolution = float(resolution["x"])
                y_resolution = float(resolution["y"])
            except (KeyError, TypeError, ValueError):
                continue
            found.append(f"{pair_name} {x_resolution:g} × {y_resolution:g} m")
        elif resolution is not None:
            try:
                found.append(f"{pair_name} {float(resolution):g} m")
            except (TypeError, ValueError):
                continue
    return found


def _parser():
    parser = argparse.ArgumentParser(
        description="Map coherence decrease between a pre-event and event-spanning pair."
    )
    parser.add_argument("event_id", help="registered event id")
    parser.add_argument("--input-dir", help="directory containing coh_pre.tif, coh_co.tif, and coherence_info.json")
    parser.add_argument("--output-dir", help="destination for change outputs (default: data/output/<event>)")
    parser.add_argument("--pre-min", type=float, default=0.5, help="minimum smoothed pre coherence in [0, 1]")
    parser.add_argument("--loss-min", type=float, default=0.3, help="minimum smoothed pre-minus-event loss in (0, 1]")
    parser.add_argument("--min-pixels", type=int, default=10, help="minimum 8-connected component size (default 10)")
    parser.add_argument("--simplify", type=float, default=15.0, help="display polygon simplification tolerance in metres")
    parser.add_argument("--overwrite", action="store_true", help="replace existing change outputs")
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        metadata = create_change_map(
            event_id=args.event_id,
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            pre_min=args.pre_min,
            loss_min=args.loss_min,
            min_pixels=args.min_pixels,
            simplify=args.simplify,
            overwrite=args.overwrite,
        )
    except ChangeMapError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # Keep malformed input failures concise for command-line users.
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    coverage = metadata["coverage"]
    aoi_count = coverage["aoiPixelCount"]
    common_count = coverage["commonValidPixelCount"]
    eligible_count = coverage["eligiblePixelCount"]
    common_percent = coverage["commonValidCoveragePercent"]
    eligible_percent = coverage["eligibleCoveragePercent"]
    print(f"Common valid coverage: {common_count}/{aoi_count} AOI pixels ({common_percent:.2f}%)")
    print(f"Eligible coverage: {eligible_count}/{aoi_count} AOI pixels ({eligible_percent:.2f}%)")

    native = _native_resolutions(metadata.get("sources", {}))
    native_text = ", ".join(native) if native else "not recorded"
    output_resolution = metadata["grid"]["resolutionMetres"]
    print(f"Native source resolution: {native_text}; output resolution: {output_resolution:g} m/pixel")
    for warning in metadata.get("warnings", []):
        print(f"Warning: {warning}")
    print(f"Changed area: {metadata['stats']['km2Changed']:.6f} km²")
    print("Saved: change_mask.tif, change.geojson, change_extent.json, 06_change_check.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
