# Tanaw interface design spec v2 ("Mangrove")

This is the approved design for restyling the Tanaw frontend. It is Antigravity task **A6** (see `docs/ANTIGRAVITY_TASKS.md`).

- **Design canvas (private to the project owner):** https://claude.ai/artifact/RfXSbuREG44jnVdYaPdvq3. Ask the owner for a share link or screenshots if you need to see it.
- **Board source, for exact markup and styles:** `docs/design/v2-mangrove/*.dc.html`. These files are Claude Design components and won't render on their own. Read them for structure, spacing and colours; don't copy their runtime.

| Board file | Screen |
|---|---|
| `MapFirst.dc.html` | Flood rhythm, the first view |
| `Season.dc.html` | Season (single pass with before/after swipe) |
| `Motion.dc.html` | Ground motion, with the Map tools panel open |
| `History.dc.html` | History |
| `Future.dc.html` | Future (scenario picker is interactive) |
| `MapTools.dc.html` | Map tools panel, interactive |
| `PhoneV2.dc.html` | Phone layout |
| `Palettes.dc.html` | Palette options; **Mangrove was chosen** |

## 0. Ground rules

1. **Restyle and re-lay-out; don't rewire.** Keep every API call, data hook, error state and test that exists. Change layout, styling and where components sit. If the design needs data the API doesn't provide, show the existing unavailable state and log a `NEEDS-BACKEND:` line in `docs/ANTIGRAVITY_STATUS.md`.
2. **Stay inside `frontend/`.** Do not edit `backend/`.
3. **Honesty rules still apply** (`AGENTS.md` §2). Never show a number without its source. Synthetic values always carry a **Demo** tag (see §4.9). Say "exposure", not "damage", and "line-of-sight motion", not "sinking". Scenarios are "conditional, not predictions".
4. **No invented content.** The boards use placeholders like `[km²]` and `[n]`. In the app those come from the API. The board's map shapes and chart bar heights are illustrations; only the History and Future rainfall numbers on the boards are real.
5. Run `npm run lint`, `npm run build` and `npm run test:api` before every push.

## 1. Who it's for, and the feel

- **Primary audience:** judges and the general public. Secondary: researchers and students. Plain language first, with method details one click away.
- **Feel:** calm civic, with the precision of a scientific instrument. Generous white space, aligned numbers and precise labels.
- **Laptop first** (1366×768 is the target). The phone layout must be usable but doesn't get extra features.

## 2. Design tokens

Put these in `frontend/app/globals.css` as CSS variables, and extend `tailwind.config.js` with them so components use names, not hex values.

### 2.1 Interface colours (Mangrove)

| Token | Hex | Use |
|---|---|---|
| `--primary` | `#1E5B3A` | Brand, active states, primary buttons, focus ring |
| `--primary-strong` | `#123B25` | Text on `--primary-soft`, hover on primary |
| `--primary-soft` | `#E3EFE7` | Active rail item, selected chips, tints |
| `--ground` | `#F2F5F1` | Page background, stat-card background |
| `--surface` | `#FFFFFF` | Panels, cards, header |
| `--ink` | `#16231B` | Body text |
| `--muted` | `#4A5850` | Secondary text (6.8:1 on ground) |
| `--line` | `#DCE3DB` | Borders and dividers |
| `--demo-bg` | `#FFF6DE` | Demo tag background |
| `--demo-ink` | `#7A5B00` | Demo tag text and border (5.9:1) |

Measured contrast: primary on white is 8.0:1; muted on ground is 6.8:1.

### 2.2 Data colours (these mean the same thing everywhere; never use them for interface chrome)

| Meaning | Colours |
|---|---|
| Flood rhythm, 4 classes (water on 1–2 / 3–5 / 6–8 / 9–11 passes) | `#C6DBEF` `#6BAED6` `#2171B5` `#08306B` |
| Open water on a single pass | `#2171B5` |
| Possible flooded vegetation (L-band) | `#E69F00`, drawn as a **diamond** in legends |
| Permanent water (not counted) | `#D3E2EA` fill, `#9DB6C4` outline |
| Ground motion, line-of-sight: away from satellite → stable → toward | `#7B3294` `#9970AB` `#C2A5CF` `#F2F0F2` `#A6DBA0` `#1B7837` |
| Flood scenario (exploratory) | violet hatching: `#6B5A9E` lines on `#E7E3F1` |
| Outlook months | dashed `#2171B5` outline on `#DCEAF5` |
| Scenario months | `#8A7BB5` |
| Rain bars on the timeline | `#6BAED6` (selected window `#2171B5`) |

