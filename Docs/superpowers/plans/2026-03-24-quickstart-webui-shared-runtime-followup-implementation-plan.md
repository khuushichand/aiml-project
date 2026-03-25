# Quickstart WebUI Shared Runtime Follow-Up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the quickstart same-origin rollout by moving the shared browser runtime and transport layers onto the WebUI origin, failing fast for incomplete advanced mode, and fixing the Docker single-user docs so they launch the real WebUI path.

**Architecture:** Keep the existing WebUI env validator in `apps/tldw-frontend` authoritative, but extract a shared browser transport helper in `apps/packages/ui` so both shared HTTP and shared WebSocket callers can follow the same quickstart-versus-advanced contract. Make the WebUI quickstart canonical `serverUrl` resolve to the WebUI origin, preserve explicit-host behavior for extension surfaces, and prove one WS-backed quickstart flow end-to-end through the WebUI origin before declaring the transport migration complete.

**Tech Stack:** Next.js standalone WebUI, shared React/TypeScript UI package, Vitest, Playwright, Docker Compose, pytest docs/contract tests, Bandit

---

## File Structure

- `apps/packages/ui/src/services/tldw/browser-networking.ts`
  Purpose: shared browser transport contract for quickstart vs advanced HTTP/WS base resolution, loopback detection, and surface-aware validation.
- `apps/packages/ui/src/services/tldw/__tests__/browser-networking.test.ts`
  Purpose: unit coverage for quickstart/advanced transport resolution, `[::1]`, and WebUI-only fail-fast rules.
- `apps/tldw-frontend/lib/api-base.ts`
  Purpose: thin WebUI wrapper over the shared transport helper; remains the authoritative WebUI env contract surface.
- `apps/tldw-frontend/scripts/validate-networking-config.mjs`
  Purpose: fail build/startup on invalid quickstart or advanced env combinations without guessing from runtime connectivity.
- `apps/tldw-frontend/__tests__/app/app-networking-guard.test.tsx`
  Purpose: WebUI guard coverage for missing advanced API URL, loopback mismatch, and preserved quickstart invariants.
- `apps/tldw-frontend/__tests__/frontend-quickstart-networking.test.ts`
  Purpose: quick regression checks for WebUI quickstart env/edge wiring.
- `apps/packages/ui/src/hooks/useCanonicalConnectionConfig.ts`
  Purpose: canonical config hydration for WebUI quickstart and explicit-host extension/browser-app surfaces.
- `apps/packages/ui/src/hooks/__tests__/useCanonicalConnectionConfig.test.tsx`
  Purpose: quickstart storage precedence and extension-host preservation tests.
- `apps/tldw-frontend/extension/shims/runtime-bootstrap.ts`
  Purpose: stop seeding `127.0.0.1:8000` into browser runtime config during WebUI quickstart while preserving explicit extension defaults.
- `apps/tldw-frontend/__tests__/extension/runtime-bootstrap.test.ts`
  Purpose: runtime bootstrap coverage for same-origin quickstart hydration and extension explicit-host behavior.
- `apps/packages/ui/src/services/tldw-server.ts`
  Purpose: remove unconditional loopback fallback from shared browser surfaces.
