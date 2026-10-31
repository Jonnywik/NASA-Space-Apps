"""Deterministic, evidence-bound text summaries for published P3 products.

The briefing is a presentation of fields already present in a product manifest.
It deliberately has no model, network, or external data dependency.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import html
import json
import math
from pathlib import Path
from typing import Any, Mapping

from . import core


TEMPLATE_VERSION = "p3-briefing-1.0"
_DATA_KINDS = {"observed", "derived", "scenario", "synthetic"}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _json_safe(value: Any) -> Any:
    """Copy JSON-compatible metadata and replace non-finite numbers with null."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items() if key != "_directory"}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def _as_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = value
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    if not math.isfinite(number):
        return None
    if isinstance(number, float) and number.is_integer():
        return int(number)
    return number


def _first(sources: list[Mapping[str, Any]], names: tuple[str, ...]) -> Any:
    for source in sources:
        for name in names:
            value = source.get(name)
            if value is not None:
                return value
    return None


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed_date = date.fromisoformat(text)
            parsed = datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=timezone.utc)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _region(manifest: Mapping[str, Any], region_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(region_id, str) or not region_id.strip():
        raise ValueError("region_id must be a non-empty registered region identifier")
    summaries = _mapping(manifest.get("regionalSummaries"))
    if region_id == "whole-event":
        return dict(manifest), dict(manifest)
    if region_id not in summaries or not isinstance(summaries[region_id], Mapping):
        # The calibrated biomass product uses a row list for named regions.
        rows = manifest.get("regionalMetrics")
        if isinstance(rows, (list, tuple)):
            matches = [row for row in rows if isinstance(row, Mapping) and row.get("regionId") == region_id]
            if len(matches) == 1:
                summary = dict(matches[0])
                return summary, summary
        raise ValueError(f"Unknown region_id {region_id!r}; expected 'whole-event' or a registered regional summary")
    summary = dict(summaries[region_id])
    return summary, summary


def _value_sources(manifest: Mapping[str, Any], summary: Mapping[str, Any], region_id: str) -> list[Mapping[str, Any]]:
    sources: list[Mapping[str, Any]] = []
    # Whole-event facts may be supplied at manifest root or nested under stats.
    # Regional facts never fall back to whole-event measurements.
    if region_id == "whole-event":
        sources.append(_mapping(manifest.get("stats")))
        sources.append(_mapping(manifest.get("metrics")))
        sources.append(_mapping(manifest.get("statistics")))
        sources.append(_mapping(manifest.get("regionalSummary")))
        sources.append(manifest)
    else:
        sources.append(_mapping(summary.get("stats")))
        sources.append(_mapping(summary.get("metrics")))
        sources.append(_mapping(summary.get("statistics")))
        sources.append(summary)
    return sources


def _canonical_metrics(sources: list[Mapping[str, Any]]) -> dict[str, int | float | None]:
    aliases = {
        "changedAreaKm2": ("km2Changed", "changedAreaKm2", "areaKm2Changed"),
        "floodAreaKm2": ("floodAreaKm2", "floodArea", "km2Flood"),
        "losRateMmPerYear": ("losRateMmPerYear", "rateMmPerYear", "medianRateMmPerYear", "meanRateMmPerYear"),
        "biomassMgHa": ("biomassMgHa", "biomassMgPerHa", "meanBiomassMgHa", "medianBiomassMgHa", "medianMgPerHa", "agbMgHa"),
        "scenarioExposureAreaKm2": ("scenarioExposureAreaKm2", "exposureAreaKm2", "exposedAreaKm2", "projectedExposureKm2", "km2Exposed"),
        "exposedCellCount": ("exposedCellCount",),
        "validTerrainCellCount": ("validTerrainCellCount", "validTerrainCount"),
        "validLosCellCount": ("validLosCellCount",),
        "validExposureCellCount": ("validExposureCellCount",),
        "medianLosDisplacementMm": ("medianLosDisplacementMm", "medianLosMm", "medianLOSmm", "medianDisplacementMm", "losDisplacementMm"),
        "mappedAssetCount": ("mappedAssetCount", "assetCount", "buildingCount"),
        "regionAssetOverlapCount": ("regionAssetOverlapCount",),
        "exposedAssetCount": ("exposedAssetCount",),
        "populationExposureCount": ("populationExposureCount", "exposedPopulationCount", "exposedPopulation", "populationCount"),
    }
    metrics: dict[str, int | float | None] = {}
    for canonical, names in aliases.items():
        number = _as_number(_first(sources, names))
        if canonical in {"changedAreaKm2", "floodAreaKm2", "biomassMgHa", "scenarioExposureAreaKm2", "exposedCellCount", "validTerrainCellCount", "validLosCellCount", "validExposureCellCount", "mappedAssetCount", "regionAssetOverlapCount", "exposedAssetCount", "populationExposureCount"} and number is not None and number < 0:
            number = None
        metrics[canonical] = number
    return metrics


def _classify(manifest: Mapping[str, Any]) -> str:
    markers = " ".join(str(manifest.get(key, "")) for key in ("product", "productType", "product_type", "kind", "analysisType")).casefold()
    if any(word in markers for word in ("projection", "scenario", "exposure")):
        return "scenario"
    if any(word in markers for word in ("vegetation", "biomass", "agb")):
        return "vegetation"
    if any(word in markers for word in ("ground-motion", "ground_motion", "ground motion", "motion", "subsidence", "los-rate")):
        return "motion"
    return "observation"


def _source_run_ids(*manifests: Mapping[str, Any]) -> list[str]:
    found: list[str] = []

    def add(value: Any) -> None:
        if isinstance(value, str) and value and value not in found:
            found.append(value)

    for source in manifests:
        add(source.get("runId"))
        add(source.get("sourceRunId"))
        for key in ("sourceRunIds", "upstreamRunIds"):
            values = source.get(key, [])
            if isinstance(values, (list, tuple)):
                for value in values:
                    add(value)
        source_entries = source.get("sources")
        if isinstance(source_entries, Mapping):
            for entry in source_entries.values():
                if isinstance(entry, Mapping):
                    add(entry.get("runId"))
        elif isinstance(source_entries, list):
            for entry in source_entries:
                if isinstance(entry, Mapping):
                    add(entry.get("runId") or entry.get("sourceRunId"))
        regional_entries = source.get("regionalMetrics")
        if isinstance(regional_entries, (list, tuple)):
            for entry in regional_entries:
                if isinstance(entry, Mapping):
                    add(entry.get("runId") or entry.get("sourceRunId"))
        for key in ("regionalSummary",):
            entry = source.get(key)
            if isinstance(entry, Mapping):
                add(entry.get("runId") or entry.get("sourceRunId"))
    return found


def _lineage_kinds(source: Mapping[str, Any]) -> set[str]:
    kinds: set[str] = set()
    value = source.get("dataKind")
    if isinstance(value, str):
        kinds.add(value)
    values = source.get("sourceDataKinds", [])
    if isinstance(values, (list, tuple)):
        kinds.update(kind for kind in values if isinstance(kind, str))
    for key in ("lineage", "sources"):
        entries = source.get(key)
        if isinstance(entries, Mapping):
            entries = entries.values()
        if isinstance(entries, (list, tuple)) or hasattr(entries, "__iter__") and not isinstance(entries, (str, bytes, Mapping)):
            try:
                for entry in entries:
                    if isinstance(entry, Mapping) and isinstance(entry.get("dataKind"), str):
                        kinds.add(entry["dataKind"])
            except TypeError:
                pass
    if source.get("syntheticLineage"):
        kinds.add("synthetic")
    return kinds


def _source_details(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    entries = source.get("sources", [])
    iterable = list(entries.items()) if isinstance(entries, Mapping) else [(None, item) for item in entries] if isinstance(entries, (list, tuple)) else []
    for label, item in iterable:
        if isinstance(item, Mapping):
            name = item.get("name") or item.get("productId") or item.get("sourceId") or item.get("provider") or label or item.get("runId") or item.get("sourceRunId")
            if name is not None:
                result.append({
                    "name": str(name),
                    "productId": item.get("productId"),
                    "runId": item.get("runId") or item.get("sourceRunId"),
                    "sha256": item.get("sha256") or item.get("sourceSha256"),
                    "acquisitionDates": _json_safe(item.get("acquisitionDates")),
                })
    if not result:
        source_ids = source.get("sourceIds")
        if isinstance(source_ids, (list, tuple)):
            result = [{"name": str(item)} for item in source_ids]
    return result


def _supported_years(manifest: Mapping[str, Any], annual: Mapping[Any, Any]) -> list[int]:
    years: list[int] = []
    supported = manifest.get("supportedYears")
    candidates = supported if isinstance(supported, (list, tuple)) else list(annual.keys())
    for value in candidates:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed not in years:
            years.append(parsed)
    return sorted(years)


def _regional_year_summaries(manifest: Mapping[str, Any], year: int, supported_years: list[int]) -> dict[str, Any]:
    summaries = _mapping(manifest.get("regionalSummaries"))
    selected: dict[str, Any] = {}
    for region_id, value in summaries.items():
        if not isinstance(value, Mapping):
            continue
        annual = value.get("annualMetrics") or value.get("byYear") or value.get("years")
        if isinstance(annual, Mapping):
            item = annual.get(str(year), annual.get(year))
            if isinstance(item, Mapping):
                selected[str(region_id)] = dict(item)
        elif len(supported_years) <= 1:
            selected[str(region_id)] = dict(value)
    return selected


def _select_projection_year(manifest: Mapping[str, Any], year: int | str | None) -> tuple[dict[str, Any], int | None]:
    """Select one explicitly supported annual metric record; never blend years."""
    if _classify(manifest) != "scenario":
        if year is not None:
            raise ValueError("year is only valid for projection or scenario briefings")
        return dict(manifest), None

    annual_value = manifest.get("annualMetrics")
    if annual_value is not None and not isinstance(annual_value, Mapping):
        raise ValueError("annualMetrics must be keyed by supported year")
    annual = _mapping(annual_value)
    supported = _supported_years(manifest, annual)
    declared = manifest.get("selectedYear", manifest.get("projectionYear", manifest.get("year")))
    if year is None:
        if declared is not None:
            chosen = _as_number(declared)
        elif len(supported) == 1:
            chosen = supported[0]
        elif len(supported) > 1:
            raise ValueError("A year is required for a multi-year projection briefing")
        else:
            chosen = None
    else:
        chosen = _as_number(year)
    if chosen is None or int(chosen) != chosen:
        if year is not None or supported:
            raise ValueError("A supported integer projection year is required")
        return dict(manifest), None
    chosen = int(chosen)
    if supported and chosen not in supported:
        raise ValueError(f"Unsupported projection year {chosen}; supported years are {supported}")

    entry = annual.get(str(chosen), annual.get(chosen))
    if entry is None:
        if len(supported) > 1:
            raise ValueError(f"Projection year {chosen} has no published annual metrics")
        selected = dict(manifest)
        selected["projectionYear"] = chosen
        selected["year"] = chosen
        return selected, chosen
    if not isinstance(entry, Mapping):
        raise ValueError(f"Projection annual metrics for year {chosen} must be an object")

    selected = dict(manifest)
    # Root-level metrics in a multi-year product can describe another year or
    # a whole-product aggregate. Remove them before applying the selected entry.
    metric_fields = {
        "stats", "statistics", "metrics", "regionalSummary", "regionalSummaries", "coverage", "validCoverage",
        "km2Changed", "changedAreaKm2", "areaKm2Changed", "floodAreaKm2", "floodArea", "km2Flood",
        "losRateMmPerYear", "rateMmPerYear", "medianRateMmPerYear", "meanRateMmPerYear",
        "scenarioExposureAreaKm2", "exposureAreaKm2", "exposedAreaKm2", "projectedExposureKm2", "km2Exposed",
        "exposedCellCount", "validTerrainCellCount", "validTerrainCount", "validLosCellCount", "validExposureCellCount",
        "medianLosDisplacementMm", "medianLosMm", "medianLOSmm", "medianDisplacementMm", "losDisplacementMm",
        "mappedAssetCount", "assetCount", "buildingCount", "exposedAssetCount", "populationExposureCount",
        "exposedPopulationCount", "exposedPopulation", "populationCount", "snapshotMetricsAvailability",
    }
    for key in metric_fields:
        selected.pop(key, None)
    selected.update({key: value for key, value in entry.items() if key not in {"regionalSummaries", "regions"}})
    selected["projectionYear"] = chosen
    selected["year"] = chosen
    regions = entry.get("regionalSummaries") or entry.get("regions")
    if isinstance(regions, Mapping):
        selected["regionalSummaries"] = dict(regions)
    else:
        selected["regionalSummaries"] = _regional_year_summaries(manifest, chosen, supported)
    return selected, chosen


def _coverage(summary: Mapping[str, Any], manifest: Mapping[str, Any], region_id: str) -> Any:
    if region_id != "whole-event":
        value = summary.get("coverage")
        if value is None:
            value = summary.get("validCoverage")
        return _json_safe(value)
    return _json_safe(manifest.get("coverage", manifest.get("validCoverage")))


def _native_support(manifest: Mapping[str, Any], summary: Mapping[str, Any], region_id: str) -> dict[str, Any]:
    if region_id == "whole-event":
        sources = [manifest, _mapping(manifest.get("regionalSummary"))]
        statistics = [_mapping(manifest.get("stats")), _mapping(manifest.get("statistics")),
                      _mapping(manifest.get("regionalSummary")),
                      _mapping(manifest.get("coverage")), _mapping(manifest.get("validCoverage")), manifest]
        grid = _mapping(manifest.get("grid"))
    else:
        sources = [summary]
        statistics = [_mapping(summary.get("stats")), _mapping(summary.get("statistics")),
                      _mapping(summary.get("coverage")), summary]
        grid = {}
    resolution = _first(sources, ("nativeResolutionMetres", "nativeResolutionMeters", "nativeResolution", "resolutionMetres"))
    if resolution is None:
        resolution = grid.get("resolutionMetres") or grid.get("resolution")
    return _json_safe({
        "nativeResolution": resolution,
        "validPixelCount": _as_number(_first(statistics, ("validPixelCount", "commonValidPixelCount", "supportedPixelCount", "validRateCellCount", "validTerrainCellCount", "validLosCellCount", "validExposureCellCount", "validSeriesCellCount"))),
        "totalPixelCount": _as_number(_first(statistics, ("totalPixelCount", "aoiPixelCount", "selectedCellCount"))),
        "validObservationCount": _as_number(_first(statistics, ("validObservationCount", "validEpochCount", "epochCount", "observationCount", "medianValidEpochCount"))),
    })


def _dates(manifest: Mapping[str, Any], summary: Mapping[str, Any], region_id: str) -> dict[str, Any]:
    sources = [summary] if region_id != "whole-event" else [manifest]
    dates: dict[str, Any] = {
        "observationStart": _first(sources, ("observationStart", "observationStartDate", "startDate", "acquisitionStart")),
        "observationEnd": _first(sources, ("observationEnd", "observationEndDate", "endDate", "acquisitionEnd")),
        "observationDates": _first(sources, ("observationDates", "acquisitionDates", "dates", "epochs")),
        "baselineDate": _first(sources, ("baselineDate", "referenceDate", "referenceEpoch", "baselineEpoch")),
        "projectionYear": _first(sources, ("projectionYear", "year")),
        "projectionDate": _first(sources, ("projectionDate",)),
    }
    event_window = _mapping(manifest.get("eventWindow"))
    obs_dates = dates.get("observationDates")
    if isinstance(obs_dates, (list, tuple)) and obs_dates and all(isinstance(item, Mapping) for item in obs_dates):
        dates["observationDates"] = [item.get("epoch") or item.get("date") for item in obs_dates if item.get("epoch") or item.get("date")]
    if dates["observationStart"] is None and isinstance(dates.get("observationDates"), (list, tuple)) and dates["observationDates"]:
        dates["observationStart"] = dates["observationDates"][0]
    if dates["observationEnd"] is None and isinstance(dates.get("observationDates"), (list, tuple)) and dates["observationDates"]:
        dates["observationEnd"] = dates["observationDates"][-1]
    if region_id == "whole-event":
        dates["observationStart"] = dates["observationStart"] or event_window.get("start")
        dates["observationEnd"] = dates["observationEnd"] or event_window.get("end")
    return _json_safe(dates)


def _warnings(source: Mapping[str, Any], exposure: Mapping[str, Any] | None = None) -> list[str]:
    warnings: list[str] = []

    def append(value: Any) -> None:
        if isinstance(value, str) and value.strip() and value not in warnings:
            warnings.append(value)

    for item in source.get("warnings", []) if isinstance(source.get("warnings", []), (list, tuple)) else []:
        append(item)
    quality = _mapping(source.get("quality"))
    for item in quality.get("warnings", []) if isinstance(quality.get("warnings", []), (list, tuple)) else []:
        append(item)
    now = datetime.now(timezone.utc)
    for label, item in (("product", source), ("exposure snapshot", exposure or {})):
        for key in ("expiresAt", "validUntil", "snapshotExpiresAt"):
            expiry = _parse_timestamp(item.get(key))
            if expiry is not None and expiry < now:
                append(f"{label} expired at {item[key]}.")
                break
    return warnings


def _metric_reasons(manifest: Mapping[str, Any], metrics: Mapping[str, Any]) -> dict[str, str]:
    reasons: dict[str, str] = {}
    availability = _mapping(manifest.get("snapshotMetricsAvailability"))
    field_aliases = {
        "exposedAssetCount": ("exposedAssetCount", "assets", "assetCount"),
        "populationExposureCount": ("exposedPopulationCount", "populationExposureCount", "population"),
    }
    for metric, names in field_aliases.items():
        if metrics.get(metric) is not None:
            continue
        for name in names:
            status = availability.get(name)
            if isinstance(status, Mapping):
                reason = status.get("reason")
                if status.get("available") is not True and isinstance(reason, str) and reason:
                    reasons[metric] = reason
                    break
            elif isinstance(status, str) and status:
                reasons[metric] = status
                break
            if status is None:
                direct_reason = manifest.get(f"{name}Reason")
                if isinstance(direct_reason, str) and direct_reason:
                    reasons[metric] = direct_reason
                    break
    return reasons


def _display(value: Any) -> str:
    if value is None:
        return "not reported"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return format(value, ".6g")
    if isinstance(value, (list, tuple)):
        parts = [_display(item) for item in value if item is not None]
        return ", ".join(parts) if parts else "not reported"
    if isinstance(value, Mapping):
        if all(key in value for key in ("x", "y")):
            return f"{_display(value['x'])} × {_display(value['y'])}"
        if "resolutionMetres" in value:
            return _display(value["resolutionMetres"])
        valid = value.get("validPixelCount", value.get("commonValidPixelCount"))
        total = value.get("totalPixelCount", value.get("aoiPixelCount"))
        if valid is not None and total is not None:
            return f"{_display(valid)} of {_display(total)} pixels"
        for key in ("coveragePercent", "validCoveragePercent", "commonValidCoveragePercent", "eligibleCoveragePercent", "percent", "validPixelCount", "count"):
            if value.get(key) is not None:
                unit = "%" if "Percent" in key or key in {"percent", "coveragePercent"} else ""
                return f"{_display(value[key])}{unit}"
        return "recorded"
    return html.escape(str(value), quote=True)


def _date_text(dates: Mapping[str, Any], template: str) -> str:
    start, end = dates.get("observationStart"), dates.get("observationEnd")
    obs = dates.get("observationDates")
    chunks: list[str] = []
    if start is not None or end is not None:
        if start is not None and end is not None:
            chunks.append(f"observations {_display(start)} to {_display(end)}")
        elif start is not None:
            chunks.append(f"observations from {_display(start)}")
        else:
            chunks.append(f"observations through {_display(end)}")
    elif obs is not None:
        chunks.append(f"observation dates {_display(obs)}")
    if dates.get("baselineDate") is not None:
        chunks.append(f"baseline {_display(dates['baselineDate'])}")
    if template == "scenario":
        projection = dates.get("projectionYear") or dates.get("projectionDate")
        if projection is not None:
            chunks.append(f"projection {_display(projection)}")
    return "; ".join(chunks) if chunks else "not reported"


def _text_for(template: str, region_name: str, data_kind: str, dates: Mapping[str, Any], coverage: Any,
              native_support: Mapping[str, Any], metrics: Mapping[str, Any], sources: list[dict[str, Any]],
              limitations: list[str], exposure_facts: Mapping[str, Any] | None = None,
              metric_reasons: Mapping[str, str] | None = None) -> str:
    region_text = html.escape(region_name, quote=True)
    period = _date_text(dates, template)
    coverage_text = _display(coverage)
    source_names = [html.escape(str(item["name"]), quote=True) for item in sources if item.get("name") is not None]
    sources_text = ", ".join(source_names) if source_names else "not listed"
    resolution = native_support.get("nativeResolution")
    native_support_text = f"native resolution {_display(resolution)} m" if resolution is not None else "native resolution not reported"
    if native_support.get("validPixelCount") is not None:
        native_support_text += f"; valid cells {_display(native_support['validPixelCount'])}"
    if native_support.get("totalPixelCount") is not None:
        native_support_text += f" of {_display(native_support['totalPixelCount'])} selected cells"
    if native_support.get("validObservationCount") is not None:
        native_support_text += f"; supported observations {_display(native_support['validObservationCount'])}"
    if template == "motion":
        rate = metrics.get("losRateMmPerYear")
        finding = f"reported LOS motion rate is {_display(rate)} mm/year" if rate is not None else "LOS motion rate is unavailable"
    elif template == "vegetation":
        biomass = metrics.get("biomassMgHa")
        finding = f"reported biomass is {_display(biomass)} Mg/ha" if biomass is not None else "biomass is unavailable"
    elif template == "scenario":
        area = metrics.get("scenarioExposureAreaKm2")
        displacement = metrics.get("medianLosDisplacementMm")
        findings = [f"conditional scenario exposure area is {_display(area)} km²" if area is not None else "scenario exposure area is unavailable"]
        if displacement is not None:
            findings.append(f"median LOS displacement is {_display(displacement)} mm")
        reasons = metric_reasons or {}
        for key, reason_key, label in (("exposedAssetCount", "exposedAssetCount", "mapped asset count"),
                                       ("populationExposureCount", "populationExposureCount", "population exposure")):
            value = metrics.get(key)
            if value is not None:
                if key == "exposedAssetCount":
                    findings.append(f"{_display(value)} mapped assets overlap the scenario footprint; this is exposure context, not damage")
                else:
                    findings.append(f"population exposure is {_display(value)}, not confirmed affected population")
            else:
                reason = reasons.get(reason_key)
                findings.append(f"{label} unavailable" + (f" ({html.escape(reason, quote=True)})" if reason else ""))
        finding = "; ".join(findings)
    else:
        findings: list[str] = []
        for key, label in (("changedAreaKm2", "changed area"), ("floodAreaKm2", "flood area")):
            if metrics.get(key) is not None:
                findings.append(f"reported {label} is {_display(metrics[key])} km²")
        finding = "; ".join(findings) if findings else "area metrics are unavailable"
    exposure_text = ""
    if exposure_facts is not None:
        snapshot_time = exposure_facts.get("timestamp")
        snapshot_coverage = exposure_facts.get("coverage")
        exposure_parts = [
            f"snapshot as of {_display(snapshot_time)}" if snapshot_time is not None else "snapshot time not reported",
            f"snapshot coverage {_display(snapshot_coverage)}" if snapshot_coverage is not None else "snapshot coverage not reported",
        ]
        if metrics.get("mappedAssetCount") is not None:
            exposure_parts.append(f"mapped asset count {_display(metrics['mappedAssetCount'])} with scope as supplied")
        if metrics.get("regionAssetOverlapCount") is not None:
            exposure_parts.append(f"{_display(metrics['regionAssetOverlapCount'])} unique mapped asset overlaps in the named region")
        if metrics.get("exposedAssetCount") is not None:
            exposure_parts.append(f"{_display(metrics['exposedAssetCount'])} unique mapped assets overlap the supplied footprint; this is exposure context, not damage")
        if metrics.get("populationExposureCount") is not None:
            exposure_parts.append(f"population exposure {_display(metrics['populationExposureCount'])}, not confirmed affected population")
        exposure_text = " Exposure: " + "; ".join(exposure_parts) + "."
    limit_text = "; ".join(html.escape(item, quote=True) for item in limitations) if limitations else "none recorded"
    return (
        f"{region_text}: {finding}. Data kind: {html.escape(data_kind, quote=True)}. "
        f"Dates: {period}. Valid coverage: {coverage_text}. Native support: {native_support_text}. "
        f"Sources: {sources_text}.{exposure_text} Limitations: {limit_text}."
    )


def _exposure_payload(exposure: Mapping[str, Any] | None) -> tuple[dict[str, Any] | None, list[str]]:
    if exposure is None:
        return None, []
    snapshot = dict(exposure)
    warnings: list[str] = []
    # Published exposure products may store a GeoJSON footprint asset. Resolve it
    # only through the validated asset table attached by core.load_manifest.
    assets = _mapping(snapshot.get("assets"))
    for key in ("footprints", "features", "geojson"):
        if key in assets and snapshot.get("_directory"):
            asset_path = core.asset_path(snapshot, key)
            geojson = json.loads(Path(asset_path).read_text(encoding="utf-8"))
            if isinstance(geojson, Mapping):
                snapshot["footprints"] = geojson.get("features", [])
                snapshot.setdefault("footprintCrs", geojson.get("crs") or snapshot.get("crs"))
            break
    return snapshot, warnings


def _region_geometry(manifest: Mapping[str, Any], summary: Mapping[str, Any], region_id: str) -> tuple[Any, Any]:
    geometry = summary.get("geometry") or summary.get("regionGeometry")
    crs = summary.get("geometryCrs") or summary.get("crs")
    if region_id == "whole-event":
        geometry = geometry or manifest.get("regionGeometry") or manifest.get("geometry")
        crs = crs or manifest.get("regionGeometryCrs") or manifest.get("geometryCrs")
        crs = crs or _mapping(manifest.get("grid")).get("crs")
    return geometry, crs


def _deduplicated_asset_count(manifest: Mapping[str, Any], summary: Mapping[str, Any], region_id: str,
                              exposure: Mapping[str, Any], warnings: list[str]) -> tuple[int | None, str | None]:
    features = exposure.get("footprints")
    if features is None:
        features = exposure.get("features")
    if isinstance(features, Mapping) and features.get("type") == "FeatureCollection":
        features = features.get("features")
    if not isinstance(features, (list, tuple)):
        return None, None
    region_geometry, region_crs = _region_geometry(manifest, summary, region_id)
    exposure_crs = exposure.get("footprintCrs") or exposure.get("crs")
    if not region_geometry or not region_crs or not exposure_crs:
        warnings.append("Asset overlap count unavailable: region and footprint geometries with CRS metadata are required.")
        return None, None
    try:
        from rasterio.crs import CRS
        from shapely.geometry import shape
    except ImportError:
        warnings.append("Asset overlap count unavailable: geometry libraries are not installed.")
        return None, None
    try:
        r_crs = CRS.from_user_input(region_crs)
        e_crs = CRS.from_user_input(exposure_crs)
        if not r_crs.is_projected or not e_crs.is_projected or r_crs.linear_units not in {"metre", "meter", "metres", "meters"} or e_crs.linear_units not in {"metre", "meter", "metres", "meters"}:
            warnings.append("Asset overlap count unavailable: footprint and region geometries must use metric projected CRSs.")
            return None, None
        if r_crs != e_crs:
            warnings.append("Asset overlap count unavailable: region and footprint CRSs differ; reproject inputs explicitly.")
            return None, None
        region_shape = shape(region_geometry.get("geometry", region_geometry) if isinstance(region_geometry, Mapping) else region_geometry)
        if not region_shape.is_valid or region_shape.area <= 0:
            warnings.append("Asset overlap count unavailable: region geometry is invalid or has no area.")
            return None, None
        # An administrative boundary can scope a regional inventory, but does
        # not by itself identify hazard exposure. Only call a count exposed when
        # the input supplies a separate mapped hazard/exposure footprint.
        hazard_geometry = (
            exposure.get("exposureGeometry") or exposure.get("hazardFootprint") or
            manifest.get("exposureGeometry") or manifest.get("hazardFootprint") or
            summary.get("exposureGeometry") or summary.get("hazardFootprint")
        )
        hazard_shape = None
        scope = "regionAssetOverlapCount"
        if hazard_geometry is not None:
            hazard_crs = exposure.get("exposureGeometryCrs") or exposure.get("hazardFootprintCrs") or exposure_crs
            h_crs = CRS.from_user_input(hazard_crs)
            if not h_crs.is_projected or h_crs.linear_units not in {"metre", "meter", "metres", "meters"} or h_crs != e_crs:
                warnings.append("Asset exposure count unavailable: hazard footprint must use the same metric projected CRS as asset footprints.")
                return None, None
            hazard_shape = shape(hazard_geometry.get("geometry", hazard_geometry) if isinstance(hazard_geometry, Mapping) else hazard_geometry)
            if not hazard_shape.is_valid or hazard_shape.area <= 0:
                warnings.append("Asset exposure count unavailable: hazard footprint is invalid or has no area.")
                return None, None
            scope = "exposedAssetCount"
        ids: set[str] = set()
        for feature in features:
            if not isinstance(feature, Mapping):
                continue
            properties = _mapping(feature.get("properties"))
            identifier = (feature.get("assetId") or feature.get("id") or properties.get("assetId") or
                          properties.get("buildingId") or properties.get("osm_id") or properties.get("uid") or properties.get("id"))
            geometry = feature.get("geometry")
            if identifier is None or not isinstance(geometry, Mapping):
                continue
            try:
                footprint = shape(geometry)
                if not footprint.is_valid or footprint.area <= 0:
                    continue
                overlap = footprint.intersection(region_shape)
                if hazard_shape is not None:
                    overlap = overlap.intersection(hazard_shape)
                if overlap.is_valid and overlap.area > 0:
                    ids.add(str(identifier))
            except Exception:
                continue
        return len(ids), scope
    except Exception as exc:  # noqa: BLE001 - invalid optional geometry degrades to explicit unavailable.
        warnings.append(f"Asset overlap count unavailable: {html.escape(str(exc), quote=True)}.")
        return None, None


def _validate_exposure_ids(manifest: Mapping[str, Any], exposure: Mapping[str, Any], region_id: str) -> None:
    event_id = manifest.get("event")
    exposure_event = exposure.get("event")
    if event_id is not None and exposure_event is not None and event_id != exposure_event:
        raise ValueError(f"Exposure event {exposure_event!r} does not match product event {event_id!r}")
    exposure_region = exposure.get("regionId")
    if exposure_region is not None and exposure_region != region_id:
        raise ValueError(f"Exposure region {exposure_region!r} does not match requested region {region_id!r}")
    reference_run = exposure.get("inputRunId") or exposure.get("forRunId") or exposure.get("projectionRunId")
    accepted_runs = set(_source_run_ids(manifest))
    if reference_run is not None and reference_run not in accepted_runs:
        raise ValueError(f"Exposure input run {reference_run!r} does not match briefing product lineage")


def build_briefing(manifest: Mapping[str, Any], region_id: str = "whole-event", exposure: Mapping[str, Any] | None = None,
                   year: int | str | None = None) -> dict[str, Any]:
    """Build a deterministic paragraph and the exact structured facts behind it."""
    if not isinstance(manifest, Mapping):
        raise ValueError("manifest must be a mapping")
    manifest, selected_year = _select_projection_year(manifest, year)
    data_kind = manifest.get("dataKind")
    if data_kind not in _DATA_KINDS:
        raise ValueError("manifest dataKind must be observed, derived, scenario, or synthetic")
    summary, region_record = _region(manifest, region_id)
    exposure_data, _ = _exposure_payload(exposure)
    if exposure_data is not None:
        _validate_exposure_ids(manifest, exposure_data, region_id)

    metric_sources = _value_sources(manifest, summary, region_id)
    metrics = _canonical_metrics(metric_sources)
    metric_reasons = _metric_reasons(manifest, metrics)
    warnings = _warnings(manifest, exposure_data)
    if exposure_data is not None:
        asset_count, asset_scope = _deduplicated_asset_count(manifest, summary, region_id, exposure_data, warnings)
        if asset_count is None:
            asset_count = _as_number(exposure_data.get("mappedAssetCount", exposure_data.get("assetCount")))
            asset_scope = "mappedAssetCount"
        if asset_count is not None and asset_scope is not None:
            metrics[asset_scope] = asset_count
        population = _first([_mapping(exposure_data.get("stats")), exposure_data],
                            ("populationExposureCount", "exposedPopulationCount", "exposedPopulation", "populationCount"))
        parsed_population = _as_number(population)
        if parsed_population is not None and parsed_population >= 0:
            metrics["populationExposureCount"] = parsed_population

    lineage_kinds = _lineage_kinds(manifest)
    if exposure_data is not None:
        lineage_kinds.update(_lineage_kinds(exposure_data))
    if "synthetic" in lineage_kinds:
        final_data_kind = "synthetic"
    else:
        final_data_kind = data_kind
    if "synthetic" in lineage_kinds and any(kind != "synthetic" for kind in lineage_kinds):
        warnings.append("Lineage includes synthetic and non-synthetic sources; the briefing is labeled synthetic.")

    dates = _dates(manifest, summary, region_id)
    coverage = _coverage(summary, manifest, region_id)
    native_support = _native_support(manifest, summary, region_id)
    region_name = str(region_record.get("name") or (manifest.get("eventName") if region_id == "whole-event" else None) or region_id)
    template = _classify(manifest)
    sources = _source_details(manifest)
    if exposure_data is not None:
        exposure_sources = _source_details(exposure_data)
        if not exposure_sources:
            exposure_sources = [{"name": str(exposure_data.get("product") or exposure_data.get("runId") or "exposure snapshot")}]
        sources.extend(exposure_sources)
    if not sources:
        sources = [{"name": str(manifest.get("product") or manifest.get("runId") or "unnamed source")}]

    limitations_raw = manifest.get("limitations", [])
    limitations = [str(item) for item in limitations_raw if item is not None] if isinstance(limitations_raw, (list, tuple)) else []
    limitations.extend(warning for warning in warnings if warning not in limitations)
    if template == "scenario":
        limitations.append("Scenario results are conditional outputs, not forecasts.")
    if exposure_data is not None and metrics.get("exposedAssetCount") is not None:
        limitations.append("Mapped asset overlap with the supplied footprint indicates exposure, not damage.")
    if exposure_data is not None and metrics.get("populationExposureCount") is not None:
        limitations.append("Population exposure is not confirmed affected population.")
    if template == "observation" and any(metrics.get(key) == 0 for key in ("changedAreaKm2", "floodAreaKm2")):
        limitations.append("An empty detection applies only within valid mapped coverage and is not proof of safety.")
    # Keep stable first occurrence while preventing repeated template notices.
    limitations = list(dict.fromkeys(limitations))

    source_run_ids = _source_run_ids(manifest, exposure_data or {})
    source_hashes = _json_safe(manifest.get("sourceHashes", {}))
    provenance: dict[str, Any] = {
        "event": manifest.get("event"),
        "product": manifest.get("product"),
        "runId": manifest.get("runId"),
        "selectedYear": selected_year,
        "sourceHashes": source_hashes,
        "sources": sources,
        "sourceRunIds": source_run_ids,
        "dataKinds": sorted(lineage_kinds),
        "exposureSnapshot": None,
    }
    if exposure_data is not None:
        provenance["exposureSnapshot"] = {
            "event": exposure_data.get("event"),
            "runId": exposure_data.get("runId"),
            "timestamp": exposure_data.get("timestamp") or exposure_data.get("snapshotTimestamp") or exposure_data.get("asOf"),
            "coverage": _json_safe(exposure_data.get("coverage")),
            "sourceHashes": _json_safe(exposure_data.get("sourceHashes", {})),
        }
    facts = {
        "region": {"id": region_id, "name": region_name},
        "product": manifest.get("product"),
        "selectedYear": selected_year,
        "template": template,
        "dataKind": final_data_kind,
        "dates": dates,
        "coverage": coverage,
        "nativeSupport": native_support,
        "metrics": metrics,
        "metricReasons": metric_reasons,
        "missingMetrics": [key for key, value in metrics.items() if value is None],
        "sources": sources,
        "sourceRunIds": source_run_ids,
        "limitations": limitations,
        "warnings": warnings,
        "exposure": provenance["exposureSnapshot"],
    }
    text = _text_for(template, region_name, final_data_kind, dates, coverage, native_support, metrics,
                     sources, limitations, provenance["exposureSnapshot"], metric_reasons)
    return {
        "text": text,
        "facts": _json_safe(facts),
        "provenance": _json_safe(provenance),
        "templateVersion": TEMPLATE_VERSION,
        "dataKind": final_data_kind,
        "selectedYear": selected_year,
        "sourceRunIds": source_run_ids,
    }


def _load_exposure_path(path: str | Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    loaded = core.load_manifest(path)
    return dict(loaded)


def generate(event: str, manifest_path: str | Path, region_id: str = "whole-event",
             exposure_path: str | Path | None = None, output_root: str | Path | None = None,
             year: int | str | None = None) -> Path:
    """Load hash-checked inputs and publish an immutable briefing JSON product."""
    manifest = core.load_manifest(manifest_path)
    if manifest.get("event") != event:
        raise ValueError(f"Manifest event must be {event!r}; received {manifest.get('event')!r}")
    exposure = _load_exposure_path(exposure_path)
    briefing = build_briefing(manifest, region_id=region_id, exposure=exposure, year=year)
    metadata = {
        "dataKind": briefing["dataKind"],
        "syntheticLineage": briefing["dataKind"] == "synthetic",
        "sourceRunIds": briefing["sourceRunIds"],
        "sourceHashes": briefing["provenance"]["sourceHashes"],
        "templateVersion": briefing["templateVersion"],
        "regionId": region_id,
        "selectedYear": briefing["selectedYear"],
        "warnings": briefing["facts"]["warnings"],
        "implementationStatus": "verified",
        "limitations": briefing["facts"]["limitations"],
    }

    def writer(stage: Path) -> dict[str, str]:
        (stage / "briefing.json").write_text(json.dumps(briefing, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        return {"briefing": "briefing.json"}

    published = core.publish(event, "briefing", metadata, writer, output_root=output_root)
    return Path(published)