The backend renders the per-pass PNGs in `#0072B2` (water) and `#E69F00` (vegetation). If the API returns a `legend` array, use its colours for those overlays. The rhythm legend comes from the API already.

Each mode's eyebrow label takes its data colour:
- Flood rhythm and Season: `--primary`.
- Ground motion: `#7B3294`.
- Future: `#6B5A9E`.

### 2.3 Type

- **Headlines, place names and map water labels:** **Source Serif 4** (weights 500–700), loaded with `next/font/google`.
- **Everything else:** **Inter** (400–700), loaded with `next/font/google`. Replace Geist.
- **All numbers** use `font-variant-numeric: tabular-nums`.

| Role | Font | Size and weight |
|---|---|---|
| Findings headline | Serif | 25px / 600, line-height 1.22 |
| Phone headline | Serif | 21px / 600 |
| Spot-card place name | Serif | 19px / 600 |
| Section title ("In plain words") | Serif | 16px / 600 |
| Stat value | Inter | 24px / 700 (22px in 3-column grids) |
| Body text | Inter | 13px, line-height 1.6 |
| Labels | Inter | 12px, `--muted` |
| Eyebrow | Inter | 11px / 700, letter-spacing 0.08em, uppercase |
| Wordmark "TANAW" | Inter | 19px / 700, letter-spacing 0.06em |

### 2.4 Shape and space

- **Radii:** 14px for panels, floating cards and the app frame; 12px for stat cards and buttons; 9–10px for small buttons; 4px for tags.
- **Shadows:** floating map controls use `0 2px 8px rgba(20,30,40,.12)`; the open panel and spot card use `0 6px 20px rgba(20,30,40,.18)`.
- **Spacing:** a 4px base. Panels have 20px padding, and sections are 14–16px apart.
- **Touch targets:** at least 44px for every control. Small chips may be 36px only if they have 4px spacing around them.

## 3. Layout shell (laptop)

The app sits in a 12px margin on `--ground`, inside one `--surface` frame with a 1px `--line` border and 14px radius.

```
┌ header 58px ──────────────────────────────────────────────────────────┐
│ [logo] TANAW │ CAMANAVA · 2026 wet season        Take the tour · Sources and limits · ⚙ │
├──────┬───────────────────────────────────────────────┬────────────────┤
│ rail │ MAP (flex 1)                                  │ findings panel │
│ 84px │ [search, top-left]           [Map tools ▾]    │ 300–340px      │
│      │                                               │ (420–480px in  │
│      │ [spot card, bottom-left]     [legend, b-right]│  History and   │
│      │                                               │  Future)       │
├──────┴───────────────────────────────────────────────┴────────────────┤
│ footer timeline: ‹ date › ▶ │ slider with rain bars and pass dots │ caption │
└───────────────────────────────────────────────────────────────────────┘
```

### 3.1 Header
- **Left:** a line-mark logo (see the SVG in `MapFirst.dc.html`) and the "TANAW" wordmark, then a 1px divider, then the area title "CAMANAVA · 2026 wet season". **Render the title as plain text, with no dropdown arrow**, until a second area or season exists. The board shows an arrow; the owner hasn't confirmed it, so drop it.
- **Right:**
  - "Take the tour": an outlined primary button that opens the existing `StoryTour`.
  - "Sources and limits": a text link that opens the existing `LimitsDrawer`.
  - A gear button: the **Settings** menu.
- **Settings menu:** Language (English default / Filipino), Base map (mirrors Map tools), "Regional context (Sentinel-1 2022–2025)" link, and "Pipeline preview (synthetic)" toggle (off).
- The old header mode buttons, EN/FIL toggle and "Regional context" button are **removed from the header**.

### 3.2 Left mode rail (84px)
- **Five modes, each an icon above a short label** (paths are in the boards): Season, Flood rhythm, Ground motion, History, Future.
- **Active item:** `--primary-soft` background, `--primary` text, 700 weight, and `aria-current="page"`.
- **Bottom of the rail:** "Layers" (opens Map tools) and "How radar sees" (opens the existing `RadarCards`).
- **First view is Flood rhythm**, not Season.

