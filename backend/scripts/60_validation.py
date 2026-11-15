"""Compare two normalized observed water rasters, supplied with provenance."""
import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from processing.validation.metrics import compare_rasters


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nisar", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--provenance", required=True, type=Path,
                        help="JSON with nisar and reference objects: dataKind, date, source and url")
    parser.add_argument("--out", type=Path, default=Path("data/cache/validation/camanava_2026.json"))
    args = parser.parse_args()
    provenance = json.loads(args.provenance.read_text(encoding="utf-8"))
    for name in ("nisar", "reference"):
        item = provenance[name]
        if item.get("dataKind") not in ("observed", "derived") or not item.get("source") or not item.get("url"):
            parser.error(f"{name} needs observed/derived dataKind, source and URL; synthetic is rejected")
    if provenance["nisar"]["url"] == provenance["reference"]["url"]:
        parser.error("The reference must identify a distinct independent source")
    dates = [date.fromisoformat(provenance[name]["date"]) for name in ("nisar", "reference")]
    if abs((dates[0] - dates[1]).days) > 2:
        parser.error("Acquisition dates must be within two days")
    metrics = compare_rasters(args.nisar, args.reference)
    if not metrics["validPixels"]:
        parser.error("No jointly valid pixels")
    result = {"area": "camanava_2026", "status": "partial", "dataKind": "derived",
              "source": provenance, "generatedAt": datetime.now(timezone.utc).isoformat(),
              "nativeResolution": "coarser common raster grid",
              "units": {"agreement": "fraction", "validPixels": "pixels"},
              "agreement": metrics, "sensitivity": None,
              "warnings": ["Threshold sensitivity and ground-motion comparison are not included."],
              "limitations": ["Nearest-neighbour comparison is on the coarser raster grid; acquisitions can be up to two days apart.",
                              "Agreement with another satellite product is not ground truth."]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
