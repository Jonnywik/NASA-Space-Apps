// Known backend reason strings -> i18n keys, so Filipino mode doesn't show English free text.
const REASONS = {
  "no barangay polygon contains this point": "reason.noBarangay",
  "the point has no containing barangay": "reason.noBarangayExposure",
  "permanent water is excluded from the flood rhythm": "reason.permanentWater",
  "priority mask or its provenance is unavailable": "reason.noPriority",
  "No reviewed current product": "reason.noMotion",
  "barangay exposure is unavailable": "reason.noExposure",
  "IMERG pass data is unavailable": "reason.noImerg",
  "line-of-sight motion is unavailable": "reason.noLos"
};

export function reasonText(t, reason) {
  if (!reason) return reason;
  const key = REASONS[reason];
  return key ? t(key) : reason;
}

const LANDCOVER = new Set([10, 20, 30, 40, 50, 60, 80, 90, 95]);

export function landCoverName(t, row) {
  const c = Number(row?.class);
  return LANDCOVER.has(c) ? t(`lc.${c}`) : row?.name ?? row?.class;
}
