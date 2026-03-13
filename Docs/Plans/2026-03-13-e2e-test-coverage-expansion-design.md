# E2E Test Coverage Expansion Design (v2)

**Date**: 2026-03-13
**Status**: Approved
**Supersedes**: `2026-03-12-e2e-test-coverage-expansion-design.md`
**Goal**: Achieve near-full E2E coverage for WebUI and browser extension with systematic dead-button detection and full backend verification — replacing manual QA entirely.

## Context

Solo developer without a QA team. Primary pain points:
1. Buttons that render but do nothing when clicked (dead onClick handlers)
2. APIs not being called or called incorrectly / backend APIs broken

Tests run against a **live local server with real LLM providers**. Thoroughness over speed — full suite can take 30-60+ minutes.

## Approach: Feature Module Specs (Top-Down)

Write dedicated E2E workflow specs for every feature area, with:
- A **network assertion layer** verifying every button fires the correct API with the correct payload
- **Dead button detection** via `assertAllButtonsWired()` on every page
- **Full backend round-trip verification** — click → API called → backend processed → UI updated
- **Cross-feature journey specs** testing multi-page workflows end-to-end

---

## Section 1: Network Assertion Layer

The foundation everything else builds on. Shared utilities that intercept API calls and let any test assert "this button fired this API with this payload and got this response."

### Files

```
e2e/utils/
├── api-assertions.ts      # Core network interception + assertion helpers
├── api-contracts.ts        # Expected request/response shapes per endpoint
└── fixtures.ts             # Extended to include network capture
```

### Core Helpers

- **`expectApiCall(page, matcher)`** — waits for a matching request, returns req+res pair
- **`expectNoApiCall(page, matcher, timeout)`** — asserts a button does NOT fire an API (dead button detection)
- **`assertApiSequence(page, [...matchers])`** — for multi-step flows, asserts calls happen in order
- **`captureAllApiCalls(page)`** — records all `/api/v1/*` traffic during a test block for post-hoc inspection

### Usage Pattern

```typescript
const apiCall = await expectApiCall(page, {
  method: 'POST',
  url: '/api/v1/media/process',
  bodyContains: { url: 'https://youtube.com/watch?v=abc' },
});

await page.getByRole('button', { name: 'Ingest' }).click();

const { request, response } = await apiCall;
expect(response.status()).toBe(200);
expect(await response.json()).toHaveProperty('media_id');
```

### Failure Artifact

On test failure, dump captured API call log as a test attachment alongside trace/screenshot/video:

```typescript
test.afterEach(async ({ page }, testInfo) => {
  if (testInfo.status !== 'passed') {
    const apiLog = getCapturedApiCalls(page);
    await testInfo.attach('api-calls.json', {
      body: JSON.stringify(apiLog, null, 2),
      contentType: 'application/json',
    });
  }
});
```

---

## Section 2: Feature Spec Structure & Page Object Models

### Spec Organization

One spec file per feature module, organized by risk tier:

