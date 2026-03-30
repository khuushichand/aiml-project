# Quickstart WebUI Same-Origin Networking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `make quickstart` use same-origin browser API calls through the WebUI container proxy, while keeping advanced absolute-API deployments available and failing fast on incoherent configs.

**Architecture:** Add a focused frontend networking helper that becomes the single source of truth for deployment mode, browser API base resolution, and invalid-configuration detection. In quickstart mode, Next.js proxies `/api/:path*` to the Docker `app` service so the browser never makes cross-origin API calls; advanced mode keeps explicit absolute API hosts and blocks known-bad localhost/non-localhost combinations.

**Tech Stack:** Next.js pages router, Axios, fetch/SSE helpers, React Testing Library, Vitest, Docker Compose, Makefile, pytest doc/contract tests

---

## File Structure

- `apps/tldw-frontend/lib/api-base.ts`
  Purpose: centralize deployment mode parsing, browser API origin resolution, base URL assembly, and fail-fast networking diagnostics.
- `apps/tldw-frontend/lib/api.ts`
  Purpose: consume the new helper for Axios defaults and exported API-base helpers.
- `apps/tldw-frontend/lib/api-config.ts`
  Purpose: keep helper-based API URL construction consistent for utility callers.
- `apps/tldw-frontend/hooks/useConfig.tsx`
  Purpose: persist runtime config without overriding quickstart same-origin behavior.
- `apps/tldw-frontend/lib/api/researchRuns.ts`
  Purpose: ensure SSE endpoint URLs continue working when API base is relative.
- `apps/tldw-frontend/lib/api/notifications.ts`
  Purpose: ensure notification streaming works with same-origin API bases.
- `apps/tldw-frontend/next.config.mjs`
  Purpose: add quickstart-only proxy rewrites to the internal Docker API service.
- `apps/tldw-frontend/components/networking/ConfigurationGuard.tsx`
  Purpose: block rendering when deployment mode and browser/API origin are incompatible.
- `apps/tldw-frontend/components/networking/ConfigurationErrorScreen.tsx`
  Purpose: show targeted remediation instructions instead of generic network/CORS breakage.
- `apps/tldw-frontend/pages/_app.tsx`
  Purpose: mount the configuration guard at the app shell boundary.
- `apps/tldw-frontend/scripts/validate-networking-config.mjs`
  Purpose: fail builds or startup scripts when quickstart and advanced env combinations are incoherent.
- `Dockerfiles/Dockerfile.webui`
  Purpose: pass deployment-mode env/build args and run the networking validator before shipping the bundle.
- `Dockerfiles/docker-compose.webui.yml`
  Purpose: wire quickstart mode and internal proxy target into the default WebUI container.
- `Makefile`
  Purpose: make `quickstart` and `quickstart-docker-webui` opt into same-origin quickstart mode by default while leaving advanced overrides available.
- `apps/tldw-frontend/lib/__tests__/api-base.test.ts`
  Purpose: cover deployment mode, relative API base generation, and mismatch detection.
- `apps/tldw-frontend/hooks/__tests__/useConfig.networking.test.tsx`
  Purpose: verify quickstart mode ignores stale absolute hosts and advanced mode still respects explicit hosts.
- `apps/tldw-frontend/__tests__/frontend-quickstart-networking.test.ts`
  Purpose: verify Next.js rewrites and quickstart env expectations.
- `apps/tldw-frontend/__tests__/app/app-networking-guard.test.tsx`
  Purpose: verify the blocking configuration UI appears for bad advanced-mode combinations.
- `apps/tldw-frontend/lib/__tests__/researchRuns.test.ts`
  Purpose: confirm SSE URL building still works after the helper migration.
- `apps/tldw-frontend/lib/__tests__/notifications.test.ts`
  Purpose: confirm notification streaming still works with same-origin API bases.
- `README.md`
  Purpose: redefine the default quickstart story as same-origin from the browser perspective.
- `Docs/Getting_Started/README.md`
  Purpose: make the onboarding index describe LAN/custom-host access as advanced.
