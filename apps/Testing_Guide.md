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
