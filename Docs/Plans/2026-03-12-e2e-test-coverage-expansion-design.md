# E2E Test Coverage Expansion Design

**Date**: 2026-03-12
**Status**: Approved
**Goal**: Achieve near-full e2e coverage for WebUI and browser extension, simulating real user workflows — replacing manual QA with automated regression and feature validation.

## Approach

**Hybrid (Approach C)**: Page objects for Tier A features (highest churn, most value), lightweight workflow scripts for Tier B/C. Matches existing codebase patterns.

**Test environment**: Real backend with live LLMs where possible, mocks where necessary.
**Assertion strategy**: Strict for deterministic flows (CRUD, auth, settings), behavioral for LLM-dependent flows (chat responses, flashcard generation, transcription).

## Priority Tiers

| Tier | Features | Test Style |
|------|----------|------------|
| A (daily use) | Chat+RAG, Media, Settings, Notes, Flashcards | Page objects + workflow tests |
| B (regular use) | Characters, Audio, Watchlists, Collections, Content Review | Inline workflow scripts |
| C (occasional) | Evaluations, Prompt Studio, Agents/ACP, Writing, Admin | Minimal smoke-plus scripts |

## Current Coverage

### Well-Covered
- Chat (streaming, queuing, tool approval)
- Media ingest + review + navigation
- Search / Knowledge QA
- Settings + onboarding
- Workspace playground
- Collections (stage3)
- Personas + login/auth
- Dictionaries / World Books

### Gaps Identified
- Notes: no tests (full CRUD, search, tagging, export, soft-delete/restore)
- Flashcards: no WebUI tests (generation, study flow, deck management)
- RAG+Chat integration: tested separately, never end-to-end
- Media batch operations: partial (multi-select, batch delete/tag, trash restore)
- Characters: no creation/editing/import-export tests
- Audio STT/TTS: no workflow tests
- Watchlists: no WebUI tests
- Content Review: no tests
- Evaluations, Prompt Studio, Agents, Writing, Admin: no tests
- Extension: no notes, flashcards, context capture, or cross-feature workflows

---

## Section 1: Tier A — Page Objects & Workflow Tests

### 1.1 Notes

**New page object: `NotesPage.ts`**
- Navigate to `/notes`
- Create note (title, content, tags)
- Edit note content
- Search notes by text
- Add/remove tags
- Soft-delete and restore from trash
- Export note

**Workflow tests (`notes.spec.ts`):**
- `create-edit-delete`: Create → edit → verify persistence → soft-delete → verify gone → restore → verify back
- `search-and-filter`: Create 3 notes → search by title → verify results → filter by tag → verify filtered
- `tag-management`: Create note → add tags → verify display → remove tag → verify removal
- `export`: Create note → export → verify downloaded file

Assertions: Strict (deterministic CRUD).

### 1.2 Flashcards

**New page object: `FlashcardsPage.ts`**
- Navigate to `/flashcards`
- Trigger flashcard generation from source content
- Browse deck list
- Enter study mode
- Flip card, mark known/unknown
- View progress stats

**Workflow tests (`flashcards.spec.ts`):**
- `generate-from-media`: Ingest media → navigate to flashcards → generate → verify cards created (behavioral: at least N cards)
- `study-flow`: Open deck → study → flip → mark known → flip next → mark unknown → verify progress
- `deck-management`: Create deck → rename → delete → verify gone

Assertions: Mixed — strict for deck CRUD, behavioral for generated content.

### 1.3 RAG + Chat Integration

Uses existing `ChatPage` + `SearchPage`/`KnowledgeQAPage`. No new page object.

**Workflow tests (`chat-rag-integration.spec.ts`):**
- `search-then-chat-with-context`: Ingest known content → RAG search → inject into chat → verify response references source keywords (behavioral)
- `multi-mode-rag`: Same query in simple vs advanced mode → verify both return results
- `citation-in-chat`: Search → select result with citation → send to chat → verify citation marker

Assertions: Behavioral.

### 1.4 Media Batch Operations

**Extend existing `MediaPage.ts`** with: `selectMultiple()`, `batchDelete()`, `batchTag()`, `navigateToTrash()`, `restoreItem()`

**Workflow tests (`media-batch.spec.ts`):**
- `batch-delete-and-restore`: Ingest 3 → select all → batch delete → verify gone → trash → verify present → restore one → verify back
- `batch-tag`: Ingest 2 → select both → apply tag → filter by tag → verify both appear

Assertions: Strict.

### 1.5 Cross-Feature: Notes → Flashcards

**Workflow test (`notes-to-flashcards.spec.ts`):**
- `generate-flashcards-from-notes`: Create note with study content → generate flashcards from note → verify cards created → study one

Assertions: Mixed.

---

## Section 2: Tier B — Lightweight Workflow Scripts

Inline selectors, no page objects. One spec file per feature.

### 2.1 Characters (`characters.spec.ts`)
- `create-character`: Create with name/description/greeting/system prompt → verify in list
- `chat-with-character`: Select → chat → verify response streams with persona (behavioral)
- `edit-character-settings`: Change model/temperature → save → reopen → verify persisted
- `import-export-png-card`: Import PNG card → verify created → export as PNG → verify download
- `delete-character`: Create → delete → verify removed

### 2.2 Audio STT/TTS (`audio.spec.ts`)
- `tts-generate-and-play`: Select provider/voice → enter text → generate → verify audio player with duration > 0
- `stt-upload-file`: Upload audio → select model → transcribe → verify transcript non-empty (behavioral)
- `voice-catalog-browse`: Open catalog → verify voices → switch provider → verify list changes

