# Tanaw integration check — 15 November 2026

Completed by Codex with Terra agents after the user asked it to finish the remaining integration and handoff tasks. This is a software check, not observed radar validation or user research.

## Implemented

- The spot-check card now reads the composed `/api/v1/spot-check` facts rather than four separate endpoints. Place, flood, rainfall and motion panels retain source information and missing-value reasons. Priority membership and barangay-level priority exposure are included, with the geographic scope stated.
- English and Filipino HTML briefing buttons and CSV download use the existing API error handling. Synthetic products and pending translation review remain visible. If a browser blocks the new tab, HTML falls back to a downloaded file.
- Frontend fixture modes disable composed spot/briefing/validation requests, avoiding a synthetic map being paired with unrelated backend facts or accuracy scores. Default backend mode remains the mode for integration checks.
- The independent-comparison card is connected in Flood rhythm and Ground motion. It shows unavailable until a compatible observed result exists; literature and synthetic data do not become accuracy scores.
- Four referenced hypotheses are populated in the schema the existing panel expects. Each remains labelled as a hypothesis; the unsupported fishpond claim was excluded.
- The pass legend uses the backend renderer's shared colour constants. Data credits are available in the Limits drawer; the map retains its OpenStreetMap attribution.
- `FIL_REVIEW.md` covers 345 UI keys, four hypothesis titles and summaries, and 13 briefing-template entries. Placeholder checks passed. The user will review the wording; no sign-off is claimed.
- Source availability, date alignment and access limitations were reviewed in `SOURCE_REVIEW.md`. No matching independent reference and observed NISAR pair was available; no agreement was computed.

## Checks completed on the laptop

- Backend: all 337 unit tests passed on Windows.
- Frontend: lint passed; production build passed; three client API regression tests passed. The client tests cover coordinate/language query parameters, CSV bytes, unavailable export/validation responses, and fixture isolation. CI now runs them.
- Running backend: the point `120.957, 14.665` resolves to **Niugan, City of Malabon** in the cached COD-AB boundaries. English and Filipino briefing JSON facts matched the spot-check stream values. Both HTML exports and the 19-row CSV returned successfully. Filipino HTML retained the pending-review notice.
- Missing radar, motion and priority values remained null with reasons. An out-of-coverage point returned 404 `outside_coverage`; validation returned 404 `data_unavailable`.
- The production frontend homepage and hypothesis JSON returned HTTP 200. Rainfall monthly history from 2000 and timeline availability returned HTTP 200.

## Checks that remain

Computer Use stopped because it could not confidently identify the current Opera URL on Windows. No screenshots, visual tile check, coastline alignment, responsive layout, keyboard walkthrough or browser-click export check were completed. Direct HTTP checks do not establish those behaviours.

For the manual laptop check, open `http://127.0.0.1:3000/?lon=120.957&lat=14.665` with the backend running on port 8000:

1. At 1366×768, confirm streets and OpenStreetMap attribution are visible; inspect both CAMANAVA and Regional context. Verify no clipping or horizontal overflow. Check 390×844 as well.
2. Search Niugan or Malabon, open its spot check, switch EN/FIL and inspect the review notice. Tab through the controls and close dialogs with Escape.
3. Open Briefing (EN), Briefing (FIL), and Download CSV. Compare their values and missing-data reasons with the spot card, and check print preview.
4. Open History at 2000 and a recent year. Open Future and verify the conditional-scenario caveat. Open Flood rhythm and Ground motion; absent products and validation must show unavailable.
5. Open Limits and follow the source credits. If real radar products become available later, check overlay/coastline alignment without shifting the frontend imagery.

## Recording readiness

The current build is **not an observed NISAR demonstration**. T1/T2 remain user-deferred; no flood counts, measured motion, priority population, agreement score or causal finding should be narrated as an observed result. The original scope's example numbers and story claims are not recording evidence. Real-data readiness, user wording review and the manual checks above remain open.

An honest 30-second draft for the present build, to time and refine before recording:

> Tanaw helps researchers and students explore environmental change in CAMANAVA. Compare NASA POWER rainfall since 2000, locate a barangay, and export a sourced briefing in English or Filipino. Our NISAR flood and ground-motion tools are implemented, but actual radar results remain unavailable in this build. Tanaw is open source, with missing data and limitations visible.

Suggested shots: map and study outline → historical rainfall → barangay search → briefing export → explicit radar-unavailable state → project name and repository link. This is a draft; no recording, public hosting, external user test or native-language approval was performed.
