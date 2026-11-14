// fitBounds padding that keeps the area clear of the floating panels
// (left controls + right details on desktop, controls on top + bottom sheet on phones).
export function fitOptions(extra = {}) {
  const wide = typeof window === 'undefined' ? true : window.innerWidth >= 768;
  if (wide) return { paddingTopLeft: [340, 40], paddingBottomRight: [360, 40], ...extra };
  const h = typeof window === 'undefined' ? 800 : window.innerHeight;
  return { paddingTopLeft: [20, 70], paddingBottomRight: [20, Math.round(h * 0.45) + 10], ...extra };
}