### 2.3 Watchlists (`watchlists.spec.ts`)
- `create-source-and-watchlist`: Create watchlist → add source → verify in sources tab
- `run-and-monitor`: Trigger run → verify in runs tab → wait for completion → verify status
- `item-filtering`: After run → items tab → search filter → verify narrowed → status filter → verify further
- `watchlist-settings`: Modify schedule → save → verify persisted

### 2.4 Collections (`collections.spec.ts`)
Extends existing `collections-stage3.spec.ts`:
- `create-collection-with-items`: Create → ingest media → add → verify count
- `edit-collection-metadata`: Edit name/description → save → verify
- `remove-item-from-collection`: Remove → verify count decremented
- `delete-collection`: Delete → verify removed

### 2.5 Content Review (`content-review.spec.ts`)
- `review-queue-flow`: Navigate → verify items → approve one → verify moved → reject another → verify status
- `batch-review`: Select multiple → batch approve → verify all updated
- `claim-extraction`: Select content → trigger extraction → verify claims appear (behavioral)

---

## Section 3: Tier C — Minimal Coverage Scripts

Smoke-plus: page loads, primary action works, nothing crashes.

### 3.1 Evaluations (`evaluations.spec.ts`)
- `run-single-evaluation`: Configure → run → verify result with score (behavioral)
- `batch-evaluation-progress`: Start batch → verify progress → wait → verify results table

### 3.2 Prompt Studio (`prompt-studio.spec.ts`)
- `prompt-crud`: Create prompt with template variable → save → edit → delete → verify
- `test-prompt-against-model`: Fill variable → run → verify response (behavioral)

### 3.3 Agents/ACP (`agents.spec.ts`)
- `browse-agent-registry`: Verify list renders → click agent → verify detail panel
- `create-and-monitor-task`: Create task → verify in task list with status

### 3.4 Writing Tools (`writing.spec.ts`)
- `writing-playground-roundtrip`: Input text → trigger assistance → verify suggestion (behavioral)
- `repo2txt-render`: Input repo → generate → verify formatted output

### 3.5 Admin Pages (`admin.spec.ts`)
- `server-health-dashboard`: Verify health indicators render, no error states
- `data-ops-page-loads`: Verify page renders with action buttons
- `model-management-loads`: Verify model list or empty state

---

## Section 4: Extension-Specific Gaps

### 4.1 Notes (`ext-notes.spec.ts`)
- `sidepanel-save-to-notes`: Chat in sidepanel → save response as note → verify in options `/notes`
- `notes-crud-in-options`: Create/edit/delete through extension options page

### 4.2 Flashcards (`ext-flashcards.spec.ts`)
- `generate-flashcards-from-sidepanel`: Chat → trigger generation → verify cards in options
- `study-mode-in-options`: Open flashcards → study → flip/mark → verify progress

### 4.3 Context Capture (`ext-context.spec.ts`)
- `capture-page-content-to-chat`: Navigate to page → sidepanel → "chat with page" → verify page content in context (behavioral)
- `context-menu-ingest`: Right-click → "Send to tldw_server" → verify notification

### 4.4 Cross-Feature (`ext-cross-feature.spec.ts`)
- `ingest-then-rag-then-chat`: Quick ingest URL → wait for notification → sidepanel RAG search → verify found → chat → verify grounded response
- `hf-pull-button`: Navigate to HuggingFace page → verify button injected → click → verify toast

### 4.5 Audio (`ext-audio.spec.ts`)
- `sidepanel-voice-input`: Activate voice input (mock mic) → verify transcription in composer
- `tts-playback`: Chat → trigger TTS on response → verify audio element

---

## Section 5: Infrastructure

### New Page Objects
| File | Location | Covers |
|------|----------|--------|
| `NotesPage.ts` | `e2e/utils/page-objects/` | `/notes` CRUD, search, tags, soft-delete, export |
| `FlashcardsPage.ts` | `e2e/utils/page-objects/` | `/flashcards` generation, decks, study, progress |

**Extend existing**: `MediaPage.ts` — add `selectMultiple()`, `batchDelete()`, `batchTag()`, `navigateToTrash()`, `restoreItem()`

### Test Fixtures
| Fixture | Purpose |
|---------|---------|
| `e2e/fixtures/test-audio.wav` | Small synthetic WAV for STT tests |
| `e2e/fixtures/test-character.png` | PNG with SillyTavern tEXt metadata |
| `e2e/fixtures/test-document.md` | Markdown with known keywords for RAG assertions |

### New Helper Functions (`e2e/utils/helpers.ts`)
- `ingestAndWait(page, url, title)` — ingest media and poll until complete
- `waitForStreamComplete(page)` — wait for streaming to finish
- `assertFlashcardsGenerated(page, minCount)` — behavioral assertion

### CI Integration

No new workflows. Integrate via tags:

```typescript
test.describe('@tier-a', () => { ... });  // PR gate
test.describe('@tier-b', () => { ... });  // Nightly
test.describe('@tier-c', () => { ... });  // Nightly
```

| Existing Gate | Addition |
|---------------|----------|
| `frontend-ux-gates.yml` smoke job | Tier C specs in all-pages stage |
| `frontend-ux-gates.yml` onboarding job | Notes + flashcards workflows |
| `frontend-ux-gates.yml` **new job: "core-workflows"** | Tier A specs with real backend, ~10 min |
| Nightly schedule | Tier B + C specs |

### Test Count Summary

| Category | New | Existing | Total |
|----------|-----|----------|-------|
| WebUI Tier A | ~15 | ~22 | ~37 |
| WebUI Tier B | ~14 | ~3 | ~17 |
| WebUI Tier C | ~8 | 0 | ~8 |
| Extension | ~10 | ~110 | ~120 |
| Smoke | 0 | 18 | 18 |
| **Total** | **~47** | **~153** | **~200** |