```
e2e/workflows/
├── tier-1-critical/           # Core functionality
│   ├── media-ingest.spec.ts        # (exists, enhance)
│   ├── chat-completions.spec.ts    # (exists, enhance)
│   ├── search-rag.spec.ts          # (exists, enhance)
│   ├── notes.spec.ts               # NEW
│   ├── collections.spec.ts         # (exists, enhance)
│   └── settings-core.spec.ts       # NEW
│
├── tier-2-features/           # Major feature modules
│   ├── prompt-studio.spec.ts       # NEW
│   ├── prompts-library.spec.ts     # NEW
│   ├── characters.spec.ts          # NEW
│   ├── evaluations.spec.ts         # NEW
│   ├── audiobook-studio.spec.ts    # NEW
│   ├── stt-transcription.spec.ts   # NEW
│   ├── tts-synthesis.spec.ts       # NEW
│   ├── speech-playground.spec.ts   # NEW
│   ├── chatbooks.spec.ts           # NEW
│   ├── sources-connectors.spec.ts  # NEW
│   ├── data-tables.spec.ts         # NEW
│   ├── document-workspace.spec.ts  # NEW
│   ├── content-review.spec.ts      # NEW
│   ├── writing-playground.spec.ts  # NEW
│   ├── kanban.spec.ts              # NEW
│   ├── flashcards.spec.ts          # NEW
│   ├── quiz.spec.ts                # NEW
│   └── mcp-hub.spec.ts             # NEW
│
├── tier-3-automation/         # Agents & workflows
│   ├── acp-playground.spec.ts      # NEW
│   ├── agent-registry.spec.ts      # NEW
│   ├── agent-tasks.spec.ts         # NEW
│   ├── chat-workflows.spec.ts      # NEW
│   └── workflow-editor.spec.ts     # NEW
│
├── tier-4-admin/              # Admin & config
│   ├── admin-server.spec.ts        # NEW
│   ├── admin-llamacpp.spec.ts      # NEW
│   ├── admin-mlx.spec.ts           # NEW
│   ├── admin-orgs.spec.ts          # NEW
│   ├── admin-data-ops.spec.ts      # NEW
│   ├── admin-maintenance.spec.ts   # NEW
│   ├── settings-full.spec.ts       # NEW (all 26 subsections)
│   ├── profile-companion.spec.ts   # NEW
│   ├── notifications.spec.ts       # NEW
│   └── privileges.spec.ts          # NEW
│
├── tier-5-specialized/        # Niche features
│   ├── moderation-playground.spec.ts   # NEW
│   ├── chunking-playground.spec.ts     # NEW
│   ├── model-playground.spec.ts        # NEW
│   ├── repo2txt.spec.ts               # NEW
│   ├── claims-review.spec.ts          # NEW
│   ├── researchers-page.spec.ts       # NEW
│   ├── journalists-page.spec.ts       # NEW
│   ├── osint-page.spec.ts             # NEW
│   └── skills-page.spec.ts            # NEW
│
└── journeys/                  # Cross-feature workflows
    ├── ingest-search-chat.spec.ts      # NEW
    ├── ingest-evaluate-review.spec.ts  # NEW
    ├── create-character-chat.spec.ts   # NEW
    ├── notes-to-flashcards.spec.ts     # NEW
    ├── prompt-studio-to-chat.spec.ts   # NEW
    └── watchlist-ingest-notify.spec.ts # NEW
```

**Total: ~45 new spec files, ~6 enhanced existing specs, 6 cross-feature journey specs.**

### Spec Template

Every spec follows this pattern:

```typescript
import { test, expect } from '../utils/fixtures';
import { expectApiCall, expectNoApiCall } from '../utils/api-assertions';
import { NotesPage } from '../utils/page-objects/notes-page';

test.describe('Notes', () => {
  let notes: NotesPage;

  test.beforeEach(async ({ authedPage }) => {
    notes = new NotesPage(authedPage);
    await notes.goto();
  });

  test('page loads with expected elements', async ({ authedPage }) => {
    await notes.assertPageReady();
  });

  test('create note fires API and shows result', async ({ authedPage }) => {
    const apiCall = await expectApiCall(authedPage, {
      method: 'POST',
      url: '/api/v1/notes',
    });

    await notes.createNote({ title: 'Test Note', content: 'Body text' });

    const { request, response } = await apiCall;
    expect(request.postDataJSON()).toMatchObject({ title: 'Test Note' });
    expect(response.status()).toBe(200);
    await notes.assertNoteVisible('Test Note');
  });

  test('interactive elements are wired', async ({ authedPage }) => {
    await notes.assertAllButtonsWired();
  });
});
```

### New Page Object Models (~25)

Each extends a `BasePage` class with shared `assertAllButtonsWired()` and `assertPageReady()`:

- `NotesPage`, `PromptStudioPage`, `PromptsLibraryPage`, `CharactersPage`, `EvaluationsPage`
- `AudiobookStudioPage`, `STTPage`, `TTSPage`, `SpeechPage`, `ChatbooksPage`
- `SourcesPage`, `DataTablesPage`, `DocumentWorkspacePage`, `ContentReviewPage`
- `WritingPlaygroundPage`, `KanbanPage`, `FlashcardsPage`, `QuizPage`, `MCPHubPage`
- `ACPPage`, `AgentRegistryPage`, `AgentTasksPage`, `ChatWorkflowsPage`
- `AdminPage` (covers all admin sub-pages), `SettingsPage` (extended for all 26 subsections)

---

## Section 3: Dead Button Detection (`assertAllButtonsWired()`)

### Mechanism

Each Page Object declares every interactive element and its expected behavior:

```typescript
async getInteractiveElements(): Promise<InteractiveElement[]> {
  return [
    { locator: this.page.getByRole('button', { name: 'Create Note' }),
      expectation: 'api_call',
      apiPattern: '/api/v1/notes' },

    { locator: this.page.getByRole('button', { name: 'Delete' }),
      expectation: 'modal',
      modalSelector: '[role="dialog"]' },

    { locator: this.page.getByRole('link', { name: 'Settings' }),
      expectation: 'navigation',
      targetUrl: '/settings' },
  ];
}
```

### Assertion Logic

```typescript
async assertAllButtonsWired() {
  const elements = await this.getInteractiveElements();

  for (const el of elements) {
    if (!(await el.locator.isVisible())) continue;

    switch (el.expectation) {
      case 'api_call':
        const call = expectApiCall(this.page, { url: el.apiPattern });
        await el.locator.click();
        await call;  // throws if no API call fires
        break;

      case 'modal':
        await el.locator.click();
        await expect(this.page.locator(el.modalSelector)).toBeVisible();
        await this.page.keyboard.press('Escape');
        break;

      case 'navigation':
        await el.locator.click();
        await expect(this.page).toHaveURL(new RegExp(el.targetUrl));
        await this.page.goBack();
        break;

      case 'state_change':
        const before = await el.stateCheck(this.page);
        await el.locator.click();
        const after = await el.stateCheck(this.page);
        expect(after).not.toEqual(before);
        break;
    }
  }
}
```

### Why Explicit Over Automatic Discovery

- **Destructive actions** — blindly clicking "Delete All" is dangerous
- **Stateful forms** — clicking "Submit" on an empty form tests error handling, not functionality
- **Order dependence** — some buttons only work after setup steps
- **Clear failure messages** — "Button 'Export' expected to fire `/api/v1/chatbooks/export` but no API call was made"

Maps can be built incrementally — start with workflow tests, fill in `getInteractiveElements()` over time.

---

## Section 4: Cross-Feature Journey Specs

Test multi-page workflows that mirror real user behavior.

### `ingest-search-chat.spec.ts`
1. Navigate to media ingestion → submit a URL
2. Assert `POST /api/v1/media/process` → wait for processing
3. Navigate to search → search for ingested content
4. Assert `POST /api/v1/rag/search` → verify item appears
5. Navigate to chat → ask about the content
6. Assert `POST /api/v1/chat/completions` with RAG context → verify response references content

### `ingest-evaluate-review.spec.ts`
1. Ingest content
2. Navigate to evaluations → run evaluation
3. Assert evaluation API → verify results
4. Navigate to content review → verify evaluated content with scores

### `create-character-chat.spec.ts`
1. Navigate to characters → create character card
2. Assert creation API → verify saved
3. Navigate to chat → select character → send message
4. Assert chat completions fires with character system prompt

### `notes-to-flashcards.spec.ts`
1. Create note with structured content
2. Navigate to flashcards → generate from note
3. Assert generation API → verify cards created
4. Review a flashcard → verify content matches source

### `prompt-studio-to-chat.spec.ts`
1. Navigate to prompt studio → create and test a prompt
2. Assert prompt save API
3. Navigate to chat → select saved prompt → send message
4. Verify prompt applied in API call

### `watchlist-ingest-notify.spec.ts`
1. Create watchlist with source URL
2. Assert watchlist creation API
3. Trigger run → assert run API
4. Verify notification on completion
5. Navigate to media → verify ingested items

### Shared Journey Utilities

```typescript
// e2e/utils/journey-helpers.ts

async function ingestAndWaitForReady(page, input): Promise<string> {}
async function createNote(page, opts): Promise<string> {}
async function createCharacter(page, opts): Promise<string> {}
```

### Failure Isolation

Each journey uses `test.step()` for clear reporting:

```typescript
test('ingest → search → chat pipeline', async ({ authedPage }) => {
  const mediaId = await test.step('Ingest media', async () => { ... });
  await test.step('Search finds ingested content', async () => { ... });
  await test.step('Chat references ingested content', async () => { ... });
});
```

---

## Section 5: Test Runner Configuration & Tiering

### Playwright Projects

