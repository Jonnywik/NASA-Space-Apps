"""Build a time-lapse from the observed NISAR product and IMERG cache."""
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BACKEND = Path(__file__).resolve().parents[1]
PRODUCT = BACKEND / "data/output/camanava_2026/nisar"
RAIN = BACKEND / "data/cache/climate/imerg_passes.json"
OUTPUT = BACKEND / "data/cache/nisar/timelapse.gif"
MANILA = timezone(timedelta(hours=8))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rain_value(row):
    value = row.get("last48hMm") if row and row.get("missingHalfHours") == 0 else None
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None


def caption(acquisition_time):
    timestamp = datetime.fromisoformat(acquisition_time.replace("Z", "+00:00"))
    if timestamp.utcoffset() is None:
        raise ValueError("Acquisition time has no timezone")
    local = timestamp.astimezone(MANILA)
    return f"NISAR L-band | {local.strftime('%d %b %Y | %H:%M')} Manila"


def build(product=PRODUCT, rain_path=RAIN, output=OUTPUT):
    product, rain_path, output = Path(product), Path(rain_path), Path(output)
    manifest_path = product / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        rain = json.loads(rain_path.read_text(encoding="utf-8"))
        passes = manifest["passes"]
        if (manifest.get("dataKind") != "observed" or manifest.get("kind") != "nisar-flood-rhythm"
                or manifest.get("area") != "camanava_2026" or not passes
                or manifest.get("passCount") != len(passes)):
            raise ValueError("NISAR product is missing or not observed")
        if rain.get("dataKind") != "observed" or rain.get("area") != "camanava_2026" or rain.get("hoursBeforePass") != 48:
            raise ValueError("IMERG cache is missing or not observed")
        rain_by_date = {row["date"]: row for row in rain["passes"]}
        frames = []
        font = ImageFont.load_default()
        for row in passes:
            pid = row["id"]
            if len(pid) != 8 or not pid.isdigit():
                raise ValueError("Invalid pass ID")
            paths = []
            for prefix in ("hh", "pass"):
                name = f"{prefix}_{pid}"
                asset = manifest["assets"][name]
                path = product / f"{name}.png"
                if asset["path"] != path.name or digest(path) != asset["sha256"]:
                    raise ValueError(f"Product asset mismatch: {path.name}")
                paths.append(path)

            with Image.open(paths[0]) as hh, Image.open(paths[1]) as water:
                hh = hh.convert("RGBA").resize((499, 700), Image.Resampling.LANCZOS)
                water = water.convert("RGBA").resize(hh.size, Image.Resampling.NEAREST)
                hh.alpha_composite(water)
                frame = Image.new("RGB", (539, 810), "#101820")
                frame.paste(hh.convert("RGB"), (20, 45))
            draw = ImageDraw.Draw(frame)
            draw.text((20, 13), caption(row["acquisitionTime"]), fill="white", font=font)
            value = rain_value(rain_by_date.get(row["date"]))
            label = "unavailable" if value is None else f"{value:g} mm"
            draw.text((20, 752), f"IMERG rain in previous 48 hours: {label}", fill="white", font=font)
            if value is not None:
                draw.rectangle((20, 770, 519, 777), fill="#34424b")
                draw.rectangle((20, 770, 20 + round(499 * min(value, 100) / 100), 777), fill="#4bb9e8")
                draw.text((350, 752), "bar: 0-100+ mm", fill="white", font=font)
            draw.text((20, 788), "Open water outside usual water | NASA-ISRO NISAR / ASF; NASA GPM IMERG", fill="white", font=font)
            frames.append(frame.quantize(colors=128))
        output.parent.mkdir(parents=True, exist_ok=True)
        frames[0].save(output, save_all=True, append_images=frames[1:], duration=1200, loop=0, optimize=False, disposal=2)
        provenance = {"dataKind": "derived", "gifSha256": digest(output), "productManifestSha256": digest(manifest_path),
                      "imergCacheSha256": digest(rain_path), "source": "NASA-ISRO NISAR L2 GCOV via ASF; NASA GPM IMERG via GES DISC"}
        output.with_suffix(".json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    except (OSError, KeyError, ValueError, TypeError) as exc:
        raise ValueError(f"Cannot build timelapse: real NISAR product or IMERG cache missing/invalid: {exc}") from exc


if __name__ == "__main__":
    try:
        build()
        print(f"Created {OUTPUT} ({OUTPUT.stat().st_size} bytes)")
    except ValueError as exc:
        raise SystemExit(str(exc))



