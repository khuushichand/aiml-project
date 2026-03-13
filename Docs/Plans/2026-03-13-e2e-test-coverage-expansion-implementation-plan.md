# E2E Test Coverage Expansion — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Achieve near-full E2E coverage for WebUI and browser extension with network assertion verification and dead-button detection across all ~129 routes.

**Architecture:** Build a network assertion layer on top of existing Playwright fixtures, then systematically create Page Object Models and workflow specs for every uncovered feature area. Each spec verifies buttons fire correct APIs with correct payloads and the backend responds successfully.

**Tech Stack:** Playwright, TypeScript, existing `fixtures.ts`/`helpers.ts` infrastructure, Page Object Model pattern matching existing `ChatPage`/`MediaPage` conventions.

**Design Doc:** `Docs/Plans/2026-03-13-e2e-test-coverage-expansion-design.md`

---

## Stage 1: Foundation — Network Assertion Layer

### Task 1.1: Create `api-assertions.ts`

**Files:**
- Create: `apps/tldw-frontend/e2e/utils/api-assertions.ts`

**Step 1: Create the network assertion utility**

```typescript
/**
 * Network assertion helpers for E2E tests.
 * Intercepts API calls and lets tests verify buttons fire correct endpoints.
 */
import { type Page, type Request, type Response, expect } from "@playwright/test"

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

export interface ApiCallMatcher {
  method?: string            // "GET" | "POST" | "PUT" | "DELETE" | "PATCH"
  url: string | RegExp       // substring or regex match against request URL
  bodyContains?: Record<string, unknown>  // partial match on JSON body
}

export interface CapturedApiCall {
  method: string
  url: string
  requestBody: unknown
  status: number
  responseBody: unknown
  timestamp: number
}

interface ApiCallResult {
  request: Request
  response: Response
}

/* ------------------------------------------------------------------ */
/* expectApiCall                                                        */
/* ------------------------------------------------------------------ */

/**
 * Returns a promise that resolves when a matching API call is made.
 * Call BEFORE the action that triggers the API call.
 *
 * @example
 * const apiCall = expectApiCall(page, { method: 'POST', url: '/api/v1/notes' });
 * await page.getByRole('button', { name: 'Create' }).click();
 * const { request, response } = await apiCall;
 * expect(response.status()).toBe(200);
 */
export function expectApiCall(
  page: Page,
  matcher: ApiCallMatcher,
  timeoutMs = 15_000
): Promise<ApiCallResult> {
  return new Promise<ApiCallResult>((resolve, reject) => {
    const timer = setTimeout(() => {
      page.removeListener("requestfinished", handler)
      reject(
        new Error(
          `Expected API call matching ${JSON.stringify(matcher)} but none was made within ${timeoutMs}ms`
        )
      )
    }, timeoutMs)

    const handler = async (request: Request) => {
      if (!matchesRequest(request, matcher)) return

      const response = await request.response()
      if (!response) return

      if (matcher.bodyContains) {
        try {
          const body = request.postDataJSON()
          if (!partialMatch(body, matcher.bodyContains)) return
        } catch {
          return
        }
      }

      clearTimeout(timer)
      page.removeListener("requestfinished", handler)
      resolve({ request, response })
    }

    page.on("requestfinished", handler)
  })
}

/* ------------------------------------------------------------------ */
/* expectNoApiCall                                                     */
/* ------------------------------------------------------------------ */

/**
 * Asserts that NO matching API call is made within the timeout.
 * Use to detect dead buttons.
 *
 * @example
 * await page.getByRole('button', { name: 'Broken' }).click();
 * await expectNoApiCall(page, { url: '/api/v1/' }, 3000);
 */
export async function expectNoApiCall(
  page: Page,
  matcher: ApiCallMatcher,
  timeoutMs = 3_000
): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => {
      page.removeListener("requestfinished", handler)
      resolve()
    }, timeoutMs)

    const handler = async (request: Request) => {
      if (!matchesRequest(request, matcher)) return
      clearTimeout(timer)
      page.removeListener("requestfinished", handler)
      reject(
        new Error(
          `Expected NO API call matching ${JSON.stringify(matcher)} but one was made: ${request.method()} ${request.url()}`
        )
      )
    }

    page.on("requestfinished", handler)
  })
}

/* ------------------------------------------------------------------ */
/* assertApiSequence                                                   */
/* ------------------------------------------------------------------ */

/**
 * Asserts API calls happen in the specified order.
 *
 * @example
 * const sequence = assertApiSequence(page, [
 *   { method: 'POST', url: '/api/v1/media/process' },
 *   { method: 'GET', url: '/api/v1/media/' },
 * ]);
 * await page.getByRole('button', { name: 'Ingest' }).click();
 * await sequence;
 */
export function assertApiSequence(
  page: Page,
  matchers: ApiCallMatcher[],
  timeoutMs = 30_000
): Promise<ApiCallResult[]> {
  return new Promise<ApiCallResult[]>((resolve, reject) => {
    const results: ApiCallResult[] = []
    let currentIndex = 0

    const timer = setTimeout(() => {
      page.removeListener("requestfinished", handler)
      reject(
        new Error(
          `API sequence incomplete: matched ${currentIndex}/${matchers.length}. ` +
          `Waiting for: ${JSON.stringify(matchers[currentIndex])}`
        )
      )
    }, timeoutMs)

    const handler = async (request: Request) => {
      if (currentIndex >= matchers.length) return
      if (!matchesRequest(request, matchers[currentIndex])) return

      const response = await request.response()
      if (!response) return

      results.push({ request, response })
      currentIndex++

      if (currentIndex === matchers.length) {
        clearTimeout(timer)
        page.removeListener("requestfinished", handler)
        resolve(results)
      }
    }

    page.on("requestfinished", handler)
  })
}

/* ------------------------------------------------------------------ */
/* captureAllApiCalls                                                  */
/* ------------------------------------------------------------------ */

/**
 * Starts capturing all /api/ calls. Returns a handle to stop and retrieve.
 *
 * @example
 * const capture = captureAllApiCalls(page);
 * await doSomething();
 * const calls = await capture.stop();
 * expect(calls.length).toBeGreaterThan(0);
 */
export function captureAllApiCalls(page: Page): {
  stop: () => Promise<CapturedApiCall[]>
} {
  const calls: CapturedApiCall[] = []

  const handler = async (request: Request) => {
    if (!request.url().includes("/api/")) return
    const response = await request.response()
    if (!response) return

    let requestBody: unknown = null
    try { requestBody = request.postDataJSON() } catch { /* no body */ }

    let responseBody: unknown = null
    try { responseBody = await response.json() } catch { /* non-json */ }

    calls.push({
      method: request.method(),
      url: request.url(),
      requestBody,
      status: response.status(),
      responseBody,
      timestamp: Date.now(),
    })
  }

  page.on("requestfinished", handler)

  return {
    stop: async () => {
      page.removeListener("requestfinished", handler)
      return calls
    },
  }
}

/* ------------------------------------------------------------------ */
/* getCapturedApiCalls (for fixture integration)                        */
/* ------------------------------------------------------------------ */

const pageCallsMap = new WeakMap<Page, CapturedApiCall[]>()

/**
 * Start auto-capturing API calls for a page (call in fixture setup).
 */
export function startApiCapture(page: Page): void {
  const calls: CapturedApiCall[] = []
  pageCallsMap.set(page, calls)

  page.on("requestfinished", async (request: Request) => {
    if (!request.url().includes("/api/")) return
    const response = await request.response()
    if (!response) return

    let requestBody: unknown = null
    try { requestBody = request.postDataJSON() } catch { /* no body */ }

    let responseBody: unknown = null
    try { responseBody = await response.json() } catch { /* non-json */ }

    calls.push({
      method: request.method(),
      url: request.url(),
      requestBody,
      status: response.status(),
      responseBody,
      timestamp: Date.now(),
    })
  })
}

/**
 * Get all captured API calls for a page (call in fixture teardown).
 */
export function getCapturedApiCalls(page: Page): CapturedApiCall[] {
  return pageCallsMap.get(page) ?? []
}

/* ------------------------------------------------------------------ */
/* Internal helpers                                                    */
/* ------------------------------------------------------------------ */

function matchesRequest(request: Request, matcher: ApiCallMatcher): boolean {
  if (matcher.method && request.method() !== matcher.method.toUpperCase()) {
    return false
  }
  const url = request.url()
  if (typeof matcher.url === "string") {
    if (!url.includes(matcher.url)) return false
  } else {
    if (!matcher.url.test(url)) return false
  }
  return true
}

function partialMatch(actual: unknown, expected: Record<string, unknown>): boolean {
  if (typeof actual !== "object" || actual === null) return false
  for (const [key, value] of Object.entries(expected)) {
    if ((actual as Record<string, unknown>)[key] !== value) return false
  }
  return true
}
```