### 3.3 Map
- **Search:** a large search box floats top-left. It is 52px tall, max 400px wide, 14px radius, with a shadow. Placeholder: "Find my barangay or city". It reuses `SearchBox` behaviour; results drop down under it.
- **Map tools:** a button floats top-right (§4.3). On Flood rhythm the zoom buttons stack beside it, as Leaflet zoom restyled to match.
- **Spot card:** floats bottom-left (§4.5) and appears only after a map click or a search result.
- **Legend:** floats bottom-right, specific to the overlay (§4.4).
- **Attribution:** keep the OpenStreetMap and NISAR (NASA/ISRO via ASF) attribution visible at bottom-right in 10px text.

### 3.4 Findings panel (right)
Pattern (§4.6): eyebrow → serif headline sentence → stat cards → "In plain words" → source line pinned to the bottom.

### 3.5 Footer timeline
A stepper on the left, then a slider, then a caption (§4.8).

## 4. Components

### 4.1 Buttons
- **Primary:** `--primary` fill, white 600 text, 12px radius, 40–44px tall.
- **Secondary:** 1px `--primary` border, `--primary` text, on surface.
- **Quiet:** text only, `--ink`.
- **Focus:** a 2px `--primary` outline with 2px offset on every interactive element.

### 4.2 Mode rail item
See §3.2. It shows a label and icon in every state; never icon-only.

### 4.3 Map tools (new; see `MapTools.dc.html`, which works in Play)

**Closed button:**
- 44px tall: layers icon, then "Map tools", then a live summary in 11px muted text, then a chevron.
- Example summary: "Flood rhythm · Streets · 4 layers".
- `aria-expanded` reflects the state.

**Open panel:** a 316–340px dialog under the button, with max-height and scroll, `aria-label="Map tools"`. Escape closes it and returns focus to the button. It has three sections:

1. **Map mode:** a radio group of three tiles with small preview swatches.
   - **Streets** (default): light muted streets.
   - **Satellite.** If no free, key-less satellite tiles that allow this use can be found, hide this tile and log it.
   - **Minimal:** coastline, rivers and boundaries only.
2. **Overlay, one at a time:** a radio list. Each item has a swatch, a label and a one-line hint:
   - Flood rhythm: "How often each place had water, all passes".
   - Single NISAR pass: "Water on one date; pick it on the timeline".
   - Ground motion: "Line-of-sight motion, 23 Jun – 21 Oct".
   - Flood scenario: "Exploratory what-if for a chosen month".

   The selected overlay shows its options in an indented box (2px left border in `--primary`), followed by an opacity slider:
   - **Flood rhythm:** show permanent water; show possible flooded vegetation.
   - **Single pass:** radar image underneath (HH, and Polarization if available); compare two passes with a swipe.
   - **Ground motion:** outline often-flooded areas; show the reference area.
   - **Flood scenario:** show the observed flood rhythm underneath.
3. **Layers:** checkboxes for barangay boundaries (on), place labels (on), roads (off), rivers and waterways (on), study-area outline (on), and buildings from OpenStreetMap (off).

**Footer:** "Reset map" (underlined text button) and "Done" (primary).

**Overlay selection follows the mode by default.** Entering a mode selects its overlay: Season gives single pass, Flood rhythm gives rhythm, Ground motion gives motion, Future gives scenario, and History gives no NISAR overlay (it shows the NASA POWER grid-cell outline). The user can switch the overlay within a mode. This replaces the old separate HH/Polarization switch and the Streets/Satellite switch.

### 4.4 Legend card
- Surface card, 12px radius, 12px text, with a 600-weight title naming what is drawn.
- **Flood rhythm:** a 4-swatch bar labelled "1–2, 3–5, 6–8, 9–11" (use the API `legend` if present), plus possible flooded vegetation (diamond), permanent water and study area (dashed line).
- **Ground motion:** a 6-step bar labelled "Away from satellite / Stable / Toward", plus a reference-area square.
- **Every legend shows shape as well as colour** (diamond, dashed line, hatching), so nothing relies on colour alone.

### 4.5 Spot card (bottom-left of the map)
This replaces the right-panel spot check. It is a 330px card (max `100% - 32px`) with 14px radius and the strong shadow, `role="dialog"`, `aria-label="Spot check: <barangay>, <city>"`. Escape or × closes it.

