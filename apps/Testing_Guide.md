# Testing Guide (apps)

Central reference for running tests across the shared UI codebase (extension + webapp).

## Prerequisites
- A running `tldw_server` instance accessible over HTTP.
- API key accepted by that server.
- Playwright browsers installed where required (`npx playwright install`).

## Required env vars (real‑server E2E)
These are used by the shared real‑server workflows in both targets.
- `TLDW_E2E_SERVER_URL` (example: `http://127.0.0.1:8000`)
- `TLDW_E2E_API_KEY` (valid API key for that server)

### Optional env vars
- `TLDW_E2E_MEDIA_BASE`: override media API base path if your server is non‑standard.
- `TLDW_E2E_ALLOW_DEV=1`: allow extension tests to use a dev build if no prod build exists.
- `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`: custom Chromium path if needed.
- `TLDW_WEB_URL`: base URL for web tests (default: `http://localhost:3000`).
- `TLDW_WEB_CMD`: command to start the web app for Playwright (default: `bun run dev`).
- `TLDW_WEB_AUTOSTART=false`: do not auto‑start the web app (use your own server).

## Shared real‑server workflows
The shared workflow implementation lives at:
- `test-utils/real-server-workflows.ts`

Two thin wrappers register the same suite:
- Extension wrapper: `extension/tests/e2e/real-server-workflows.spec.ts`
- Web wrapper: `tldw-frontend/e2e/real-server-workflows.spec.ts`

### Run the shared workflows (extension)
```bash
cd extension
npx playwright test tests/e2e/real-server-workflows.spec.ts
```

### Run the shared workflows (web)
```bash
cd tldw-frontend
npx playwright test e2e/real-server-workflows.spec.ts
```

## Extension tests
- Playwright config: `extension/playwright.config.ts`
- Test dir: `extension/tests/e2e`

Run all extension E2E tests:
```bash
cd extension
npx playwright test
```

Notes:
- The extension Playwright config uses a global setup that builds the extension.
- Host permission is automatically handled by the driver, but Chrome may still prompt in some environments.

### Extension page review (full route sweep)
Runs a separate Playwright test per route (options + sidepanel), with offline mode seeded.

```bash
cd extension
bun run test:e2e -- tests/e2e/page-review.spec.ts
```

Optional flags:
- `TLDW_PAGE_REVIEW_CAPTURE=1` to save screenshots to `playwright-mcp-artifacts/extension-page-review`.
- `TLDW_PAGE_REVIEW_STRICT=1` to fail on console errors.

## Webapp tests
- Playwright config: `tldw-frontend/playwright.config.ts`
- Test dir: `tldw-frontend/e2e`

Run all web E2E tests:
```bash
cd tldw-frontend
npx playwright test
```

Run only smoke tests:
```bash
cd tldw-frontend
npx playwright test e2e/smoke
```

### Webapp page review (full route sweep)
Runs a separate Playwright test per Next.js page (from `e2e/smoke/page-inventory.ts`).

```bash
cd tldw-frontend
bun run e2e:smoke -- --workers=1
```

### Workflow E2E Tests

The webapp includes comprehensive workflow tests that verify user journeys from end to end.

**Test files:**
- `e2e/workflows/chat.spec.ts` - Chat workflow (15 tests)
- `e2e/workflows/media-ingest.spec.ts` - Media ingestion workflow
- `e2e/workflows/search.spec.ts` - Search/RAG workflow
- `e2e/workflows/settings.spec.ts` - Settings configuration workflow

**Run workflow tests:**
```bash
cd tldw-frontend

# Run all workflow tests
npx playwright test e2e/workflows/

# Run specific workflow
npx playwright test e2e/workflows/chat.spec.ts
npx playwright test e2e/workflows/media-ingest.spec.ts
npx playwright test e2e/workflows/search.spec.ts
npx playwright test e2e/workflows/settings.spec.ts

# Run with UI for debugging
npx playwright test e2e/workflows/ --ui

# Run with headed browser
npx playwright test e2e/workflows/ --headed
```

**What's tested:**