- `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
  Purpose: keep canonical config and auth header setup aligned with quickstart same-origin semantics.
- `apps/packages/ui/src/store/connection.tsx`
  Purpose: connection liveness and recovery logic for canonical WebUI-origin quickstart config.
- `apps/packages/ui/src/store/__tests__/connection.test.ts`
  Purpose: quickstart liveness and fallback behavior tests.
- `apps/packages/ui/src/services/tldw/request-core.ts`
  Purpose: central shared HTTP request transport with a quickstart mode distinct from hosted mode.
- `apps/packages/ui/src/services/tldw/__tests__/request-core.quickstart.test.ts`
  Purpose: quickstart request-core coverage for relative/same-origin requests with self-host auth headers intact.
- `apps/packages/ui/src/services/tldw/__tests__/request-core.hosted.test.ts`
  Purpose: hosted-mode regression coverage so quickstart transport changes do not bleed into hosted behavior.
- `apps/packages/ui/src/services/acp/client.ts`
  Purpose: ACP REST and WS clients must use shared HTTP/WS builders instead of direct `serverUrl` concatenation.
- `apps/packages/ui/src/services/acp/__tests__/client.test.ts`
  Purpose: ACP REST/WS same-origin quickstart coverage and advanced explicit-host regressions.
- `apps/packages/ui/src/services/persona-stream.ts`
  Purpose: persona WS URL builder must use the shared WS base helper.
- `apps/packages/ui/src/services/prompt-studio-stream.ts`
  Purpose: prompt-studio WS URL builder must use the shared WS base helper.
- `apps/packages/ui/src/services/watchlists-stream.ts`
  Purpose: watchlists WS URL builder must use the shared WS base helper.
- `apps/packages/ui/src/services/__tests__/persona-stream.test.ts`
  Purpose: quickstart and advanced persona WS URL coverage.
- `apps/packages/ui/src/services/__tests__/prompt-studio-stream.test.ts`
  Purpose: quickstart and advanced prompt-studio WS URL coverage.
- `apps/packages/ui/src/services/__tests__/watchlists-stream.test.ts`
  Purpose: quickstart and advanced watchlists WS URL coverage.
- `apps/packages/ui/src/hooks/useVoiceChatStream.tsx`
  Purpose: live voice chat WS bootstrap must use the shared WS base helper.
- `apps/packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx`
  Purpose: live voice chat regression coverage after the WS builder migration.
- `apps/packages/ui/src/hooks/document-workspace/useReadingProgress.ts`
  Purpose: reading-progress beacon/keepalive writes must stay on the WebUI origin in quickstart.
- `apps/packages/ui/src/hooks/document-workspace/useAnnotationSync.ts`
  Purpose: annotation-sync beacon/keepalive writes must stay on the WebUI origin in quickstart.
- `apps/packages/ui/src/hooks/document-workspace/__tests__/useReadingProgress.test.tsx`
  Purpose: same-origin quickstart coverage for reading progress sync.
- `apps/packages/ui/src/hooks/document-workspace/__tests__/useAnnotationSync.test.tsx`
  Purpose: same-origin quickstart coverage for annotation sync beacon/keepalive behavior.
- `apps/packages/ui/src/components/Option/AgentRegistry/index.tsx`
  Purpose: ACP health fetch must use the shared HTTP builder instead of direct `serverUrl` concatenation.
- `apps/tldw-frontend/next.config.mjs`
  Purpose: quickstart HTTP rewrite remains aligned with the transport contract; if WS requires a proxy layer, this file must stay coherent with it.
- `Dockerfiles/Dockerfile.webui`
  Purpose: build-time env validation and any quickstart WS edge runtime requirements.
- `Dockerfiles/docker-compose.webui.yml`
  Purpose: WebUI quickstart stack wiring for the same-origin HTTP/WS edge.
- `apps/tldw-frontend/e2e/utils/helpers.ts`
  Purpose: Playwright auth/bootstrap helpers must seed quickstart WebUI config coherently instead of hardcoding backend origins into browser storage.
- `apps/tldw-frontend/e2e/workflows/persona-live.spec.ts`
  Purpose: representative WS-backed quickstart proof that traffic stays on the WebUI origin.
- `README.md`
  Purpose: top-level quickstart and advanced override guidance.
- `Docs/Getting_Started/Profile_Docker_Single_User.md`
  Purpose: fix the command mismatch so the guide launches the actual WebUI quickstart path and verifies `http://127.0.0.1:8080`.
- `Docs/Website/index.html`
  Purpose: keep public quickstart copy aligned with the real WebUI path.
- `tldw_Server_API/tests/Docs/test_quickstart_same_origin_docs.py`
  Purpose: docs contract coverage for the quickstart/WebUI story.
- `tldw_Server_API/tests/Utils/test_makefile_quickstart_same_origin.py`
  Purpose: keep the Makefile quickstart/default WebUI networking contract locked.
- `tldw_Server_API/tests/Utils/test_docker_quickstart_hardening.py`
  Purpose: keep Docker quickstart hardening checks aligned with the new transport contract.

## Task 0: Prove The Quickstart WebSocket Edge Before Migrating Callers

**Files:**
- Modify: `apps/tldw-frontend/e2e/utils/helpers.ts`
- Modify: `apps/tldw-frontend/e2e/workflows/persona-live.spec.ts`
- Modify: `apps/tldw-frontend/next.config.mjs`
- Modify: `Dockerfiles/Dockerfile.webui`
- Modify: `Dockerfiles/docker-compose.webui.yml`
- Test: `apps/tldw-frontend/e2e/workflows/persona-live.spec.ts`
- Test: `apps/tldw-frontend/__tests__/frontend-quickstart-networking.test.ts`

- [ ] **Step 1: Write the failing WS-origin proof first**

Add a quickstart-only capture in `persona-live.spec.ts` that records `new WebSocket(...)` URLs from the page and asserts at least one live persona connection uses the WebUI host/port, not the backend host/port.