- `Docs/Getting_Started/Profile_Docker_Single_User.md`
  Purpose: update the default Docker single-user profile to the new networking contract.
- `Docs/Website/index.html`
  Purpose: keep the public quick-start copy aligned with the same-origin default.
- `apps/tldw-frontend/README.md`
  Purpose: clarify quickstart versus advanced/custom-host WebUI networking.
- `tldw_Server_API/tests/Docs/test_quickstart_same_origin_docs.py`
  Purpose: lock the docs wording to the new quickstart contract.
- `tldw_Server_API/tests/Utils/test_makefile_quickstart_same_origin.py`
  Purpose: lock the Makefile quickstart defaults to same-origin WebUI mode.

## Task 1: Add a deployment-mode and API-base helper

**Files:**
- Create: `apps/tldw-frontend/lib/api-base.ts`
- Test: `apps/tldw-frontend/lib/__tests__/api-base.test.ts`

- [ ] **Step 1: Write the failing helper tests**

```ts
import { describe, expect, it } from "vitest"
import {
  buildApiBaseUrl,
  detectNetworkingIssue,
  resolveDeploymentMode,
  resolvePublicApiOrigin
} from "@web/lib/api-base"

describe("api-base", () => {
  it("uses a same-origin relative base in quickstart mode", () => {
    expect(resolveDeploymentMode({ NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE: "quickstart" })).toBe("quickstart")
    expect(resolvePublicApiOrigin({ NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE: "quickstart" }, "http://localhost:8080")).toBe("")
    expect(buildApiBaseUrl("", "v1")).toBe("/api/v1")
  })

  it("keeps explicit absolute API origins in advanced mode", () => {
    expect(
      resolvePublicApiOrigin(
        {
          NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE: "advanced",
          NEXT_PUBLIC_API_URL: "https://api.example.test"
        },
        "https://app.example.test"
      )
    ).toBe("https://api.example.test")
  })

  it("flags localhost API URLs when the page origin is not loopback", () => {
    expect(
      detectNetworkingIssue(
        {
          NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE: "advanced",
          NEXT_PUBLIC_API_URL: "http://127.0.0.1:8000"
        },
        "http://192.168.5.184:8080"
      )?.kind
    ).toBe("loopback_api_not_browser_reachable")
  })
})
```

- [ ] **Step 2: Run the helper tests to verify they fail**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run lib/__tests__/api-base.test.ts --reporter=verbose
```

Expected: FAIL with a missing module or missing export error for `@web/lib/api-base`.

- [ ] **Step 3: Implement the helper**

```ts
export type TldwDeploymentMode = "quickstart" | "advanced"

export function resolveDeploymentMode(
  env: Record<string, string | undefined>
): TldwDeploymentMode {
  return env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE === "quickstart"
    ? "quickstart"
    : "advanced"
}

export function resolvePublicApiOrigin(
  env: Record<string, string | undefined>,
  pageOrigin?: string
): string {
  const mode = resolveDeploymentMode(env)
  if (mode === "quickstart") return ""
  return (env.NEXT_PUBLIC_API_URL || pageOrigin || "").replace(/\/$/, "")
}

export function buildApiBaseUrl(origin: string, version: string): string {
  const cleanVersion = version || "v1"
  return origin ? `${origin}/api/${cleanVersion}` : `/api/${cleanVersion}`
}
```

Implement loopback/non-loopback mismatch detection in the same file so later tasks can reuse it without re-parsing env state in multiple places.

- [ ] **Step 4: Re-run the helper tests to verify they pass**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run lib/__tests__/api-base.test.ts --reporter=verbose
```

Expected: PASS for all helper cases.

- [ ] **Step 5: Commit**

```bash
git add apps/tldw-frontend/lib/api-base.ts apps/tldw-frontend/lib/__tests__/api-base.test.ts
git commit -m "refactor: add webui api base resolver"
```

## Task 2: Migrate API consumers to the new helper

