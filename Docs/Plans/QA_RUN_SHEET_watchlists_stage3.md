# QA Run Sheet: Watchlists/Collections Stage 3

## Quick Start (Copy/Paste)

```bash
# Terminal 1: backend
python -m uvicorn tldw_Server_API.app.main:app --reload

# Terminal 2: frontend
cd apps/tldw-frontend
bun run dev
```

Open:
- Web UI: `http://localhost:3000/collections`
- Backend docs: `http://127.0.0.1:8000/docs`

## Required Setup

1. Ensure server auth is configured for your local run.
2. Ensure at least one reading item has content text.
3. Ensure `Collections` page is reachable and connected.

## Run Steps

### 1) Selection Highlight Flow

1. Open `Collections -> Reading List`.
2. Open any item detail.
3. In `Content` tab, select a text phrase.
4. In the selection panel, set color/note and click `Add Highlight`.
5. Re-select the same phrase, click `Update`.
6. Re-select again, click `Delete`.

Pass if:
- Selection panel appears.
- Add/Update/Delete actions complete without UI errors.

### 2) Stale Badge + Filters

1. Patch one highlight to stale:
   - `PATCH /api/v1/reading/highlights/{id}` with `{"state":"stale"}`.
2. Open `Collections -> Highlights`.
3. Verify stale item shows `Stale` badge.
4. Use search + color filter and confirm stale item handling remains correct.

Pass if:
- `Stale` badge is visible.
- Search/filter results remain correct.

### 3) Notes Autosave + Dirty Protection

1. Open item detail -> `Notes`.
2. Click `Add Notes` or `Edit Notes`.
3. Type text and pause.
4. Verify state transitions:
   - `Unsaved changes` -> `Saving…` -> `All changes saved`.
5. Close drawer, reopen item, verify note persisted.
6. Optional failure path: force save failure, close drawer, verify discard-confirm behavior.

Pass if:
- Autosave status appears and transitions correctly.
- Notes persist after reopen.
- No silent data loss on close.

## Result Log Template

```text
Run Date:
Tester:
Environment:

Selection Highlight Flow: PASS/FAIL
Notes:

Stale Badge + Filters: PASS/FAIL
Notes:

Notes Autosave + Dirty Protection: PASS/FAIL
Notes:

Overall Stage 3 Manual QA: PASS/FAIL
Blocking Issues:
```