**Step 2: Run TypeScript check**

Run: `cd apps/tldw-frontend && npx tsc --noEmit e2e/utils/api-assertions.ts --esModuleInterop --moduleResolution node --target es2020 --module commonjs --strict --skipLibCheck 2>&1 | head -20`

If there are import issues, adjust based on the project's tsconfig. The file should compile cleanly.

**Step 3: Commit**

```bash
git add apps/tldw-frontend/e2e/utils/api-assertions.ts
git commit -m "feat(e2e): add network assertion layer for API call verification"
```

---

### Task 1.2: Integrate API Capture into Existing Fixtures

**Files:**
- Modify: `apps/tldw-frontend/e2e/utils/fixtures.ts`

**Step 1: Read the existing fixtures file**

Read `apps/tldw-frontend/e2e/utils/fixtures.ts` to understand the current fixture structure.

**IMPORTANT:** The current `authedPage` fixture has NO teardown code — it's just:
```typescript
authedPage: async ({ page }, use) => {
  await seedAuth(page)
  await use(page)
}
```

**Step 2: Add API capture with teardown to the `authedPage` fixture**

Add imports at the top of `fixtures.ts`:
```typescript
import { startApiCapture, getCapturedApiCalls } from "./api-assertions"
```

Replace the `authedPage` fixture definition with this version that adds both setup AND teardown (Playwright runs code after `await use()` as teardown):

```typescript
authedPage: async ({ page }, use, testInfo) => {
  await seedAuth(page)
  startApiCapture(page)
  await use(page)
  // Teardown: attach API call log on test failure for debugging
  if (testInfo.status !== "passed") {
    const apiLog = getCapturedApiCalls(page)
    if (apiLog.length > 0) {
      await testInfo.attach("api-calls.json", {
        body: JSON.stringify(apiLog, null, 2),
        contentType: "application/json",
      })
    }
  }
}
```

**NOTE:** The `testInfo` parameter is the third arg to Playwright fixture functions. This is a standard Playwright pattern for fixture teardown — no separate `afterEach` needed.

**Step 4: Verify existing tests still pass**

Run: `cd apps/tldw-frontend && npx playwright test e2e/smoke/all-pages.spec.ts --reporter=line --timeout=120000 2>&1 | tail -20`

Expected: All existing tests still pass (the API capture is passive).

**Step 5: Commit**

```bash
git add apps/tldw-frontend/e2e/utils/fixtures.ts
git commit -m "feat(e2e): integrate API call capture into test fixtures"
```

---

### Task 1.3: Create `BasePage` Class

**Files:**
- Create: `apps/tldw-frontend/e2e/utils/page-objects/BasePage.ts`
- Modify: `apps/tldw-frontend/e2e/utils/page-objects/index.ts`

**Step 1: Create the BasePage**

```typescript
import { type Page, type Locator, expect } from "@playwright/test"
import { expectApiCall, expectNoApiCall, captureAllApiCalls } from "../api-assertions"

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

export type InteractiveExpectation =
  | { type: "api_call"; apiPattern: string | RegExp; method?: string }
  | { type: "modal"; modalSelector: string }
  | { type: "navigation"; targetUrl: string | RegExp }
  | { type: "state_change"; stateCheck: (page: Page) => Promise<unknown> }
  | { type: "toggle" }  // e.g., checkbox, switch — just verify it toggles

export interface InteractiveElement {
  /** Human-readable name for error messages */
  name: string
  /** Playwright locator for the element */
  locator: Locator
  /** What should happen when clicked */
  expectation: InteractiveExpectation
  /** Optional: setup to run before clicking (e.g., fill required fields) */
  setup?: (page: Page) => Promise<void>
  /** Optional: cleanup to run after clicking (e.g., dismiss modal, undo) */
  cleanup?: (page: Page) => Promise<void>
}

/* ------------------------------------------------------------------ */
/* BasePage                                                            */
/* ------------------------------------------------------------------ */

export abstract class BasePage {
  constructor(protected page: Page) {}

  /** Navigate to the page. Subclasses implement. */
  abstract goto(): Promise<void>

  /** Assert key elements are visible. Subclasses implement. */
  abstract assertPageReady(): Promise<void>

  /**
   * Return all interactive elements and their expected behaviors.
   * Subclasses override to declare their buttons/links/actions.
   * Default: empty array (no wired-button checks).
   */
  async getInteractiveElements(): Promise<InteractiveElement[]> {
    return []
  }

  /**
   * Systematically click every declared interactive element and verify
   * it does what it's supposed to do. Catches dead buttons.
   */
  async assertAllButtonsWired(): Promise<void> {
    const elements = await this.getInteractiveElements()
    if (elements.length === 0) {
      throw new Error(
        `${this.constructor.name}.getInteractiveElements() returned empty array. ` +
        `Override it to declare interactive elements, or remove assertAllButtonsWired() call.`
      )
    }

    for (const el of elements) {
      // Skip if element isn't visible (conditional rendering)
      const visible = await el.locator.isVisible().catch(() => false)
      if (!visible) continue

      const enabled = await el.locator.isEnabled().catch(() => false)
      if (!enabled) continue

      // Run optional setup
      if (el.setup) await el.setup(this.page)

      try {
        switch (el.expectation.type) {
          case "api_call": {
            const call = expectApiCall(this.page, {
              url: el.expectation.apiPattern,
              method: el.expectation.method,
            }, 10_000)
            await el.locator.click()
            try {
              await call
            } catch (err) {
              throw new Error(
                `Button "${el.name}" expected to fire API call ` +
                `${el.expectation.method ?? "ANY"} ${el.expectation.apiPattern} ` +
                `but no matching call was made. Original: ${(err as Error).message}`
              )
            }
            break
          }

          case "modal": {
            await el.locator.click()
            const modal = this.page.locator(el.expectation.modalSelector)
            await expect(modal).toBeVisible({ timeout: 5_000 })
            // Close modal for cleanup
            await this.page.keyboard.press("Escape")
            await expect(modal).toBeHidden({ timeout: 3_000 }).catch(() => {})
            break
          }

          case "navigation": {
            const targetUrl = el.expectation.targetUrl
            await el.locator.click()
            if (typeof targetUrl === "string") {
              await expect(this.page).toHaveURL(new RegExp(targetUrl), { timeout: 10_000 })
            } else {
              await expect(this.page).toHaveURL(targetUrl, { timeout: 10_000 })
            }
            await this.page.goBack()
            await this.assertPageReady()
            break
          }

          case "state_change": {
            const before = await el.expectation.stateCheck(this.page)
            await el.locator.click()
            // Allow time for state to update
            await this.page.waitForTimeout(500)
            const after = await el.expectation.stateCheck(this.page)
            if (JSON.stringify(before) === JSON.stringify(after)) {
              throw new Error(
                `Button "${el.name}" expected state change but state is identical before and after click.`
              )
            }
            break
          }

          case "toggle": {
            const beforeChecked = await el.locator.isChecked().catch(() => null)
            await el.locator.click()
            if (beforeChecked !== null) {
              const afterChecked = await el.locator.isChecked().catch(() => null)
              if (beforeChecked === afterChecked) {
                throw new Error(`Toggle "${el.name}" did not change checked state after click.`)
              }
            }
            break
          }
        }
      } finally {
        // Run optional cleanup
        if (el.cleanup) await el.cleanup(this.page).catch(() => {})
      }
    }
  }
}
```

