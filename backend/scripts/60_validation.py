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
    calendar_days = abs((dates[0] - dates[1]).days)
    if calendar_days > 2:
        parser.error("Acquisition dates must be within two days")
    times = []
    for name, day in zip(("nisar", "reference"), dates):
        value = provenance[name].get("acquisitionTime")
        if value is None:
            times.append(None)
            continue
        try:
            instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if instant.utcoffset() is None or instant.astimezone(timezone.utc).date() != day:
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            parser.error(f"{name} acquisitionTime must have a timezone and match its UTC date")
        times.append(instant)
    elapsed = abs((times[0] - times[1]).total_seconds()) / 3600 if all(times) else None
    metrics = compare_rasters(args.nisar, args.reference)
    if not metrics["validPixels"]:
        parser.error("No jointly valid pixels")
    result = {"area": "camanava_2026", "status": "partial", "dataKind": "derived",
              "source": provenance, "generatedAt": datetime.now(timezone.utc).isoformat(),
              "nativeResolution": "coarser common raster grid",
              "units": {"agreement": "fraction", "validPixels": "pixels"},
              "temporalMatch": {"calendarDays": calendar_days, "elapsedHours": elapsed,
                                "within48Hours": elapsed <= 48 if elapsed is not None else None},
              "comparison": "NISAR total open water versus DSWx total water including inundated vegetation; not flood-only accuracy.",
              "agreement": metrics, "sensitivity": None,
              "warnings": ["Threshold sensitivity and ground-motion comparison are not included."],
              "limitations": ["Nearest-neighbour comparison is on the coarser raster grid; the date gate permits two calendar days, not necessarily 48 hours.",
                              "NISAR detects open water while DSWx also includes inundated vegetation; neither is a flood-only map.",
                              "Agreement with another satellite product is not ground truth."]}
    if elapsed is None:
        result["warnings"].append("Exact elapsed time is unknown because acquisition times were not supplied for both sources.")
    elif elapsed > 48:
        result["warnings"].append("NEAR MATCH: acquisitions are more than 48 hours apart despite passing the two-calendar-day gate.")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