```ts
await authedPage.addInitScript(() => {
  const OriginalWebSocket = window.WebSocket
  const seen: string[] = []
  ;(window as any).__tldwSeenWsUrls = seen
  window.WebSocket = class extends OriginalWebSocket {
    constructor(url: string | URL, protocols?: string | string[]) {
      seen.push(String(url))
      super(url, protocols)
    }
  } as typeof WebSocket
})

const seenWsUrls = await authedPage.evaluate(() => (window as any).__tldwSeenWsUrls || [])
expect(
  seenWsUrls.some((raw: string) => new URL(raw).host === new URL(TEST_CONFIG.webUrl).host)
).toBe(true)
```

Also update `e2e/utils/helpers.ts` so quickstart tests can seed `tldwConfig.serverUrl` from the WebUI origin instead of always forcing the backend origin into storage.

- [ ] **Step 2: Run the failing WS proof**

Run:

```bash
docker compose --env-file tldw_Server_API/Config_Files/.env \
  -f Dockerfiles/docker-compose.yml \
  -f Dockerfiles/docker-compose.webui.yml up -d --build

cd apps/tldw-frontend && \
TLDW_WEB_URL=http://127.0.0.1:8080 \
TLDW_SERVER_URL=http://127.0.0.1:8000 \
TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY \
bunx playwright test e2e/workflows/persona-live.spec.ts --reporter=line
```

Expected: FAIL because the captured persona WS URL still targets the backend origin directly (`:8000`) or the page bootstrap still seeds a direct backend `serverUrl`.

- [ ] **Step 3: Add a minimal quickstart edge regression test**

Add or extend `apps/tldw-frontend/__tests__/frontend-quickstart-networking.test.ts` so quickstart still requires `TLDW_INTERNAL_API_ORIGIN` and still wires the WebUI stack for same-origin `/api/:path*` forwarding.

```ts
expect(rewrites).toContainEqual({
  source: "/api/:path*",
  destination: "http://app:8000/api/:path*"
})
```

- [ ] **Step 4: Implement the quickstart WS edge**

Land the smallest implementation that makes the proof pass:

- First try to keep the current WebUI edge as the public origin and forward WS upgrades there.
- If the current Next.js standalone edge cannot pass the Playwright proof after three focused attempts, add a dedicated quickstart reverse-proxy layer in the Docker WebUI stack, reusing the patterns already present in `Dockerfiles/docker-compose.proxy.yml` or `Dockerfiles/docker-compose.proxy-nginx.yml`.
- Do not change the quickstart env contract: `TLDW_INTERNAL_API_ORIGIN` must remain required in quickstart and absolute `NEXT_PUBLIC_API_URL` must remain forbidden there.

- [ ] **Step 5: Re-run the edge proof**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run __tests__/frontend-quickstart-networking.test.ts --reporter=verbose

cd apps/tldw-frontend && \
TLDW_WEB_URL=http://127.0.0.1:8080 \
TLDW_SERVER_URL=http://127.0.0.1:8000 \
TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY \
bunx playwright test e2e/workflows/persona-live.spec.ts --reporter=line
```

Expected: PASS, with the captured WS URL host matching `127.0.0.1:8080`.

- [ ] **Step 6: Commit**

```bash
git add apps/tldw-frontend/e2e/utils/helpers.ts \
  apps/tldw-frontend/e2e/workflows/persona-live.spec.ts \
  apps/tldw-frontend/__tests__/frontend-quickstart-networking.test.ts \
  apps/tldw-frontend/next.config.mjs \
  Dockerfiles/Dockerfile.webui \
  Dockerfiles/docker-compose.webui.yml
git commit -m "test: prove quickstart websocket edge"
```

## Task 1: Extract A Shared Browser Transport Contract Without Creating A Second Env Truth Table

**Files:**
- Create: `apps/packages/ui/src/services/tldw/browser-networking.ts`
- Create: `apps/packages/ui/src/services/tldw/__tests__/browser-networking.test.ts`
- Modify: `apps/tldw-frontend/lib/api-base.ts`
- Modify: `apps/tldw-frontend/scripts/validate-networking-config.mjs`
- Modify: `apps/tldw-frontend/__tests__/app/app-networking-guard.test.tsx`
- Modify: `apps/tldw-frontend/__tests__/frontend-quickstart-networking.test.ts`

- [ ] **Step 1: Write the failing unit tests**

Cover:

- quickstart WebUI pages resolve same-origin HTTP and WS bases
- advanced mode requires `NEXT_PUBLIC_API_URL`
- `[::1]` is treated as loopback
- WebUI `http`/`https` pages fail on advanced loopback mismatch
- extension/browser-app contexts are not blocked by the WebUI-only loopback rule

```ts
it("treats [::1] as loopback", () => {
  expect(isLoopbackHost("[::1]")).toBe(true)
})