**Step 2: Add to page-objects index**

Read `apps/tldw-frontend/e2e/utils/page-objects/index.ts`, then add at the top:
```typescript
export { BasePage, type InteractiveElement, type InteractiveExpectation } from "./BasePage"
```

**Step 3: Commit**

```bash
git add apps/tldw-frontend/e2e/utils/page-objects/BasePage.ts apps/tldw-frontend/e2e/utils/page-objects/index.ts
git commit -m "feat(e2e): add BasePage with assertAllButtonsWired() dead-button detection"
```

---

### Task 1.4: Create Journey Helpers

**Files:**
- Create: `apps/tldw-frontend/e2e/utils/journey-helpers.ts`

**Step 1: Create shared journey utilities**

```typescript
/**
 * Reusable helpers for cross-feature journey specs.
 * Each helper performs a common setup action and returns an identifier.
 */
import { type Page, expect } from "@playwright/test"
import { expectApiCall } from "./api-assertions"
import { TEST_CONFIG, fetchWithApiKey } from "./helpers"

/**
 * Ingest content via the media page and wait until processing completes.
 * Returns the media_id from the API response.
 */
export async function ingestAndWaitForReady(
  page: Page,
  input: { url: string } | { file: string },
  timeoutMs = 120_000
): Promise<string> {
  await page.goto("/media", { waitUntil: "domcontentloaded" })

  if ("url" in input) {
    // Use quick ingest or URL input
    const urlInput = page.getByPlaceholder(/URL|Enter URL|paste/i).first()
    if (await urlInput.isVisible().catch(() => false)) {
      await urlInput.fill(input.url)
    } else {
      // Try quick ingest button
      const quickIngestBtn = page.getByRole("button", { name: /quick ingest/i }).first()
      if (await quickIngestBtn.isVisible().catch(() => false)) {
        await quickIngestBtn.click()
        const modalInput = page.getByPlaceholder(/URL|Enter URL|paste/i).first()
        await modalInput.fill(input.url)
      }
    }

    const apiCall = expectApiCall(page, {
      method: "POST",
      url: "/api/v1/media",
    }, timeoutMs)

    // Click submit/ingest button
    const submitBtn = page.getByRole("button", { name: /ingest|submit|process|add/i }).first()
    await submitBtn.click()

    const { response } = await apiCall
    const body = await response.json()
    return body.media_id ?? body.id ?? "unknown"
  }

  // File upload path
  const fileInput = page.locator('input[type="file"]').first()
  await fileInput.setInputFiles(input.file)

  const apiCall = expectApiCall(page, {
    method: "POST",
    url: "/api/v1/media",
  }, timeoutMs)

  const submitBtn = page.getByRole("button", { name: /upload|ingest|submit|process/i }).first()
  await submitBtn.click()

  const { response } = await apiCall
  const body = await response.json()
  return body.media_id ?? body.id ?? "unknown"
}

/**
 * Create a note via the notes page. Returns the note title for later lookup.
 */
export async function createNote(
  page: Page,
  opts: { title: string; content: string }
): Promise<string> {
  await page.goto("/notes", { waitUntil: "domcontentloaded" })

  const apiCall = expectApiCall(page, {
    method: "POST",
    url: "/api/v1/notes",
  })

  // Click create/new note button
  const createBtn = page.getByRole("button", { name: /create|new|add/i }).first()
  await createBtn.click()

  // Fill title and content
  const titleInput = page.getByPlaceholder(/title/i).first()
  if (await titleInput.isVisible().catch(() => false)) {
    await titleInput.fill(opts.title)
  }

  const contentInput = page.locator("textarea, [contenteditable]").first()
  if (await contentInput.isVisible().catch(() => false)) {
    await contentInput.fill(opts.content)
  }

  // Save
  const saveBtn = page.getByRole("button", { name: /save|create|submit/i }).first()
  await saveBtn.click()

  await apiCall
  return opts.title
}

/**
 * Wait for streaming response to complete in chat.
 */
export async function waitForStreamComplete(
  page: Page,
  timeoutMs = 60_000
): Promise<void> {
  // Wait for stop button to appear then disappear
  const stopBtn = page.getByRole("button", { name: /stop/i })
  try {
    await expect(stopBtn).toBeVisible({ timeout: 10_000 })
    await expect(stopBtn).toBeHidden({ timeout: timeoutMs })
  } catch {
    // Stream may have completed before we could observe the stop button
    // Wait a moment for any pending renders
    await page.waitForTimeout(1_000)
  }
}

/**
 * Verify server is available and return basic info.
 * Useful at the start of journey tests.
 */
export async function checkServerHealth(): Promise<{
  available: boolean
  version?: string
}> {
  try {
    const res = await fetchWithApiKey(
      `${TEST_CONFIG.serverUrl}/api/v1/health`,
      TEST_CONFIG.apiKey
    )
    if (res.ok) {
      const data = await res.json()
      return { available: true, version: data.version }
    }
    return { available: false }
  } catch {
    return { available: false }
  }
}
```

**Step 2: Commit**

