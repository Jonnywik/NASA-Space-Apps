// Shareable URL (U8): mode, pass, swipe pair, point and language live in the query string.
//   ?mode=season&pass=20260705&cmp=20260623,20260705&lon=120.96&lat=14.7&lang=fil&view=regional
export const MODES = ["season", "rhythm", "motion", "history", "future"];

export function readUrlState(search) {
  const q = new URLSearchParams(search);
  const num = (k) => {
    const v = q.get(k);
    if (v == null || v === "") return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  };
  const mode = q.get("mode");
  const cmp = (q.get("cmp") || "").split(",").filter(Boolean);
  const lon = num("lon");
  const lat = num("lat");
  const lang = q.get("lang");
  return {
    mode: MODES.includes(mode) ? mode : null,
    pass: /^\d{8}$/.test(q.get("pass") || "") ? q.get("pass") : null,
    cmp: cmp.length === 2 && cmp.every((c) => /^\d{8}$/.test(c)) ? cmp : null,
    point: lon != null && lat != null ? { lon, lat } : null,
    lang: lang === "fil" || lang === "en" ? lang : null,
    view: q.get("view") === "regional" ? "regional" : null,
  };
}

export function buildQuery({ mode, pass, cmp, point, lang, view }) {
  const q = new URLSearchParams();
  if (view === "regional") q.set("view", "regional");
  if (mode) q.set("mode", mode);
  if (pass) q.set("pass", pass);
  if (cmp) q.set("cmp", cmp.join(","));
  if (point) {
    q.set("lon", point.lon.toFixed(5));
    q.set("lat", point.lat.toFixed(5));
  }
  if (lang && lang !== "en") q.set("lang", lang);
  return q.toString();
}