it("rejects advanced mode without NEXT_PUBLIC_API_URL", () => {
  expect(() =>
    resolveBrowserTransport({
      surface: "webui-page",
      deploymentMode: "advanced",
      pageOrigin: "http://192.168.5.184:8080",
      apiOrigin: ""
    })
  ).toThrow(/NEXT_PUBLIC_API_URL/i)
})

it("does not block extension loopback usage", () => {
  expect(
    detectBrowserNetworkingIssue({
      surface: "extension",
      pageOrigin: "chrome-extension://abcd",
      apiOrigin: "http://127.0.0.1:8000"
    })
  ).toBeUndefined()
})

it("does not block browser-app loopback usage", () => {
  expect(
    detectBrowserNetworkingIssue({
      surface: "browser-app",
      pageOrigin: "app://tldw",
      apiOrigin: "http://127.0.0.1:8000"
    })
  ).toBeUndefined()
})
```

- [ ] **Step 2: Run the failing transport tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  ../packages/ui/src/services/tldw/__tests__/browser-networking.test.ts \
  __tests__/app/app-networking-guard.test.tsx \
  __tests__/frontend-quickstart-networking.test.ts \
  --reporter=verbose
```

Expected: FAIL because the shared helper does not exist yet, advanced mode still falls back, and `[::1]` is not consistently handled.

- [ ] **Step 3: Implement the shared browser transport helper and thin WebUI wrapper**

`apps/packages/ui/src/services/tldw/browser-networking.ts` should own the pure transport logic; `apps/tldw-frontend/lib/api-base.ts` should stay a thin WebUI wrapper around it.

```ts
export type BrowserSurface = "webui-page" | "extension" | "browser-app"
export type BrowserTransportMode = "quickstart" | "advanced"

export function resolveBrowserTransport(input: {
  surface: BrowserSurface
  deploymentMode: string | null | undefined
  pageOrigin?: string | null
  apiOrigin?: string | null
}) {
  // quickstart => same-origin page base
  // advanced => explicit apiOrigin required
}

export function buildBrowserHttpBase(resolved: BrowserTransport): string {
  return resolved.mode === "quickstart" ? "" : resolved.apiOrigin
}

export function buildBrowserWebSocketBase(resolved: BrowserTransport): string {
  const origin = resolved.mode === "quickstart" ? resolved.pageOrigin : resolved.apiOrigin
  return origin.replace(/^http/i, "ws")
}
```

Keep `validate-networking-config.mjs` authoritative for WebUI env invariants:

- quickstart requires `TLDW_INTERNAL_API_ORIGIN`
- quickstart rejects absolute `NEXT_PUBLIC_API_URL`
- advanced requires a valid absolute `NEXT_PUBLIC_API_URL`
- no advanced fallback to `pageOrigin`

- [ ] **Step 4: Re-run the transport tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  ../packages/ui/src/services/tldw/__tests__/browser-networking.test.ts \
  __tests__/app/app-networking-guard.test.tsx \
  __tests__/frontend-quickstart-networking.test.ts \
  --reporter=verbose
```

Expected: PASS, including the WebUI-only advanced fail-fast cases and the `[::1]` loopback case.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/browser-networking.ts \
  apps/packages/ui/src/services/tldw/__tests__/browser-networking.test.ts \
  apps/tldw-frontend/lib/api-base.ts \
  apps/tldw-frontend/scripts/validate-networking-config.mjs \
  apps/tldw-frontend/__tests__/app/app-networking-guard.test.tsx \
  apps/tldw-frontend/__tests__/frontend-quickstart-networking.test.ts
git commit -m "refactor: add shared browser transport contract"
```

## Task 2: Make Canonical Browser Config Hydration Same-Origin-Aware

**Files:**
- Modify: `apps/tldw-frontend/extension/shims/runtime-bootstrap.ts`
- Modify: `apps/tldw-frontend/__tests__/extension/runtime-bootstrap.test.ts`
- Modify: `apps/packages/ui/src/hooks/useCanonicalConnectionConfig.ts`
- Create: `apps/packages/ui/src/hooks/__tests__/useCanonicalConnectionConfig.test.tsx`
- Modify: `apps/packages/ui/src/services/tldw-server.ts`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Modify: `apps/packages/ui/src/store/connection.tsx`
- Modify: `apps/packages/ui/src/store/__tests__/connection.test.ts`

- [ ] **Step 1: Write the failing hydration tests**

Cover:

- WebUI quickstart ignores stale loopback/backend storage and canonicalizes to the WebUI origin
- extension contexts keep explicit hosts
- canonical config hydration does not silently reintroduce `http://127.0.0.1:8000`
- connection liveness still works when the quickstart canonical `serverUrl` is the WebUI origin