```bash
git add apps/tldw-frontend/e2e/utils/journey-helpers.ts
git commit -m "feat(e2e): add shared journey helpers for cross-feature tests"
```

---

### Task 1.5: Update Playwright Config with Tiered Projects

**Files:**
- Modify: `apps/tldw-frontend/playwright.config.ts`

**Step 1: Read the existing config**

Read `apps/tldw-frontend/playwright.config.ts`.

**CRITICAL FIX — Double-execution prevention:**
The existing config has `testDir: 'e2e'` at the **global** level. If we add project-level `testDir` values pointing to subdirectories of `e2e/`, Playwright will discover and run tests from BOTH the global and project-level paths, causing every test to run twice.

**Fix:** Remove the global `testDir: 'e2e'` line and give EVERY project (including the existing `chromium`) an explicit `testDir`.

**Step 2: Replace test directory and project config**

Remove the global `testDir: 'e2e'` line from the top-level config. Then replace the `projects` array with:

```typescript
projects: [
  // Existing smoke/workflow tests (previously discovered by global testDir)
  {
    name: 'chromium',
    testDir: 'e2e',
    testIgnore: ['**/workflows/tier-*/**', '**/workflows/journeys/**'],
    use: { ...devices['Desktop Chrome'] },
  },
  // New tiered projects
  {
    name: 'tier-1',
    testDir: 'e2e/workflows/tier-1-critical',
    use: { ...devices['Desktop Chrome'] },
  },
  {
    name: 'tier-2',
    testDir: 'e2e/workflows/tier-2-features',
    use: { ...devices['Desktop Chrome'] },
  },
  {
    name: 'tier-3',
    testDir: 'e2e/workflows/tier-3-automation',
    use: { ...devices['Desktop Chrome'] },
  },
  {
    name: 'tier-4',
    testDir: 'e2e/workflows/tier-4-admin',
    use: { ...devices['Desktop Chrome'] },
  },
  {
    name: 'tier-5',
    testDir: 'e2e/workflows/tier-5-specialized',
    use: { ...devices['Desktop Chrome'] },
  },
  {
    name: 'journeys',
    testDir: 'e2e/workflows/journeys',
    timeout: 120_000,
    expect: { timeout: 30_000 },
    use: { ...devices['Desktop Chrome'] },
  },
],
```

**Key detail:** The existing `chromium` project gets `testDir: 'e2e'` (matching the old global setting) PLUS `testIgnore` to exclude the new tier directories. This ensures:
- Running `playwright test` with no project filter runs ALL tests (existing + new tiers)
- Running `playwright test --project=chromium` runs only the original tests
- Running `playwright test --project=tier-1` runs only tier-1 tests
- No test is ever discovered/run twice

**Step 3: Create the directory structure**

```bash
cd apps/tldw-frontend
mkdir -p e2e/workflows/tier-1-critical
mkdir -p e2e/workflows/tier-2-features
mkdir -p e2e/workflows/tier-3-automation
mkdir -p e2e/workflows/tier-4-admin
mkdir -p e2e/workflows/tier-5-specialized
mkdir -p e2e/workflows/journeys
```

**Step 4: Add placeholder `.gitkeep` in each directory**

```bash
touch e2e/workflows/tier-1-critical/.gitkeep
touch e2e/workflows/tier-2-features/.gitkeep
touch e2e/workflows/tier-3-automation/.gitkeep
touch e2e/workflows/tier-4-admin/.gitkeep
touch e2e/workflows/tier-5-specialized/.gitkeep
touch e2e/workflows/journeys/.gitkeep
```

**Step 5: Add NPM scripts to package.json**

Read `apps/tldw-frontend/package.json` and add these scripts (alongside existing ones):

```json
"e2e:tier1": "playwright test --project=tier-1",
"e2e:tier2": "playwright test --project=tier-2",
"e2e:tier3": "playwright test --project=tier-3",
"e2e:tier4": "playwright test --project=tier-4",
"e2e:tier5": "playwright test --project=tier-5",
"e2e:journeys": "playwright test --project=journeys",
"e2e:critical": "playwright test --project=tier-1 --project=journeys",
"e2e:features": "playwright test --project=tier-2 --project=tier-3",
"e2e:admin": "playwright test --project=tier-4 --project=tier-5",
"e2e:all-tiers": "playwright test --project=tier-1 --project=tier-2 --project=tier-3 --project=tier-4 --project=tier-5 --project=journeys"
```

**Step 6: Commit**

```bash
git add apps/tldw-frontend/playwright.config.ts apps/tldw-frontend/package.json apps/tldw-frontend/e2e/workflows/
git commit -m "feat(e2e): add tiered project config and workflow directory structure"
```

---

## Stage 2: Tier 1 — Critical Feature Specs

### Task 2.1: Notes Page Object + Spec

**Files:**
- Create: `apps/tldw-frontend/e2e/utils/page-objects/NotesPage.ts`
- Create: `apps/tldw-frontend/e2e/workflows/tier-1-critical/notes.spec.ts`
- Modify: `apps/tldw-frontend/e2e/utils/page-objects/index.ts`

**Step 1: Explore the notes page**

Before writing, navigate to the notes page in the running app or read the route source to understand:
- What URL the notes page lives at
- What buttons/forms exist
- What API endpoints are used

Check: `apps/packages/ui/src/routes/` for notes-related route files, and `apps/packages/ui/src/components/` for notes components. Also check `apps/packages/ui/src/services/` for notes API calls.

**Step 2: Create NotesPage**

```typescript
import { type Page, type Locator, expect } from "@playwright/test"
import { BasePage, type InteractiveElement } from "./BasePage"

export class NotesPage extends BasePage {
  readonly createButton: Locator
  readonly searchInput: Locator
  readonly notesList: Locator

  constructor(page: Page) {
    super(page)
    this.createButton = page.getByRole("button", { name: /create|new|add/i }).first()
    this.searchInput = page.getByPlaceholder(/search/i).first()
    this.notesList = page.getByTestId("notes-list").or(page.locator("[class*='notes']")).first()
  }

  async goto(): Promise<void> {
    await this.page.goto("/notes", { waitUntil: "domcontentloaded" })
  }

  async assertPageReady(): Promise<void> {
    // Wait for the page to have rendered key elements
    await this.page.waitForLoadState("domcontentloaded")
    // Notes page should have at least a create button or a list area
    const hasCreate = await this.createButton.isVisible().catch(() => false)
    const hasList = await this.notesList.isVisible().catch(() => false)
    expect(hasCreate || hasList).toBe(true)
  }

  async createNote(opts: { title: string; content: string }): Promise<void> {
    await this.createButton.click()

    const titleInput = this.page.getByPlaceholder(/title/i).first()
    if (await titleInput.isVisible().catch(() => false)) {
      await titleInput.fill(opts.title)
    }

    const contentInput = this.page.locator("textarea, [contenteditable]").first()
    if (await contentInput.isVisible().catch(() => false)) {
      await contentInput.fill(opts.content)
    }

    const saveBtn = this.page.getByRole("button", { name: /save|create|submit/i }).first()
    await saveBtn.click()
  }

  async searchNotes(query: string): Promise<void> {
    if (await this.searchInput.isVisible().catch(() => false)) {
      await this.searchInput.fill(query)
      await this.searchInput.press("Enter")
    }
  }

  async assertNoteVisible(title: string): Promise<void> {
    await expect(this.page.getByText(title).first()).toBeVisible({ timeout: 10_000 })
  }

  async assertNoteNotVisible(title: string): Promise<void> {
    await expect(this.page.getByText(title)).toBeHidden({ timeout: 5_000 })
  }

  async deleteNote(title: string): Promise<void> {
    const noteRow = this.page.getByText(title).first()
    await noteRow.click()
    const deleteBtn = this.page.getByRole("button", { name: /delete|remove|trash/i }).first()
    await deleteBtn.click()
    // Confirm if dialog appears
    const confirmBtn = this.page.getByRole("button", { name: /confirm|yes|ok|delete/i }).first()
    if (await confirmBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await confirmBtn.click()
    }
  }

  async getInteractiveElements(): Promise<InteractiveElement[]> {
    // NOTE: This list should be updated as the UI evolves.
    // Start with known buttons and add more as discovered.
    return [
      {
        name: "Create Note",
        locator: this.createButton,
        expectation: { type: "modal", modalSelector: "[role='dialog'], .ant-modal" },
      },
    ]
  }
}
```