**Files:**
- Modify: `apps/tldw-frontend/lib/api.ts`
- Modify: `apps/tldw-frontend/lib/api-config.ts`
- Modify: `apps/tldw-frontend/hooks/useConfig.tsx`
- Modify: `apps/tldw-frontend/lib/api/researchRuns.ts`
- Modify: `apps/tldw-frontend/lib/api/notifications.ts`
- Modify: `apps/tldw-frontend/lib/__tests__/researchRuns.test.ts`
- Modify: `apps/tldw-frontend/lib/__tests__/notifications.test.ts`
- Test: `apps/tldw-frontend/hooks/__tests__/useConfig.networking.test.tsx`

- [ ] **Step 1: Write the failing consumer tests**

```tsx
it("keeps quickstart mode on a relative /api/v1 base", async () => {
  process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = "quickstart"
  render(<ConfigProvider><div /></ConfigProvider>)
  expect(getApiBaseUrl()).toBe("/api/v1")
})

it("does not let a stored absolute host override quickstart mode", async () => {
  localStorage.setItem("tldw-api-host", "http://127.0.0.1:8000")
  process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = "quickstart"
  render(<ConfigProvider><div /></ConfigProvider>)
  expect(getApiBaseUrl()).toBe("/api/v1")
})
```

Update `researchRuns.test.ts` and `notifications.test.ts` so at least one case asserts relative API bases generate `/api/v1/...` SSE URLs instead of absolute localhost URLs.

- [ ] **Step 2: Run the failing consumer tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  hooks/__tests__/useConfig.networking.test.tsx \
  lib/__tests__/researchRuns.test.ts \
  lib/__tests__/notifications.test.ts \
  --reporter=verbose
```

Expected: FAIL because `api.ts`, `useConfig.tsx`, and the streaming helpers still assume absolute hosts.

- [ ] **Step 3: Refactor the consumers to use the helper**

```ts
import {
  buildApiBaseUrl,
  resolveDeploymentMode,
  resolvePublicApiOrigin
} from "@web/lib/api-base"

const deploymentMode = resolveDeploymentMode(process.env)
const publicApiOrigin = resolvePublicApiOrigin(process.env)
const baseURL = buildApiBaseUrl(publicApiOrigin, process.env.NEXT_PUBLIC_API_VERSION || "v1")
```

Apply the same helper in:

- `lib/api.ts` for Axios defaults and exported `getApiBaseUrl`
- `lib/api-config.ts` for URL construction helpers
- `hooks/useConfig.tsx` so quickstart mode keeps `/api/v1` even if local storage contains an absolute host
- streaming callers that append endpoint paths to `getApiBaseUrl()`

- [ ] **Step 4: Re-run the consumer tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  lib/__tests__/api-base.test.ts \
  hooks/__tests__/useConfig.networking.test.tsx \
  lib/__tests__/researchRuns.test.ts \
  lib/__tests__/notifications.test.ts \
  --reporter=verbose
```

Expected: PASS, including the relative-base SSE URL assertions.

- [ ] **Step 5: Commit**

```bash
git add \
  apps/tldw-frontend/lib/api.ts \
  apps/tldw-frontend/lib/api-config.ts \
  apps/tldw-frontend/hooks/useConfig.tsx \
  apps/tldw-frontend/lib/api/researchRuns.ts \
  apps/tldw-frontend/lib/api/notifications.ts \
  apps/tldw-frontend/hooks/__tests__/useConfig.networking.test.tsx \
  apps/tldw-frontend/lib/__tests__/researchRuns.test.ts \
  apps/tldw-frontend/lib/__tests__/notifications.test.ts
git commit -m "refactor: make webui api clients deployment-aware"
```

## Task 3: Wire same-origin quickstart proxying into Next.js and Docker

**Files:**
- Modify: `apps/tldw-frontend/next.config.mjs`
- Modify: `Dockerfiles/Dockerfile.webui`
- Modify: `Dockerfiles/docker-compose.webui.yml`
- Modify: `Makefile`
- Test: `apps/tldw-frontend/__tests__/frontend-quickstart-networking.test.ts`