| Workflow | Coverage |
|----------|----------|
| **Chat** | Basic chat flow, streaming responses, chat history, character selection, error handling, command palette, markdown/code rendering |
| **Media Ingestion** | File upload, URL ingestion, metadata editing, quick ingest, content review flow |
| **Search/RAG** | Basic search, empty results, filters (type/date/tag), result interaction, semantic vs keyword search |
| **Settings** | Server config, persistence, validation, LLM provider config, chat settings, navigation |

### Page Objects & Test Utilities

Reusable test infrastructure is located in `e2e/utils/`:

```
e2e/utils/
├── helpers.ts           # Common test helpers (seedAuth, waitForConnection, etc.)
├── fixtures.ts          # Extended Playwright fixtures with diagnostics
├── index.ts             # Barrel export
└── page-objects/
    ├── ChatPage.ts      # Chat page interactions
    ├── MediaPage.ts     # Media page interactions
    ├── SearchPage.ts    # Search page interactions
    ├── SettingsPage.ts  # Settings page interactions
    └── index.ts         # Barrel export
```

**Usage in tests:**
```typescript
import { test, expect, skipIfServerUnavailable } from "../utils/fixtures"
import { ChatPage } from "../utils/page-objects"
import { seedAuth, TEST_CONFIG } from "../utils/helpers"

test("should send a message", async ({ authedPage, serverInfo }) => {
  skipIfServerUnavailable(serverInfo)

  const chatPage = new ChatPage(authedPage)
  await chatPage.goto()
  await chatPage.sendMessage("Hello!")
  await chatPage.waitForResponse()
})
```

**Key fixtures:**
- `authedPage` - Page pre-seeded with auth config
- `serverInfo` - Server availability and model info
- `diagnostics` - Console/error collection for debugging

**Key helpers:**
- `seedAuth(page)` - Seed localStorage with auth config
- `waitForConnection(page)` - Wait for app connection state
- `skipIfServerUnavailable(serverInfo)` - Skip test if server is down
- `skipIfNoModels(serverInfo)` - Skip test if no LLM models available

## Unit tests (preferred: bun)

### Webapp (Vitest)
- Config: `tldw-frontend/vitest.config.ts`

Run all web unit tests:
```bash
cd tldw-frontend
bun test
```

Run a single test file:
```bash
cd tldw-frontend
bun test path/to/test-file.test.ts
```

### Extension (Vitest)
- Config: `tldw-frontend/vitest.extension.config.ts`

Run all extension unit tests:
```bash
cd tldw-frontend
bun test --config vitest.extension.config.ts
```

## Troubleshooting tips
- **No models**: The workflows call `/api/v1/llm/models/metadata`. Ensure your server is configured with at least one model.
- **Compare mode**: Requires at least 2 models to pass.
- **RAG flows**: Ensure RAG is enabled and healthy (`/api/v1/rag/health`).
- **Feature flags**: Web tests seed flags via localStorage; extension tests use chrome.storage.
- **Chat not connected**: Verify the server URL and API key. Check console output for connection diagnostics.

## Quick checklist before running E2E
- `tldw_server` is running and reachable.
- `TLDW_E2E_SERVER_URL` + `TLDW_E2E_API_KEY` set.
- Playwright browsers installed.
- For web: app running at `TLDW_WEB_URL` (or allow auto‑start).

## Test counts (webapp)

| Category | Tests | Files |
|----------|-------|-------|
| Smoke tests | 70+ | `e2e/smoke/` |
| Workflow tests | 105 | `e2e/workflows/` |
| Real-server workflows | 19 | `e2e/real-server-workflows.spec.ts` |
| Login tests | 2 | `e2e/login.spec.ts` |

Total: **~200 E2E tests** for the webapp.



### Page Review
  Interactive Review:
```md
  cd apps/tldw-frontend
  npm run review:interactive           # Full review
  npm run review:session -- 3          # Start at session 3
  npm run review:resume                # Resume previous session

```

Automated Parallel Testing:
```md
  npm run review:parallel              # All pages
  npm run review:parallel:session      # By session
  npm run e2e:pw -- --grep "Session 1" # Specific session
```