```ts
it("prefers the current page origin in web quickstart mode", async () => {
  localStorage.setItem("tldw-api-host", "http://127.0.0.1:8000")
  window.history.replaceState({}, "", "http://127.0.0.1:8080/settings")
  await import("@web/extension/shims/runtime-bootstrap")
  expect(readStoredValue("tldwConfig")).toMatchObject({
    serverUrl: "http://127.0.0.1:8080"
  })
})

it("keeps extension explicit hosts intact", async () => {
  // simulate chrome-extension protocol and ensure 127.0.0.1 survives
})
```

- [ ] **Step 2: Run the failing hydration tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  __tests__/extension/runtime-bootstrap.test.ts \
  ../packages/ui/src/hooks/__tests__/useCanonicalConnectionConfig.test.tsx \
  ../packages/ui/src/store/__tests__/connection.test.ts \
  --reporter=verbose
```

Expected: FAIL because WebUI quickstart still seeds loopback/backend URLs into storage and shared config still falls back to `127.0.0.1:8000`.

- [ ] **Step 3: Implement storage precedence and canonical quickstart hydration**

Apply the spec’s precedence exactly:

1. explicit advanced/custom host chosen by the user
2. WebUI quickstart same-origin contract
3. coherent canonical stored config
4. legacy explicit-host fallbacks only for extension/browser-app surfaces

Use the shared helper instead of duplicating rules:

```ts
const resolved = resolveBrowserTransport({
  surface: isWebRuntime() ? "webui-page" : "extension",
  deploymentMode: process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE,
  pageOrigin: typeof window !== "undefined" ? window.location.origin : null,
  apiOrigin: process.env.NEXT_PUBLIC_API_URL
})

const canonicalServerUrl =
  resolved.mode === "quickstart" && resolved.surface === "webui-page"
    ? resolved.pageOrigin
    : explicitOrStoredServerUrl
```

Specific rules:

- `runtime-bootstrap.ts` must stop writing `tldw-api-host=http://127.0.0.1:8000` for WebUI quickstart
- `useCanonicalConnectionConfig.ts` must not default WebUI pages to loopback
- `tldw-server.ts` and `TldwApiClient.ts` must stop silently reintroducing loopback into configured WebUI quickstart state
- `connection.tsx` must keep recovery logic working for private LAN mismatches without overriding the WebUI quickstart contract

- [ ] **Step 4: Re-run the hydration tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  __tests__/extension/runtime-bootstrap.test.ts \
  ../packages/ui/src/hooks/__tests__/useCanonicalConnectionConfig.test.tsx \
  ../packages/ui/src/store/__tests__/connection.test.ts \
  --reporter=verbose
```

Expected: PASS, with WebUI quickstart canonicalizing to the WebUI origin and extension explicit-host flows still intact.

- [ ] **Step 5: Commit**

```bash
git add apps/tldw-frontend/extension/shims/runtime-bootstrap.ts \
  apps/tldw-frontend/__tests__/extension/runtime-bootstrap.test.ts \
  apps/packages/ui/src/hooks/useCanonicalConnectionConfig.ts \
  apps/packages/ui/src/hooks/__tests__/useCanonicalConnectionConfig.test.tsx \
  apps/packages/ui/src/services/tldw-server.ts \
  apps/packages/ui/src/services/tldw/TldwApiClient.ts \
  apps/packages/ui/src/store/connection.tsx \
  apps/packages/ui/src/store/__tests__/connection.test.ts
git commit -m "fix: canonicalize quickstart browser config"
```

## Task 3: Centralize Shared HTTP Transport And Migrate Direct HTTP Bypasses

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/request-core.ts`
- Create: `apps/packages/ui/src/services/tldw/__tests__/request-core.quickstart.test.ts`
- Modify: `apps/packages/ui/src/services/tldw/__tests__/request-core.hosted.test.ts`
- Modify: `apps/packages/ui/src/services/acp/client.ts`
- Modify: `apps/packages/ui/src/services/acp/__tests__/client.test.ts`
- Modify: `apps/packages/ui/src/hooks/document-workspace/useReadingProgress.ts`
- Modify: `apps/packages/ui/src/hooks/document-workspace/__tests__/useReadingProgress.test.tsx`
- Modify: `apps/packages/ui/src/hooks/document-workspace/useAnnotationSync.ts`
- Create: `apps/packages/ui/src/hooks/document-workspace/__tests__/useAnnotationSync.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/AgentRegistry/index.tsx`
- Modify: `apps/packages/ui/src/store/connection.tsx`
- Modify: `apps/packages/ui/src/store/__tests__/connection.test.ts`

- [ ] **Step 1: Write the failing HTTP transport tests**

Cover:

- request-core quickstart uses same-origin relative paths and still sends self-host auth headers
- hosted mode remains on `/api/proxy/...` and still omits browser auth headers
- ACP REST uses the shared HTTP base builder
- reading progress and annotation beacon/keepalive helpers use the WebUI origin in quickstart
- Agent Registry ACP health fetch stops concatenating a direct backend `serverUrl`

```ts
it("uses same-origin quickstart requests with self-host auth headers", async () => {
  const result = await tldwRequest(
    { path: "/api/v1/notifications?limit=50", method: "GET" },
    {
      getConfig: async () => ({
        serverUrl: "http://127.0.0.1:8080",
        authMode: "single-user",
        apiKey: "test-key"
      }),
      fetchFn: fetchMock
    }
  )

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/v1/notifications?limit=50",
    expect.objectContaining({
      headers: expect.objectContaining({ "X-API-KEY": "test-key" })
    })
  )
})
```

- [ ] **Step 2: Run the failing HTTP transport tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  ../packages/ui/src/services/tldw/__tests__/request-core.quickstart.test.ts \
  ../packages/ui/src/services/tldw/__tests__/request-core.hosted.test.ts \
  ../packages/ui/src/services/acp/__tests__/client.test.ts \
  ../packages/ui/src/hooks/document-workspace/__tests__/useReadingProgress.test.tsx \
  ../packages/ui/src/hooks/document-workspace/__tests__/useAnnotationSync.test.tsx \
  ../packages/ui/src/store/__tests__/connection.test.ts \
  --reporter=verbose
```

Expected: FAIL because quickstart still piggybacks on direct `serverUrl` behavior or hosted-mode branching, and the beacon/fetch callers still concatenate backend origins directly.

- [ ] **Step 3: Implement quickstart HTTP transport as a first-class shared mode**

Do not overload hosted mode. `request-core.ts` should distinguish:

- `hosted`: `/api/proxy/...`, no browser auth headers
- `quickstart`: same-origin `/api/v1/...`, self-host auth headers intact
- `advanced`: absolute explicit API origin, self-host auth headers intact

```ts
const transport = resolveBrowserRequestTransport({
  config: cfg,
  path: normalizedPath,
  pageOrigin: typeof window !== "undefined" ? window.location.origin : null
})

const requestUrl = transport.kind === "same-origin"
  ? transport.path
  : `${transport.origin}${transport.path}`
```

Then update the direct HTTP bypass callers:

- `ACPRestClient`
- `useReadingProgress` keepalive/beacon URL builder
- `useAnnotationSync` keepalive/beacon URL builder
- `AgentRegistry` ACP health fetch
- connection liveness where it still constructs `${serverUrl}/api/v1/health/live`

- [ ] **Step 4: Re-run the HTTP transport tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  ../packages/ui/src/services/tldw/__tests__/request-core.quickstart.test.ts \
  ../packages/ui/src/services/tldw/__tests__/request-core.hosted.test.ts \
  ../packages/ui/src/services/acp/__tests__/client.test.ts \
  ../packages/ui/src/hooks/document-workspace/__tests__/useReadingProgress.test.tsx \
  ../packages/ui/src/hooks/document-workspace/__tests__/useAnnotationSync.test.tsx \
  ../packages/ui/src/store/__tests__/connection.test.ts \
  --reporter=verbose
```

Expected: PASS, with quickstart using same-origin HTTP paths and hosted mode remaining unchanged.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/request-core.ts \
  apps/packages/ui/src/services/tldw/__tests__/request-core.quickstart.test.ts \
  apps/packages/ui/src/services/tldw/__tests__/request-core.hosted.test.ts \
  apps/packages/ui/src/services/acp/client.ts \
  apps/packages/ui/src/services/acp/__tests__/client.test.ts \
  apps/packages/ui/src/hooks/document-workspace/useReadingProgress.ts \
  apps/packages/ui/src/hooks/document-workspace/__tests__/useReadingProgress.test.tsx \
  apps/packages/ui/src/hooks/document-workspace/useAnnotationSync.ts \
  apps/packages/ui/src/hooks/document-workspace/__tests__/useAnnotationSync.test.tsx \
  apps/packages/ui/src/components/Option/AgentRegistry/index.tsx \
  apps/packages/ui/src/store/connection.tsx \
  apps/packages/ui/src/store/__tests__/connection.test.ts