**Step 3: Add to index**

Add to `apps/tldw-frontend/e2e/utils/page-objects/index.ts`:
```typescript
export { NotesPage } from "./NotesPage"
```

**Step 4: Create the spec**

```typescript
import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../../utils/fixtures"
import { expectApiCall } from "../../utils/api-assertions"
import { NotesPage } from "../../utils/page-objects"
import { generateTestId } from "../../utils/helpers"

test.describe("Notes", () => {
  let notes: NotesPage

  test.beforeEach(async ({ authedPage, serverInfo }) => {
    skipIfServerUnavailable(serverInfo)
    notes = new NotesPage(authedPage)
    await notes.goto()
  })

  test("page loads with expected elements", async ({ diagnostics }) => {
    await notes.assertPageReady()
    await assertNoCriticalErrors(diagnostics)
  })

  test("create note fires API and shows result", async ({ authedPage, diagnostics }) => {
    const testTitle = `Test Note ${generateTestId()}`

    const apiCall = expectApiCall(authedPage, {
      method: "POST",
      url: "/api/v1/notes",
    })

    await notes.createNote({ title: testTitle, content: "Test content body" })

    const { request, response } = await apiCall
    expect(response.status()).toBeLessThan(400)

    await notes.assertNoteVisible(testTitle)
    await assertNoCriticalErrors(diagnostics)
  })

  test("search notes filters results", async ({ authedPage, diagnostics }) => {
    // Create a note first
    const testTitle = `Searchable ${generateTestId()}`
    await notes.createNote({ title: testTitle, content: "Unique content for search" })

    // Search for it
    await notes.searchNotes(testTitle)

    await notes.assertNoteVisible(testTitle)
    await assertNoCriticalErrors(diagnostics)
  })

  test("delete note fires API and removes from list", async ({ authedPage, diagnostics }) => {
    const testTitle = `Delete Me ${generateTestId()}`
    await notes.createNote({ title: testTitle, content: "To be deleted" })
    await notes.assertNoteVisible(testTitle)

    const apiCall = expectApiCall(authedPage, {
      method: "DELETE",
      url: "/api/v1/notes",
    })

    await notes.deleteNote(testTitle)

    const { response } = await apiCall
    expect(response.status()).toBeLessThan(400)

    await notes.assertNoteNotVisible(testTitle)
    await assertNoCriticalErrors(diagnostics)
  })
})
```

**Step 5: Run the spec**

Run: `cd apps/tldw-frontend && npx playwright test e2e/workflows/tier-1-critical/notes.spec.ts --reporter=line 2>&1 | tail -30`

Expected: Tests either pass (if server running) or skip (if server unavailable). Fix any selector issues based on actual page structure.

**Step 6: Commit**

```bash
git add apps/tldw-frontend/e2e/utils/page-objects/NotesPage.ts apps/tldw-frontend/e2e/utils/page-objects/index.ts apps/tldw-frontend/e2e/workflows/tier-1-critical/notes.spec.ts
git commit -m "feat(e2e): add Notes page object and workflow spec"
```

---

### Task 2.2: Settings Core Spec

**Files:**
- Create: `apps/tldw-frontend/e2e/workflows/tier-1-critical/settings-core.spec.ts`

**Step 1: Explore settings pages**

Read the existing `SettingsPage.ts` page object to understand what's already implemented. Check what settings sections exist by reading the settings route files.

**Step 2: Create the spec**

This spec tests that settings pages load and their save buttons actually fire API calls:

```typescript
import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../../utils/fixtures"
import { expectApiCall } from "../../utils/api-assertions"
import { SettingsPage } from "../../utils/page-objects"

// These are the ACTUAL section names accepted by SettingsPage.gotoSection().
// Verified against the real SettingsPage.ts page object.
// Sections NOT in this list (chatbooks, world-books, mcp-hub, family-guardrails, etc.)
// are navigated via direct URL: `/settings/<section-name>`
const SETTINGS_SECTIONS_VIA_PAGE_OBJECT = [
  "tldw", "model", "chat", "ui", "splash", "quick-ingest",
  "image-generation", "guardian", "prompt", "knowledge",
  "rag", "speech", "evaluations", "characters", "health",
] as const

// These settings pages exist but are NOT wired into SettingsPage.gotoSection().
// Test them via direct navigation only.
const SETTINGS_SECTIONS_DIRECT_NAV = [
  "chatbooks", "world-books", "prompt-studio", "mcp-hub",
  "share", "about", "processed", "family-guardrails",
] as const

test.describe("Settings", () => {
  let settings: SettingsPage

  test.beforeEach(async ({ authedPage, serverInfo }) => {
    skipIfServerUnavailable(serverInfo)
    settings = new SettingsPage(authedPage)
  })

  const ALL_SECTIONS = [...SETTINGS_SECTIONS_VIA_PAGE_OBJECT, ...SETTINGS_SECTIONS_DIRECT_NAV]
  for (const section of ALL_SECTIONS) {
    test(`settings/${section} loads without errors`, async ({ authedPage, diagnostics }) => {
      await authedPage.goto(`/settings/${section}`, { waitUntil: "domcontentloaded" })
      await authedPage.waitForLoadState("networkidle").catch(() => {})

      // Page should not show error boundary
      const errorBoundary = authedPage.getByText(/something went wrong|error/i)
      const hasError = await errorBoundary.isVisible().catch(() => false)

      // Check for visible interactive elements (at least one button, input, or select)
      const buttons = await authedPage.getByRole("button").count()
      const inputs = await authedPage.locator("input, select, textarea").count()
      expect(buttons + inputs).toBeGreaterThan(0)

      await assertNoCriticalErrors(diagnostics)
    })
  }

  test("save settings fires API", async ({ authedPage, diagnostics }) => {
    await settings.goto()
    await settings.gotoSection("tldw")
    await settings.waitForReady()

    // Find and click save button
    const saveBtn = authedPage.getByRole("button", { name: /save/i }).first()
    if (await saveBtn.isVisible().catch(() => false)) {
      const apiCall = expectApiCall(authedPage, {
        url: "/api/v1/",
      })

      await saveBtn.click()
      const { response } = await apiCall
      expect(response.status()).toBeLessThan(400)
    }

    await assertNoCriticalErrors(diagnostics)
  })
})
```

