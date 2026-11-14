// U3 Story Mode: six steps that drive the map. `mode` picks the workspace mode, `view` where the map
// goes, `bare` hides the radar overlays (step 1 shows only the streets), `play` starts the season animation.
export const AREA_BOUNDS = [
  [14.6, 120.88],
  [14.82, 121.04],
];

export const STORY_STEPS = [
  { id: "streets", mode: "season", bare: true, view: { center: [14.69, 120.96], zoom: 13 }, play: false },
  { id: "season", mode: "season", view: { bounds: AREA_BOUNDS }, play: true, firstPass: true },
  { id: "rhythm", mode: "rhythm", view: { bounds: AREA_BOUNDS }, play: false },
  { id: "motion", mode: "motion", view: { bounds: AREA_BOUNDS }, play: false, rhythmUnder: false },
  { id: "priority", mode: "motion", view: { bounds: AREA_BOUNDS }, play: false, rhythmUnder: true, scrollTo: "priority-zones" },
  { id: "barangay", mode: "rhythm", view: { bounds: AREA_BOUNDS }, play: false, focusSearch: true },
];

export const STORY_KEY = "tanaw.story.dismissed";