git commit -m "refactor: route shared http transport through webui origin"
```

## Task 4: Centralize Shared WebSocket Builders And Prove A WS-Backed Quickstart Flow

**Files:**
- Modify: `apps/packages/ui/src/services/persona-stream.ts`
- Modify: `apps/packages/ui/src/services/prompt-studio-stream.ts`
- Modify: `apps/packages/ui/src/services/watchlists-stream.ts`
- Modify: `apps/packages/ui/src/services/acp/client.ts`
- Modify: `apps/packages/ui/src/hooks/useVoiceChatStream.tsx`
- Modify: `apps/packages/ui/src/services/__tests__/persona-stream.test.ts`
- Modify: `apps/packages/ui/src/services/__tests__/prompt-studio-stream.test.ts`
- Modify: `apps/packages/ui/src/services/__tests__/watchlists-stream.test.ts`
- Modify: `apps/packages/ui/src/services/acp/__tests__/client.test.ts`
- Modify: `apps/packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx`
- Modify: `apps/tldw-frontend/e2e/utils/helpers.ts`
- Modify: `apps/tldw-frontend/e2e/workflows/persona-live.spec.ts`

- [ ] **Step 1: Write the failing WS builder tests**

Cover:

- quickstart persona/prompt/watchlists/ACP/voice-chat WS URLs use the WebUI origin
- advanced mode keeps explicit absolute WS origins
- auth query parameters remain unchanged

```ts
it("uses the webui origin for quickstart persona websocket URLs", () => {
  expect(
    buildPersonaWebSocketUrl({
      serverUrl: "http://127.0.0.1:8080",
      authMode: "single-user",
      apiKey: "abc123",
      accessToken: ""
    })
  ).toBe("ws://127.0.0.1:8080/api/v1/persona/stream?api_key=abc123")
})
```

Keep the Playwright persona-live proof from Task 0 in the runtime suite and strengthen it if needed so it fails whenever the page falls back to a direct backend WS origin.

- [ ] **Step 2: Run the failing WS tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  ../packages/ui/src/services/__tests__/persona-stream.test.ts \
  ../packages/ui/src/services/__tests__/prompt-studio-stream.test.ts \
  ../packages/ui/src/services/__tests__/watchlists-stream.test.ts \
  ../packages/ui/src/services/acp/__tests__/client.test.ts \
  ../packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx \
  --reporter=verbose

cd apps/tldw-frontend && \
TLDW_WEB_URL=http://127.0.0.1:8080 \
TLDW_SERVER_URL=http://127.0.0.1:8000 \
TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY \
bunx playwright test e2e/workflows/persona-live.spec.ts --reporter=line
```

Expected: FAIL because the shared WS builders still derive `ws://...:8000` from `serverUrl` or the quickstart harness still seeds an explicit backend origin into the page.

- [ ] **Step 3: Refactor all touched WS callers onto the shared WS base helper**

Use the shared browser transport helper everywhere instead of hand-rolling `serverUrl.replace(/^http/, "ws")`.

```ts
const wsBase = buildBrowserWebSocketBase(
  resolveBrowserTransport({
    config,
    surface: "webui-page",
    pageOrigin: typeof window !== "undefined" ? window.location.origin : null
  })
)

return `${wsBase}/api/v1/persona/stream?${params.toString()}`
```

Update:

- `persona-stream.ts`
- `prompt-studio-stream.ts`
- `watchlists-stream.ts`
- `ACPWebSocketClient`
- `useVoiceChatStream.tsx`

Do not change auth query semantics; only the WS base/origin decision should move.

- [ ] **Step 4: Re-run the WS tests and live proof**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  ../packages/ui/src/services/__tests__/persona-stream.test.ts \
  ../packages/ui/src/services/__tests__/prompt-studio-stream.test.ts \
  ../packages/ui/src/services/__tests__/watchlists-stream.test.ts \
  ../packages/ui/src/services/acp/__tests__/client.test.ts \
  ../packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx \
  --reporter=verbose

cd apps/tldw-frontend && \
TLDW_WEB_URL=http://127.0.0.1:8080 \
TLDW_SERVER_URL=http://127.0.0.1:8000 \
TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY \
bunx playwright test e2e/workflows/persona-live.spec.ts --reporter=line
```

Expected: PASS, with the representative live persona flow using a WS URL on the WebUI origin.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/services/persona-stream.ts \
  apps/packages/ui/src/services/prompt-studio-stream.ts \
  apps/packages/ui/src/services/watchlists-stream.ts \
  apps/packages/ui/src/services/acp/client.ts \
  apps/packages/ui/src/hooks/useVoiceChatStream.tsx \
  apps/packages/ui/src/services/__tests__/persona-stream.test.ts \
  apps/packages/ui/src/services/__tests__/prompt-studio-stream.test.ts \
  apps/packages/ui/src/services/__tests__/watchlists-stream.test.ts \
  apps/packages/ui/src/services/acp/__tests__/client.test.ts \
  apps/packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx \
  apps/tldw-frontend/e2e/utils/helpers.ts \
  apps/tldw-frontend/e2e/workflows/persona-live.spec.ts
git commit -m "refactor: route shared websocket transport through webui origin"
```