- [ ] **Step 1: Write the failing proxy/config tests**

```ts
it("adds an /api proxy rewrite in quickstart mode", async () => {
  process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = "quickstart"
  process.env.TLDW_INTERNAL_API_ORIGIN = "http://app:8000"
  const nextConfig = await loadNextConfig()
  const rewrites = await nextConfig.rewrites()
  expect(rewrites).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        source: "/api/:path*",
        destination: "http://app:8000/api/:path*"
      })
    ])
  )
})

it("keeps quickstart Make defaults in same-origin mode", () => {
  expect(makefileText).toContain('NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE ?= quickstart')
})
```

- [ ] **Step 2: Run the failing proxy/config tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run __tests__/frontend-quickstart-networking.test.ts --reporter=verbose
```

Expected: FAIL because no quickstart proxy rewrite exists and the Makefile/Docker defaults still bake an external localhost API URL.

- [ ] **Step 3: Implement the proxy and quickstart env wiring**

```js
const deploymentMode = process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE || "advanced"
const internalApiOrigin = (process.env.TLDW_INTERNAL_API_ORIGIN || "http://app:8000").replace(/\/$/, "")

async rewrites() {
  if (deploymentMode !== "quickstart") {
    return []
  }
  return [
    {
      source: "/api/:path*",
      destination: `${internalApiOrigin}/api/:path*`,
    },
  ]
}
```

Apply the same quickstart contract to Docker/Make:

- set `NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE=quickstart` for the default WebUI quickstart path
- provide `TLDW_INTERNAL_API_ORIGIN=http://app:8000`
- stop requiring `NEXT_PUBLIC_API_URL` to be browser-reachable for the default quickstart path
- keep an advanced override path for explicit absolute API URLs

- [ ] **Step 4: Re-run the proxy/config tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  __tests__/frontend-quickstart-networking.test.ts \
  __tests__/frontend-dev-config.test.ts \
  --reporter=verbose
```

Expected: PASS, with proxy rewrites present only in quickstart mode.

- [ ] **Step 5: Commit**

```bash
git add \
  apps/tldw-frontend/next.config.mjs \
  apps/tldw-frontend/__tests__/frontend-quickstart-networking.test.ts \
  Dockerfiles/Dockerfile.webui \
  Dockerfiles/docker-compose.webui.yml \
  Makefile
git commit -m "feat: proxy quickstart webui api traffic"
```

## Task 4: Add fail-fast networking validation and blocking UI

**Files:**
- Create: `apps/tldw-frontend/components/networking/ConfigurationGuard.tsx`
- Create: `apps/tldw-frontend/components/networking/ConfigurationErrorScreen.tsx`
- Create: `apps/tldw-frontend/scripts/validate-networking-config.mjs`
- Modify: `apps/tldw-frontend/pages/_app.tsx`
- Modify: `Dockerfiles/Dockerfile.webui`
- Test: `apps/tldw-frontend/__tests__/app/app-networking-guard.test.tsx`

- [ ] **Step 1: Write the failing guard tests**

```tsx
it("blocks rendering when advanced mode points at loopback from a LAN page origin", async () => {
  process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = "advanced"
  process.env.NEXT_PUBLIC_API_URL = "http://127.0.0.1:8000"
  window.history.replaceState({}, "", "http://192.168.5.184:8080/")

  renderApp("/media")

  expect(await screen.findByTestId("networking-config-error")).toBeInTheDocument()
  expect(screen.getByText(/only reachable from the host machine/i)).toBeInTheDocument()
})
```

Add a script-level test or assertion in the same suite that expects the validator to reject quickstart mode when the internal API origin is missing.

- [ ] **Step 2: Run the failing guard tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run __tests__/app/app-networking-guard.test.tsx --reporter=verbose
```

Expected: FAIL because `_app.tsx` does not currently mount a networking guard and no validator script exists.

- [ ] **Step 3: Implement the guard and validator**