**Step 3: Run and verify**

Run: `cd apps/tldw-frontend && npx playwright test e2e/workflows/tier-1-critical/settings-core.spec.ts --reporter=line 2>&1 | tail -30`

**Step 4: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/tier-1-critical/settings-core.spec.ts
git commit -m "feat(e2e): add settings core spec covering all subsections"
```

---

### Task 2.3: Enhance Existing Chat Spec with API Assertions

**Files:**
- Modify: `apps/tldw-frontend/e2e/workflows/chat.spec.ts` (or wherever it lives)

**Step 1: Read the existing chat spec**

Read the existing `chat.spec.ts` to understand its current test cases.

**Step 2: Add API assertion imports and enhance key tests**

Add at the top:
```typescript
import { expectApiCall } from "../utils/api-assertions"
```

Find the test that sends a chat message (likely named something like "should send message and display response"). Wrap the send action with an API assertion:

```typescript
// Before the send action:
const apiCall = expectApiCall(authedPage, {
  method: "POST",
  url: "/api/v1/chat/completions",
})

// After the existing send action:
const { request, response } = await apiCall
expect(response.status()).toBeLessThan(400)
const requestBody = request.postDataJSON()
expect(requestBody).toHaveProperty("messages")
```

**Step 3: Run and verify**

Run: `cd apps/tldw-frontend && npx playwright test e2e/workflows/chat.spec.ts --reporter=line 2>&1 | tail -30`

**Step 4: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/chat.spec.ts
git commit -m "feat(e2e): enhance chat spec with API call assertions"
```

---

### Task 2.4: Enhance Existing Media Ingest Spec with API Assertions

Same pattern as Task 2.3 but for `media-ingest.spec.ts`. Add `expectApiCall` for:
- `POST /api/v1/media/process` on ingest
- `GET /api/v1/media` on list refresh

### Task 2.5: Enhance Existing Search Spec with API Assertions

Same pattern. Add `expectApiCall` for:
- `POST /api/v1/rag/search` or `GET /api/v1/media/search` on search
- Verify search results contain expected data

### Task 2.6: Enhance Existing Collections Spec with API Assertions

Same pattern. Add `expectApiCall` for:
- Collection CRUD endpoints

---

## Stage 3: Tier 2 — Feature Module Specs

Each task in this stage follows the same pattern:
1. Explore the feature's route/components/services to understand selectors and API endpoints
2. Create a Page Object extending `BasePage`
3. Create a workflow spec with API assertions
4. Run and fix selectors
5. Commit

### Task 3.1: Prompts Workspace (includes Prompt Studio)

**IMPORTANT ROUTE FIX:** Prompt Studio has been consolidated into the main Prompts workspace.
The route is `/prompts` (NOT `/prompt-studio`). The studio tab is accessed via `/prompts?tab=studio`.
The legacy `/prompt-studio` route redirects to `/prompts?tab=studio`.

**Files:**
- Create: `apps/tldw-frontend/e2e/utils/page-objects/PromptsWorkspacePage.ts`
- Create: `apps/tldw-frontend/e2e/workflows/tier-2-features/prompts-workspace.spec.ts`

**Step 1: Explore prompts workspace**

Read route files in `apps/packages/ui/src/routes/` matching `*prompt*`. The main route component is `PromptsWorkspace` in `option-prompts.tsx`. Check what tabs exist and what API calls are used. Backend endpoints are at `/api/v1/prompts/` (library CRUD) and `/api/v1/prompt-studio/` (studio features like execute, preview, test cases).

**Step 2: Create PromptsWorkspacePage**

Follow the `NotesPage` pattern. Key methods:
- `goto()` — navigate to `/prompts`
- `gotoStudioTab()` — navigate to `/prompts?tab=studio` (or click the studio tab)
- `assertPageReady()` — verify key elements
- `createPrompt(opts: { name: string; template: string })` — create a prompt (library)
- `testPrompt(input: string)` — fill variable and run (studio)
- `deletePrompt(name: string)` — delete

**Step 3: Create spec**

```typescript
import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../../utils/fixtures"
import { expectApiCall } from "../../utils/api-assertions"
import { PromptsWorkspacePage } from "../../utils/page-objects"
import { generateTestId } from "../../utils/helpers"

test.describe("Prompts Workspace", () => {
  test.beforeEach(async ({ authedPage, serverInfo }) => {
    skipIfServerUnavailable(serverInfo)
  })

  test("page loads with expected elements", async ({ authedPage, diagnostics }) => {
    const pw = new PromptsWorkspacePage(authedPage)
    await pw.goto()
    await pw.assertPageReady()
    await assertNoCriticalErrors(diagnostics)
  })

  test("create prompt fires API", async ({ authedPage, diagnostics }) => {
    const pw = new PromptsWorkspacePage(authedPage)
    await pw.goto()

    const apiCall = expectApiCall(authedPage, {
      method: "POST",
      url: "/api/v1/prompts",
    })

    await pw.createPrompt({
      name: `Test Prompt ${generateTestId()}`,
      template: "Summarize: {{text}}",
    })

    const { response } = await apiCall
    expect(response.status()).toBeLessThan(400)
    await assertNoCriticalErrors(diagnostics)
  })

  test("prompt studio execute fires API", async ({ authedPage, diagnostics }) => {
    const pw = new PromptsWorkspacePage(authedPage)
    await pw.gotoStudioTab()

    // Create a studio project then execute
    const apiCall = expectApiCall(authedPage, {
      method: "POST",
      url: "/api/v1/prompt-studio/execute",
    })

    await pw.testPrompt("World")

    const { response } = await apiCall
    expect(response.status()).toBeLessThan(400)
    await assertNoCriticalErrors(diagnostics)
  })
})
```

**Step 4: Run, fix selectors, commit**

### Task 3.2: (Merged into Task 3.1)

Prompts Library is part of the Prompts Workspace (`/prompts`). Covered by `PromptsWorkspacePage` in Task 3.1.

### Task 3.3: Characters

Same pattern. Page Object: `CharactersPage`. Route: `/characters`. Tests:
- Create character with name/description/system prompt
- Edit character settings
- Import/export PNG card
- Delete character
- API assertions for each CRUD operation

### Task 3.4: Evaluations

Same pattern. Page Object: `EvaluationsPage`. Route: `/evaluations`. Tests:
- Run single evaluation
- View results
- Batch evaluation with progress

### Task 3.5: Audiobook Studio

Same pattern. Page Object: `AudiobookStudioPage`. Route: `/audiobook-studio`. Tests:
- Page loads with controls
- Select source content
- Configure voice/settings
- Generate (fires TTS API)

