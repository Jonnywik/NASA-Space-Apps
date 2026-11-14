// Before/after clip for the two swipe panes ("beforePane" on the left, "afterPane" on the right).
// fraction = 0..1 from the left edge of the map; null removes the clip (single-layer view).
export function applyClip(map, fraction) {
  if (!map) return;
  const before = map.getPane("beforePane");
  const after = map.getPane("afterPane");
  if (!before || !after) return;

  if (fraction == null) {
    before.style.clip = "";
    after.style.clip = "";
    return;
  }

  const size = map.getSize();
  const nw = map.containerPointToLayerPoint([0, 0]);
  const se = map.containerPointToLayerPoint(size);
  const x = nw.x + size.x * fraction;

  before.style.clip = `rect(${nw.y}px, ${x}px, ${se.y}px, ${nw.x}px)`;
  after.style.clip = `rect(${nw.y}px, ${se.x}px, ${se.y}px, ${x}px)`;
}