```tsx
export function ConfigurationGuard({ children }: { children: React.ReactNode }) {
  const issue = detectNetworkingIssue(process.env, window.location.origin)
  if (issue) {
    return <ConfigurationErrorScreen issue={issue} />
  }
  return <>{children}</>
}
```

```js
if (mode === "quickstart" && !internalApiOrigin) {
  throw new Error("Quickstart mode requires TLDW_INTERNAL_API_ORIGIN")
}
```

Mount the guard near the top of `_app.tsx` so the user sees the targeted message before broken pages start issuing network requests. Run the validator from `Dockerfile.webui` before the production build step and/or in the runtime boot command if build-time validation alone is insufficient.

- [ ] **Step 4: Re-run the guard tests**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  __tests__/app/app-networking-guard.test.tsx \
  __tests__/app/app-layout.test.tsx \
  --reporter=verbose
```

Expected: PASS, with the new guard only blocking invalid combinations.

- [ ] **Step 5: Commit**

```bash
git add \
  apps/tldw-frontend/components/networking/ConfigurationGuard.tsx \
  apps/tldw-frontend/components/networking/ConfigurationErrorScreen.tsx \
  apps/tldw-frontend/scripts/validate-networking-config.mjs \
  apps/tldw-frontend/pages/_app.tsx \
  apps/tldw-frontend/__tests__/app/app-networking-guard.test.tsx \
  Dockerfiles/Dockerfile.webui
git commit -m "feat: fail fast on invalid webui networking config"
```

## Task 5: Update onboarding docs and contract tests

**Files:**
- Modify: `README.md`
- Modify: `Docs/Getting_Started/README.md`
- Modify: `Docs/Getting_Started/Profile_Docker_Single_User.md`
- Modify: `Docs/Website/index.html`
- Modify: `apps/tldw-frontend/README.md`
- Create: `tldw_Server_API/tests/Docs/test_quickstart_same_origin_docs.py`
- Create: `tldw_Server_API/tests/Utils/test_makefile_quickstart_same_origin.py`

- [ ] **Step 1: Write the failing docs/contract tests**

```py
from pathlib import Path

def test_readme_states_default_quickstart_is_same_origin() -> None:
    text = Path("README.md").read_text(encoding="utf-8")
    assert "same-origin" in text.lower()
    assert "browser CORS should not be part of the normal quickstart failure mode" in text

def test_makefile_defaults_quickstart_webui_mode() -> None:
    text = Path("Makefile").read_text(encoding="utf-8")
    assert "NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE ?= quickstart" in text
```

- [ ] **Step 2: Run the failing docs/contract tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Docs/test_quickstart_same_origin_docs.py \
  tldw_Server_API/tests/Utils/test_makefile_quickstart_same_origin.py \
  -v
```

Expected: FAIL until the docs and Makefile wording/defaults are updated.

- [ ] **Step 3: Update the docs**

Make the default story explicit:

- `make quickstart` is same-origin from the browser perspective
- `localhost:8080` is the normal entrypoint
- LAN/custom-host access is advanced configuration
- browser CORS errors are not the expected first-run failure mode for the default quickstart

Preserve the advanced deployment path, but move it out of the main happy path copy.

- [ ] **Step 4: Re-run the docs/contract tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Docs/test_quickstart_same_origin_docs.py \
  tldw_Server_API/tests/Utils/test_makefile_quickstart_same_origin.py \
  tldw_Server_API/tests/Docs/test_onboarding_entrypoints.py \
  tldw_Server_API/tests/Docs/test_onboarding_dev_docs.py \
  tldw_Server_API/tests/Utils/test_makefile_quickstart_default.py \
  -v
```

Expected: PASS, with the new assertions reinforcing the quickstart contract.

- [ ] **Step 5: Commit**

```bash
git add \
  README.md \
  Docs/Getting_Started/README.md \
  Docs/Getting_Started/Profile_Docker_Single_User.md \
  Docs/Website/index.html \
  apps/tldw-frontend/README.md \
  tldw_Server_API/tests/Docs/test_quickstart_same_origin_docs.py \
  tldw_Server_API/tests/Utils/test_makefile_quickstart_same_origin.py