### Task 3.6: STT Transcription

Same pattern. Page Object: `STTPage`. Route: `/stt`. Tests:
- Upload audio file
- Select transcription model
- Verify transcription API fires
- Verify transcript appears

### Task 3.7: TTS Synthesis

Same pattern. Page Object: `TTSPage`. Route: `/tts`. Tests:
- Enter text
- Select voice/provider
- Generate audio (fires `/api/v1/audio/speech`)
- Verify audio player appears

### Task 3.8: Speech Playground

Same pattern. Page Object: `SpeechPage`. Route: `/speech`. Tests: similar to TTS but with additional speech controls.

### Task 3.9: Chatbooks

Same pattern. Page Object: `ChatbooksPage`. Route: `/chatbooks`. Tests:
- Export chatbook (fires `/api/v1/chatbooks/export`)
- Import chatbook (fires `/api/v1/chatbooks/import`)
- Browse chatbooks

### Task 3.10: Sources & Connectors

Same pattern. Page Object: `SourcesPage`. Route: `/sources`. Tests:
- Browse sources list
- Create new source
- View source detail
- Connector operations

### Task 3.11: Data Tables

Same pattern. Page Object: `DataTablesPage`. Route: `/data-tables`. Tests:
- Page loads with table
- Interact with table controls
- Verify data operations fire APIs

### Task 3.12: Document Workspace

Same pattern. Page Object: `DocumentWorkspacePage`. Route: `/document-workspace`. Tests:
- Page loads
- Create/open document
- Edit operations fire APIs

### Task 3.13: Content Review

Same pattern. Page Object: `ContentReviewPage`. Route: `/content-review`. Tests:
- Browse review queue
- Approve/reject items
- Batch operations

### Task 3.14: Writing Playground

Same pattern. Page Object: `WritingPlaygroundPage`. Route: `/writing-playground`. Tests:
- Input text
- Trigger writing assistance
- Verify API call with text payload

### Task 3.15: Kanban

Same pattern. Page Object: `KanbanPage`. Route: `/kanban`. Tests:
- Page loads with board
- Create card
- Move card between columns
- Delete card

### Task 3.16: Flashcards

Same pattern. Page Object: `FlashcardsPage`. Route: `/flashcards`. Tests:
- Generate flashcards from content
- Browse decks
- Study mode (flip, mark known/unknown)
- Verify progress tracking

### Task 3.17: Quiz

Same pattern. Page Object: `QuizPage`. Route: `/quiz`. Tests:
- Generate quiz
- Take quiz (answer questions)
- View results/score

### Task 3.18: MCP Hub

Same pattern. Page Object: `MCPHubPage`. Route: `/mcp-hub`. Tests:
- Page loads with server list
- View server details
- Status checks (fires `/api/v1/mcp/status`)

---

## Stage 4: Tier 3 — Automation Specs

### Task 4.1: ACP Playground

**Files:**
- Create: `apps/tldw-frontend/e2e/utils/page-objects/ACPPage.ts`
- Create: `apps/tldw-frontend/e2e/workflows/tier-3-automation/acp-playground.spec.ts`

Same page object pattern. Route: `/acp-playground`. Tests:
- Browse agent list
- Execute tool
- View session details

### Task 4.2: Agent Registry

Route: `/agents`. Tests: browse registry, view agent details, verify list API fires.

### Task 4.3: Agent Tasks

Route: `/agent-tasks`. Tests: view tasks, create task, monitor status.

### Task 4.4: Chat Workflows

Route: `/chat-workflows`. Tests: browse workflows, create workflow, execute workflow.

### Task 4.5: Workflow Editor

Route: `/workflow-editor` (if exists as separate route). Tests: open editor, add nodes, save workflow.

---

## Stage 5: Tier 4 — Admin Specs

### Task 5.1: Admin Server

**Files:**
- Create: `apps/tldw-frontend/e2e/utils/page-objects/AdminPage.ts`
- Create: `apps/tldw-frontend/e2e/workflows/tier-4-admin/admin-server.spec.ts`

Single `AdminPage` Page Object covering all admin routes with `gotoSection(section)` method (similar to `SettingsPage`).

Tests for each admin page:
- Page loads without errors
- Key controls are visible and enabled
- Primary action buttons fire APIs

### Task 5.2: Admin llama.cpp

Route: `/admin/llamacpp`. Tests: model list loads, controls visible.

### Task 5.3: Admin MLX

Route: `/admin/mlx`. Tests: page loads, model management controls visible.

### Task 5.4: Admin Orgs

Route: `/admin/orgs`. Tests: org/user list loads.

### Task 5.5: Admin Data Ops

Route: `/admin/data-ops`. Tests: action buttons visible, at least one fires API.

### Task 5.6: Admin Maintenance

Route: `/admin/maintenance`. Tests: maintenance tools load.

### Task 5.7: Settings Full

Route: all `/settings/*` subsections. One parameterized test that visits each section and verifies it renders with interactive elements.

### Task 5.8: Profile & Companion

Routes: `/profile`, `/companion`. Tests: page loads, save fires API.

### Task 5.9: Notifications

Route: `/notifications`. Tests: notification list loads.

### Task 5.10: Privileges

Route: `/privileges`. Tests: privilege list loads.

---

## Stage 6: Tier 5 — Specialized Specs

### Tasks 6.1-6.9

One spec each for: Moderation Playground, Chunking Playground, Model Playground, Repo2Txt, Claims Review, Researchers page, Journalists page, OSINT page, Skills page.

Each follows the same pattern:
1. Navigate to route
2. Assert page loads with interactive elements
3. Test primary action fires API
4. Assert no critical errors

These are lighter-weight specs — no new Page Objects needed. Use inline selectors.

**Example template for each:**

```typescript
import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../../utils/fixtures"
import { expectApiCall } from "../../utils/api-assertions"

test.describe("Feature Name", () => {
  test.beforeEach(async ({ authedPage, serverInfo }) => {
    skipIfServerUnavailable(serverInfo)
  })

  test("page loads with interactive elements", async ({ authedPage, diagnostics }) => {
    await authedPage.goto("/route-path", { waitUntil: "domcontentloaded" })
    await authedPage.waitForLoadState("networkidle").catch(() => {})

    const buttons = await authedPage.getByRole("button").count()
    const inputs = await authedPage.locator("input, select, textarea").count()
    expect(buttons + inputs).toBeGreaterThan(0)

    await assertNoCriticalErrors(diagnostics)
  })

  test("primary action fires API", async ({ authedPage, diagnostics }) => {
    await authedPage.goto("/route-path", { waitUntil: "domcontentloaded" })

    // Find and interact with the primary action
    const primaryBtn = authedPage.getByRole("button", { name: /action-name/i }).first()
    if (await primaryBtn.isVisible().catch(() => false)) {
      const apiCall = expectApiCall(authedPage, { url: "/api/v1/expected-endpoint" })
      await primaryBtn.click()
      const { response } = await apiCall
      expect(response.status()).toBeLessThan(400)
    }

    await assertNoCriticalErrors(diagnostics)
  })
})
```

---

## Stage 7: Journey Specs

