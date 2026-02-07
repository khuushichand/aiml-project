# Manual QA Checklist: Watchlists/Collections Stage 3

Owner: QA / Dev
Date: 2026-02-07
Scope: Reader highlights + notes UX (`Stage 3` in `Docs/Product/Watchlists-UX-PRD.md`)

## 1. Preconditions

1. Start backend with reading + highlight routes enabled.
2. Start frontend and open `/collections`.
3. Ensure test user has at least one reading item with non-empty content (`clean_html` or `text`).
4. Ensure there is at least one highlight record for that item.

## 2. Focus Areas

1. Selection-based highlight quick actions in reader content tab.
2. Highlight stale badge visibility + filter/search behavior in Highlights tab.
3. Notes autosave + dirty-state protection in item detail drawer.

## 3. Test Cases

### A. Selection-Based Highlight Quick Actions

- [ ] A1. Select non-empty text in `Reading Item Detail -> Content` tab.
  - Expected: selection action panel appears with captured quote.
- [ ] A2. Add highlight from selection panel (`Add Highlight`).
  - Expected: success toast, highlight appears in Highlights tab/list.
- [ ] A3. Re-select the same quote.
  - Expected: panel identifies existing match and shows `Update` + `Delete`.
- [ ] A4. Edit note/color and press `Update`.
  - Expected: highlight updates in-place (note/color/state active).
- [ ] A5. Press `Delete` from selection panel.
  - Expected: highlight is removed from item and global highlights list.
- [ ] A6. Press `Clear`.
  - Expected: selection panel closes and text selection is cleared.

### B. Highlight Stale Badge + Filtering

- [ ] B1. Force one highlight to stale state (via API patch):
  - `PATCH /api/v1/reading/highlights/{highlight_id}` body `{"state":"stale"}`.
  - Expected: response returns `state=stale`.
- [ ] B2. Open `Collections -> Highlights`.
  - Expected: stale highlight shows visible `Stale` badge.
- [ ] B3. Search by quote fragment.
  - Expected: matching highlights only.
- [ ] B4. Filter by color.
  - Expected: highlights respect color filter while preserving search behavior.
- [ ] B5. Group by article toggle on/off.
  - Expected: no highlight loss; stale badge still visible in both modes.

### C. Notes Autosave + Dirty State

- [ ] C1. Open `Reading Item Detail -> Notes`, click `Edit Notes`.
  - Expected: editor appears with status label (`Unsaved changes` after typing).
- [ ] C2. Type notes and pause for >1 second.
  - Expected: status transitions `Saving…` -> `All changes saved`.
- [ ] C3. Re-open same item.
  - Expected: autosaved note content is persisted.
- [ ] C4. Edit notes, then click drawer close immediately.
  - Expected: component attempts save before close; no silent data loss.
- [ ] C5. Simulate save failure (stop backend or offline), then close.
  - Expected: discard confirmation appears; `Cancel` keeps drawer open; `Discard` closes without crash.
- [ ] C6. Use `Cancel` while editing notes.
  - Expected: editor resets to last saved notes and exits edit mode.

### D. Regression Smoke

- [ ] D1. Legacy highlight creation in `Highlights` tab still works.
  - Expected: create/edit/delete flows unchanged.
- [ ] D2. Reading item status/tag/favorite actions still function in drawer.
  - Expected: updates persist and no console errors.
- [ ] D3. Stage 2 import/export panel still loads.
  - Expected: no runtime errors navigating tabs.

## 4. Evidence Log

| Case | Result (Pass/Fail) | Notes / Screenshot |
|---|---|---|
| A1 |  |  |
| A2 |  |  |
| A3 |  |  |
| A4 |  |  |
| A5 |  |  |
| A6 |  |  |
| B1 |  |  |
| B2 |  |  |
| B3 |  |  |
| B4 |  |  |
| B5 |  |  |
| C1 |  |  |
| C2 |  |  |
| C3 |  |  |
| C4 |  |  |
| C5 |  |  |
| C6 |  |  |
| D1 |  |  |
| D2 |  |  |
| D3 |  |  |

## 5. Exit Criteria

1. All A/B/C cases pass.
2. No new console errors on Collections routes.
3. Any D-case regression is documented and triaged before Stage 3 is marked complete.