git commit -m "docs: clarify same-origin quickstart networking"
```

## Task 6: Run final verification before handoff

**Files:**
- Test only; no planned file changes

- [ ] **Step 1: Run the targeted frontend test sweep**

Run:

```bash
cd apps/tldw-frontend && bunx vitest run \
  lib/__tests__/api-base.test.ts \
  hooks/__tests__/useConfig.networking.test.tsx \
  lib/__tests__/researchRuns.test.ts \
  lib/__tests__/notifications.test.ts \
  __tests__/frontend-dev-config.test.ts \
  __tests__/frontend-quickstart-networking.test.ts \
  __tests__/app/app-layout.test.tsx \
  __tests__/app/app-networking-guard.test.tsx \
  --reporter=verbose
```

Expected: PASS.

- [ ] **Step 2: Run the targeted Python doc/contract sweep**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Docs/test_quickstart_same_origin_docs.py \
  tldw_Server_API/tests/Docs/test_onboarding_entrypoints.py \
  tldw_Server_API/tests/Docs/test_onboarding_dev_docs.py \
  tldw_Server_API/tests/Utils/test_makefile_quickstart_default.py \
  tldw_Server_API/tests/Utils/test_makefile_quickstart_same_origin.py \
  -v
```

Expected: PASS.

- [ ] **Step 3: Validate Docker Compose wiring**

Run:

```bash
docker compose --env-file tldw_Server_API/Config_Files/.env \
  -f Dockerfiles/docker-compose.yml \
  -f Dockerfiles/docker-compose.webui.yml \
  config > /tmp/quickstart_webui_same_origin_compose.txt
```

Expected: PASS, with `webui` receiving quickstart deployment-mode env and the internal API origin.

- [ ] **Step 4: Run Bandit on touched Python scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/tests/Docs \
  tldw_Server_API/tests/Utils \
  -f json \
  -o /tmp/bandit_quickstart_same_origin.json
```

Expected: no new findings in the touched quickstart-related test files.

- [ ] **Step 5: Final commit if verification required follow-up fixes**

```bash
git add \
  apps/tldw-frontend/lib/api-base.ts \
  apps/tldw-frontend/lib/api.ts \
  apps/tldw-frontend/lib/api-config.ts \
  apps/tldw-frontend/hooks/useConfig.tsx \
  apps/tldw-frontend/lib/api/researchRuns.ts \
  apps/tldw-frontend/lib/api/notifications.ts \
  apps/tldw-frontend/next.config.mjs \
  apps/tldw-frontend/pages/_app.tsx \
  apps/tldw-frontend/components/networking/ConfigurationGuard.tsx \
  apps/tldw-frontend/components/networking/ConfigurationErrorScreen.tsx \
  apps/tldw-frontend/scripts/validate-networking-config.mjs \
  apps/tldw-frontend/lib/__tests__/api-base.test.ts \
  apps/tldw-frontend/lib/__tests__/researchRuns.test.ts \
  apps/tldw-frontend/lib/__tests__/notifications.test.ts \
  apps/tldw-frontend/hooks/__tests__/useConfig.networking.test.tsx \
  apps/tldw-frontend/__tests__/frontend-quickstart-networking.test.ts \
  apps/tldw-frontend/__tests__/app/app-layout.test.tsx \
  apps/tldw-frontend/__tests__/app/app-networking-guard.test.tsx \
  Dockerfiles/Dockerfile.webui \
  Dockerfiles/docker-compose.webui.yml \
  Makefile \
  README.md \
  Docs/Getting_Started/README.md \
  Docs/Getting_Started/Profile_Docker_Single_User.md \
  Docs/Website/index.html \
  apps/tldw-frontend/README.md \
  tldw_Server_API/tests/Docs/test_quickstart_same_origin_docs.py \
  tldw_Server_API/tests/Utils/test_makefile_quickstart_same_origin.py
git commit -m "test: lock quickstart same-origin networking contract"
```