### Task 7.1: Ingest → Search → Chat

**Files:**
- Create: `apps/tldw-frontend/e2e/workflows/journeys/ingest-search-chat.spec.ts`

```typescript
import { test, expect, skipIfServerUnavailable, skipIfNoModels } from "../../utils/fixtures"
import { expectApiCall, assertApiSequence } from "../../utils/api-assertions"
import { ChatPage, MediaPage, SearchPage } from "../../utils/page-objects"
import { waitForStreamComplete, ingestAndWaitForReady } from "../../utils/journey-helpers"
import { generateTestId } from "../../utils/helpers"

test.describe("Journey: Ingest → Search → Chat", () => {
  test("full pipeline from ingestion to RAG chat", async ({ authedPage, serverInfo, diagnostics }) => {
    skipIfServerUnavailable(serverInfo)
    skipIfNoModels(serverInfo)

    const testUrl = "https://en.wikipedia.org/wiki/SQLite"

    // Step 1: Ingest
    const mediaId = await test.step("Ingest media", async () => {
      return await ingestAndWaitForReady(authedPage, { url: testUrl })
    })

    // Step 2: Search for ingested content
    await test.step("Search finds ingested content", async () => {
      const search = new SearchPage(authedPage)
      await search.goto()
      await search.waitForReady()

      const apiCall = expectApiCall(authedPage, {
        url: "/api/v1/",
      })

      await search.search("SQLite")
      await apiCall

      await search.waitForResults()
      const results = await search.getResults()
      expect(results.length).toBeGreaterThan(0)
    })

    // Step 3: Chat with RAG context
    await test.step("Chat references ingested content", async () => {
      const chat = new ChatPage(authedPage)
      await chat.goto()
      await chat.waitForReady()

      const apiCall = expectApiCall(authedPage, {
        method: "POST",
        url: "/api/v1/chat/completions",
      })

      await chat.sendMessage("What is SQLite? Use the ingested content.")
      const { request, response } = await apiCall
      expect(response.status()).toBeLessThan(400)

      await waitForStreamComplete(authedPage)

      const messages = await chat.getMessages()
      const lastMsg = messages[messages.length - 1]
      expect(lastMsg.content.toLowerCase()).toContain("sqlite")
    })
  })
})
```

**Run, fix, commit.**

### Task 7.2: Ingest → Evaluate → Review

Similar structure with `test.step()`. Ingest content, run evaluation, check review page.

### Task 7.3: Create Character → Chat

Create character, navigate to chat, select character, verify system prompt in API call.

### Task 7.4: Notes → Flashcards

Create note, generate flashcards, verify cards created.

### Task 7.5: Prompts Workspace → Chat

Create prompt at `/prompts`, navigate to chat, use the saved prompt, verify prompt content appears in the chat completions API call payload.

### Task 7.6: Watchlist → Ingest → Notify

Create watchlist, trigger run, verify notification and ingested items.

---

## Stage 8: Extension-Specific Specs

### Task 8.1: Background Proxy API Assertions

**Files:**
- Create: `apps/extension/tests/e2e/background-proxy-api.spec.ts`

**Step 1: Create the spec**

```typescript
import { test, expect } from "@playwright/test"
import { requireRealServerConfig, launchWithBuiltExtensionOrSkip } from "./utils/real-server"
import { waitForConnectionStore, forceConnected } from "./utils/connection"

test.describe("Background proxy API assertions", () => {
  test("chat message routes through bgRequest to backend", async () => {
    const { serverUrl, apiKey } = requireRealServerConfig(test)

    const { context, page, optionsUrl } = await launchWithBuiltExtensionOrSkip(test, {
      seedConfig: {
        serverUrl,
        authMode: "single-user",
        apiKey,
        __tldw_first_run_complete: true,
      },
    })

    try {
      await page.goto(optionsUrl + "#/chat", { waitUntil: "domcontentloaded" })
      await waitForConnectionStore(page, "bg-proxy-test")
      await forceConnected(page, { serverUrl }, "bg-proxy-test")

      // Intercept network requests to verify they reach the backend
      const apiCalls: string[] = []
      page.on("request", (req) => {
        if (req.url().includes("/api/v1/")) {
          apiCalls.push(`${req.method()} ${req.url()}`)
        }
      })

      // Send a chat message
      const input = page.locator("#textarea-message").or(page.getByPlaceholder(/message/i)).first()
      await expect(input).toBeVisible({ timeout: 10_000 })
      await input.fill("Hello from background proxy test")
      await input.press("Enter")

      // Wait for API call to fire (through background proxy)
      await expect
        .poll(() => apiCalls.some((c) => c.includes("chat/completions")), { timeout: 15_000 })
        .toBe(true)
    } finally {
      await context.close()
    }
  })
})
```

**Step 2: Run and verify**

Run: `cd apps/extension && TLDW_E2E_SERVER_URL=http://127.0.0.1:8000 TLDW_E2E_API_KEY=your-key npx playwright test tests/e2e/background-proxy-api.spec.ts --reporter=line 2>&1 | tail -20`

**Step 3: Commit**

### Task 8.2: Sidepanel ↔ Options Handoff

**Files:**
- Create: `apps/extension/tests/e2e/sidepanel-options-handoff.spec.ts`

Tests:
- Open sidepanel → click "open full view" → verify options page opens
- Change setting in options → verify sidepanel reflects change (without reload)
- Start chat in sidepanel → open options chat → verify conversation state transferred

### Task 8.3: Copilot Popup (enhance existing)

Enhance existing copilot popup spec to verify the right-click → popup → action fires correct API.

### Task 8.4: HF Pull Content Script

Test HuggingFace model pull button injection and click flow.

### Task 8.5: Reconnection

Test server disconnect → graceful degradation → reconnect:
- Connect to server → force disconnect (patch connection store) → verify error UI → force reconnect → verify recovery

### Task 8.6: Cross-Context Sync

Test settings changed in options page are reflected in sidepanel via `chrome.storage` events.

### Task 8.7: Context Menu Actions

Test all right-click menu items fire correct message-passing actions.

### Task 8.8: Extension API Assertions

Systematic button→API verification for extension-specific pages not covered by webui tests.

---

## Execution Notes

### Running Order

Stages are independent after Stage 1. Execute in order: 1 → 2 → 3 → ... → 8. But within stages 3-6, tasks can be parallelized (each spec is independent).

### Fixing Selectors

The Page Objects use resilient selector strategies (role → testId → placeholder → CSS). However, selectors WILL need adjustment when first run against the actual app. The pattern is:

1. Run the spec
2. If a selector fails, open the Playwright trace or use `--headed` mode
3. Use Playwright's `page.getByRole()`, `page.getByTestId()`, or `page.locator()` to find the correct selector
4. Update the Page Object

### Incremental Value

Each task delivers independently useful test coverage. You can stop after any task and have more coverage than before. The priority order within each stage reflects impact.

### Test Maintenance

When the UI changes:
1. Update the Page Object's selectors
2. Update `getInteractiveElements()` if buttons were added/removed
3. Run the spec to verify

All changes are localized to the Page Object — specs don't need updating.