Contents, top to bottom:
- Place name in serif 19px; city and coordinates in 12px muted text; a close button.
- One headline fact for the current mode:
  - Rhythm: "Flooded on N of M valid passes".
  - Motion: "X mm away from the satellite since 23 Jun".
  - Season: that pass's state.
  - A Demo tag when the value is synthetic.
- A 2-column fact grid, such as "Rain, 7 days before <date>" (real, NASA POWER) and "Ground motion" (value or "Not available yet").
- In Ground motion, a small point time-series line.
- Buttons: **Briefing** (primary; opens the HTML briefing in the current language), **CSV**, and **Full details**. "Full details" expands the existing full spot-check content in the findings panel, with a "Back to area findings" link.

All existing `/api/v1/spot-check` and briefing wiring (Codex T4) stays; only the placement changes.

### 4.6 Findings panel pattern
- **Eyebrow:** "<MODE> · <CONTEXT>", e.g. "FLOOD RHYTHM · 2026 WET SEASON" or "SEASON · PASS 3 OF 11".
- **Headline:** one serif sentence that states the finding with the number inside it, e.g. "[km²] of CAMANAVA was under water on half or more of the season's passes". Build it from API fields in `i18n.js` templates. **Never hard-code the number.**
- **Stat cards:** 2×2 (3 across in History and Future). Each card has a 12px muted label, a 24px/700 value and an optional 11px sub-line. Cards use the `--ground` fill with a `--line` border and 12px radius.
- **"In plain words":** a serif 16px title and a 13px paragraph from an `i18n.js` template filled with API values. Where a value is missing, the sentence says so instead of showing a number.
- **Source line:** pinned at the bottom in 11px muted text, e.g. "NISAR L2 GCOV · track 140 ascending · 30 m · Sources and limits".

### 4.7 Before/after swipe (Season)
- A vertical 3px `--primary` divider with a 44px round handle. Arrow keys move it, and it has an aria-label.
- Date chips sit above each side: the earlier pass on a white chip, the current pass on a primary chip.
- The existing clip logic stays.

### 4.8 Timeline (footer)
- **Stepper:** ‹ date › and a round primary ▶ play button. The date label is "Whole season" in Flood rhythm, the pass date in Season, and "Total, 23 Jun → 21 Oct" in Ground motion.
- **Slider:** 46px tall on `--ground`, `role="slider"` with `aria-valuetext`. Behind it, **real daily NASA POWER rain bars** (`/climate/rainfall/daily`), using square-root height scaling so the 105 mm day on 8 Aug doesn't flatten everything. Dots mark the NISAR passes; the selected pass is a larger primary dot and a compared pass is light blue. In Season, the 7 rain days before the selected pass are highlighted.
- **Caption:** "Bars: daily rain, NASA POWER. Dots: NISAR passes."
- **History footer:** a "What data exists when" ribbon, 2000–2026, with one bar each for NASA POWER, Landsat, Sentinel-1 and NISAR, from `/timeline/availability`.
- **Future footer:** a three-part band: "Observed to Nov 2026", "Outlook · Dec – Apr" (dashed) and "Conditional scenario · May – Nov 2027", plus a month stepper.

### 4.9 Demo tag (replaces the yellow banner)
- **The owner chose demo marking on the numbers only.** Remove the full-width yellow SYNTHETIC banner.
- Every synthetic value gets a small tag next to it: "Demo", or "Demo number" under a headline. The tag has a dashed `--demo-ink` border, `--demo-bg` fill, 11px/600 text and 4px radius. Its tooltip and accessible name read "Synthetic demo data, not a NISAR observation".
- Synthetic **map overlays** also get a "Demo" tag in their legend title, and the Map tools summary shows "(demo)" after the overlay name. A synthetic layer must never appear with no marker anywhere on screen.
- Drive all of this from the API's `dataKind === "synthetic"`, as the current banner logic does.

### 4.10 Unavailable states
Keep the existing unavailable messages, restyled as a soft card: dashed `--line` border, `--ground` fill, an info icon and 13px text, e.g. "Not available yet. Waiting for the NISAR interferogram run and its review."

## 5. Screens