## Task 5: Fix The Docker Single-User Story, Lock Contracts, And Run Final Verification

**Files:**
- Modify: `README.md`
- Modify: `Docs/Getting_Started/Profile_Docker_Single_User.md`
- Modify: `Docs/Website/index.html`
- Modify: `tldw_Server_API/tests/Docs/test_quickstart_same_origin_docs.py`
- Modify: `tldw_Server_API/tests/Utils/test_makefile_quickstart_same_origin.py`
- Modify: `tldw_Server_API/tests/Utils/test_docker_quickstart_hardening.py`

- [ ] **Step 1: Write the failing docs/contract expectations**

Lock the final user story:

- Docker single-user guide launches `make quickstart` or the explicit WebUI overlay stack, not the API-only compose path
- verify steps include `http://127.0.0.1:8080`
- advanced override guidance always requires both `NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE=advanced` and `NEXT_PUBLIC_API_URL`

```py
def test_single_user_profile_uses_webui_quickstart_path():
    text = PROFILE.read_text()
    assert "make quickstart" in text or "docker-compose.webui.yml" in text
    assert "http://127.0.0.1:8080" in text
```

- [ ] **Step 2: Run the failing docs/contract tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Docs/test_quickstart_same_origin_docs.py \
  tldw_Server_API/tests/Utils/test_makefile_quickstart_same_origin.py \
  tldw_Server_API/tests/Utils/test_docker_quickstart_hardening.py \
  -q
```

Expected: FAIL because `Profile_Docker_Single_User.md` still launches the API-only compose path and does not verify the WebUI endpoint.

- [ ] **Step 3: Update the docs to the real quickstart path**

Prefer `make quickstart` as the primary command, with the explicit compose overlay as the fallback/manual equivalent.

````md
## Run

```bash
make quickstart
```

## Verify

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/docs > /dev/null && echo "docs-ok"
curl -sS http://127.0.0.1:8000/api/v1/config/quickstart
curl -sS http://127.0.0.1:8080 > /dev/null && echo "webui-ok"
```
````

- [ ] **Step 4: Run the final focused verification sweep**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  __tests__/frontend-quickstart-networking.test.ts \
  __tests__/app/app-networking-guard.test.tsx \
  __tests__/extension/runtime-bootstrap.test.ts \
  ../packages/ui/src/services/tldw/__tests__/browser-networking.test.ts \
  ../packages/ui/src/services/tldw/__tests__/request-core.quickstart.test.ts \
  ../packages/ui/src/services/tldw/__tests__/request-core.hosted.test.ts \
  ../packages/ui/src/services/acp/__tests__/client.test.ts \
  ../packages/ui/src/services/__tests__/persona-stream.test.ts \
  ../packages/ui/src/services/__tests__/prompt-studio-stream.test.ts \
  ../packages/ui/src/services/__tests__/watchlists-stream.test.ts \
  ../packages/ui/src/hooks/__tests__/useCanonicalConnectionConfig.test.tsx \
  ../packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx \
  ../packages/ui/src/hooks/document-workspace/__tests__/useReadingProgress.test.tsx \
  ../packages/ui/src/hooks/document-workspace/__tests__/useAnnotationSync.test.tsx \
  ../packages/ui/src/store/__tests__/connection.test.ts \
  --reporter=verbose

cd apps/tldw-frontend && \
TLDW_WEB_URL=http://127.0.0.1:8080 \
TLDW_SERVER_URL=http://127.0.0.1:8000 \
TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY \
bunx playwright test e2e/workflows/persona-live.spec.ts --reporter=line

source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Docs/test_quickstart_same_origin_docs.py \
  tldw_Server_API/tests/Utils/test_makefile_quickstart_same_origin.py \
  tldw_Server_API/tests/Utils/test_docker_quickstart_hardening.py \
  -q

source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/tests/Docs \
  tldw_Server_API/tests/Utils \
  -f json -o /tmp/bandit_quickstart_shared_runtime_followup.json
```

Expected: PASS. If any verification fails, fix the code before continuing; do not suppress or delete the failing test.

- [ ] **Step 5: Commit**

```bash
git add README.md \
  Docs/Getting_Started/Profile_Docker_Single_User.md \
  Docs/Website/index.html \
  tldw_Server_API/tests/Docs/test_quickstart_same_origin_docs.py \
  tldw_Server_API/tests/Utils/test_makefile_quickstart_same_origin.py \
  tldw_Server_API/tests/Utils/test_docker_quickstart_hardening.py
git commit -m "docs: align docker quickstart with webui transport"
```