```typescript
projects: [
  { name: 'smoke', testDir: './e2e/smoke' },
  { name: 'tier-1', testDir: './e2e/workflows/tier-1-critical' },
  { name: 'tier-2', testDir: './e2e/workflows/tier-2-features' },
  { name: 'tier-3', testDir: './e2e/workflows/tier-3-automation' },
  { name: 'tier-4', testDir: './e2e/workflows/tier-4-admin' },
  { name: 'tier-5', testDir: './e2e/workflows/tier-5-specialized' },
  { name: 'journeys', testDir: './e2e/workflows/journeys' },
]
```

### NPM Scripts

```json
{
  "e2e:all": "playwright test",
  "e2e:smoke": "playwright test --project=smoke",
  "e2e:tier1": "playwright test --project=tier-1",
  "e2e:tier2": "playwright test --project=tier-2",
  "e2e:tier3": "playwright test --project=tier-3",
  "e2e:tier4": "playwright test --project=tier-4",
  "e2e:tier5": "playwright test --project=tier-5",
  "e2e:journeys": "playwright test --project=journeys",
  "e2e:critical": "playwright test --project=smoke --project=tier-1 --project=journeys",
  "e2e:features": "playwright test --project=tier-2 --project=tier-3",
  "e2e:admin": "playwright test --project=tier-4 --project=tier-5"
}
```

### Expected Execution Times

| Suite | Spec Count | Estimated Time |
|-------|-----------|----------------|
| Smoke (existing) | 16 | ~3-5 min |
| Tier 1 (critical) | 6 | ~5-8 min |
| Tier 2 (features) | 18 | ~15-25 min |
| Tier 3 (automation) | 5 | ~5-8 min |
| Tier 4 (admin) | 10 | ~8-12 min |
| Tier 5 (specialized) | 9 | ~5-8 min |
| Journeys | 6 | ~10-15 min |
| **Full suite** | **~70 specs** | **~40-60 min** |

### Timeout Configuration

```typescript
{
  retries: 2,
  timeout: 60_000,
  expect: { timeout: 15_000 },

  // Journey specs get longer timeouts (multi-page, backend processing)
  projects: [{
    name: 'journeys',
    timeout: 120_000,
    expect: { timeout: 30_000 },
  }]
}
```

---

## Section 6: Extension Coverage Strategy

The extension already has 109 E2E specs. Gaps to fill are extension-specific concerns.

### New Extension Specs (~8 files)

| Spec | Purpose |
|------|---------|
| `background-proxy-api.spec.ts` | Verify `bgRequest()` reaches backend with correct payloads |
| `sidepanel-options-handoff.spec.ts` | State transfer between sidepanel and options page |
| `copilot-popup.spec.ts` | Full right-click → popup → action → API flow |
| `hf-pull-content.spec.ts` | HuggingFace model pull integration |
| `reconnection.spec.ts` | Server disconnect → graceful degradation → reconnect |
| `cross-context-sync.spec.ts` | Settings change in options → sidepanel reflects without reload |
| `context-menu-actions.spec.ts` | All right-click menu items fire correct actions |
| `extension-api-assertions.spec.ts` | Systematic button→API verification for extension-specific pages |

### Reuse Strategy

- Network assertion layer (`api-assertions.ts`) in shared `apps/packages/ui/` — both webui and extension tests import it
- Page Objects for shared features reused across both — instantiated with different page contexts
- Extension-specific Page Objects stay in `apps/extension/tests/e2e/utils/`

---

## Deliverables Summary

| Category | New Files | Enhanced Files |
|----------|-----------|----------------|
| Shared utilities | 3 | 1 (fixtures.ts) |
| Page Object Models | ~25 | — |
| WebUI tier 1 (critical) | 2 | 4 |
| WebUI tier 2 (features) | 18 | — |
| WebUI tier 3 (automation) | 5 | — |
| WebUI tier 4 (admin) | 10 | — |
| WebUI tier 5 (specialized) | 9 | — |
| Journey specs | 6 | — |
| Extension specs | 8 | — |
| Config updates | 1 (playwright) | 1 (package.json) |
| **Total** | **~87 new files** | **~6 enhanced** |

## What This Catches

- Buttons that render but do nothing (dead handlers)
- API calls with wrong endpoints or payloads
- Backend errors not surfaced to the UI
- Regressions across features after code changes
- Data not flowing between features (ingest→search→chat pipeline)
- Extension-specific communication failures

## Out of Scope

- Visual regression testing (pixel diffs)
- Performance benchmarks (extension already has some)
- Load testing / concurrent users
- Browser compatibility beyond Chromium