| Mode | Overlay | Findings headline | Stat cards | Notes |
|---|---|---|---|---|
| **Flood rhythm** (first view) | Rhythm classes | "[km²] of CAMANAVA was under water on half or more of the season's passes" (from `halfOrMoreKm2`) | NISAR passes (count), Valid coverage, People living there, Buildings there (`/places/exposure?mask=rhythm_half`) | Spot card on click |
| **Season** | Single pass, with swipe compare | "<date>: [km²] of CAMANAVA under water" | Change since the previous pass, Rain in the 7 days before (real), Possible flooded vegetation, Valid coverage | Show **UTC and Manila time**: a 21:30 UTC pass is 05:30 the **next day** in Manila. Label it as on the board: "Radar pass at 21:30 UTC on 17 Jul, which is 05:30 on 18 Jul in Manila". |
| **Ground motion** | Line-of-sight motion | "Parts of the coast moved [mm] away from the satellite in four months" | Interferogram pairs, Period, Area moving away, Also often flooded (priority zones) | Until the real run exists, show the unavailable card in the panel and on the map. The plain-words text explains line of sight vs vertical. |
| **History** | NASA POWER grid-cell outline (about 50 km) over the study area | "An ordinary season so far, with one extreme month" (wording follows `/season-rank`; don't hard-code the conclusion) | 2026 rank (14th of 27, same window), August 2026 (606 mm, +126%), trend (+31 mm per decade, 95% range) | Bar chart of Jun–Nov totals 2000–2025, plus 2026 hatched as incomplete; the wettest year in `#08306B` |
| **Future** | Exploratory scenario hatching | Outlook sentence built from the anomaly signs, e.g. "drier than usual through April 2027" | Outlook coverage, December vs model normal, Flood scenario (exploratory) | 2×2 scenario picker. 12-month bars: outlook months dashed, with model-mean dots; scenario months solid. **Keep the NASA POWER dry-season caveat directly under the chart.** |

## 6. Phone (below 900px wide)
- **Header:** logo, wordmark, short area name and the gear button.
- **Map:** about 330px tall. Full-width search on top, a round 44px Map tools button below it on the right, and a compact legend.
- **Findings:** a bottom sheet with an 18px top radius, a grab handle, eyebrow, serif headline (21px), 2 stat cards, and the plain-words text truncated with "Read more".
- **Bottom tab bar:** the five modes as icon and label (Season, Rhythm, Motion, History, Future), replacing the rail.
- **Spot card:** opens as a sheet on phones.

## 7. Motion (purposeful only)
- **Fly-to:** map fly-to on search or spot select, at most 600ms.
- **Pass changes:** a cross-fade of 250ms during playback and stepping.
- **Numbers:** count up once on first load only.
- **Panels:** Map tools and the spot card fade and slide 8px, 150ms.
- **Reduce motion:** respect `prefers-reduced-motion`. Every transition becomes instant and playback steps without fades.

## 8. Accessibility checklist
- [ ] All controls are reachable and usable by keyboard, with visible focus. Escape closes the dialogs (Map tools, spot card, settings, tour).
- [ ] Text contrast is at least 4.5:1, including the 11–12px labels. The tokens above pass.
- [ ] Legends and states use shape or pattern as well as colour.
- [ ] Map overlays have text alternatives: the findings headline and legend describe what is drawn.
- [ ] `aria-current` is set on the active mode, `aria-expanded` on toggles, and `role="slider"` with `aria-valuetext` on the timeline.
- [ ] The layout works at 1366×768 with no horizontal scroll, and at 390×844.

## 9. Language
- English is the default. Filipino is chosen in **Settings**; the choice is remembered in `localStorage`, wrapped in try/catch.
- All new strings go in `frontend/utils/i18n.js`. Mark new Filipino strings "pending native review" until the team's reviewer signs them off (`docs/FIL_REVIEW.md`).

## 10. Acceptance
- [ ] The app opens on Flood rhythm, with the shell and Mangrove tokens as above.
- [ ] All five modes match their boards in layout, colour and type, using real API data or the existing unavailable states.
- [ ] Map tools works: map mode, overlay with its options, layers, reset, and a summary on the closed button.
- [ ] The spot card sits bottom-left with Briefing, CSV and Full details wired to the existing endpoints.
- [ ] The yellow banner is gone, and every synthetic number and overlay carries a Demo tag.
- [ ] Pass times show both UTC and Manila time.
- [ ] Lint, build and `test:api` pass. There are no console errors on the real backend.
- [ ] Screenshots of every mode (1366×768) and the phone view are committed to `frontend/screenshots/v2/`.

## 11. Out of scope
Radar lens, GIF/MP4 export, new backend fields, satellite tiles that need a key or payment, and any change to analysis logic or wording rules.
