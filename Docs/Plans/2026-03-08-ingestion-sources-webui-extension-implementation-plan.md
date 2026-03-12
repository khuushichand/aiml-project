# Ingestion Sources WebUI and Extension Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a shared full-page ingestion-source management workspace for the WebUI and extension options app, including list, create, detail, sync, archive upload, and notes-item reattach flows for the signed-in user.

**Architecture:** Put the shared data client, React Query hooks, i18n, routes, and page components in `apps/packages/ui`, then mount those routes in both the Next.js WebUI and the extension options shell. Keep `/admin/sources` as a route-level mirror of the same UI so the information architecture is ready for future cross-user admin APIs without forking the implementation now.

**Tech Stack:** React, TypeScript, React Router, TanStack Query, Ant Design, lucide-react, Vitest, Testing Library, Next.js dynamic route shims, Playwright extension E2E.

---

## Stage 1: Shared Data Plumbing
**Goal:** Expose the ingestion-source backend through the shared frontend client and typed hooks.
**Success Criteria:** Shared UI code can list sources, fetch detail/items, create/update sources, sync, upload archives, and reattach items through typed methods and cached hooks.
**Tests:** `bunx vitest run apps/packages/ui/src/services/__tests__/server-capabilities.test.ts apps/packages/ui/src/services/__tests__/tldw-api-client.ingestion-sources.test.ts apps/packages/ui/src/hooks/__tests__/use-ingestion-sources.test.ts`
**Status:** Not Started

### Task 1: Add ingestion-source capability detection

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/server-capabilities.ts`
- Test: `apps/packages/ui/src/services/__tests__/server-capabilities.test.ts`

**Step 1: Write the failing test**

```ts
it("detects ingestion source support from advertised paths and fallback spec", async () => {
  mocks.getOpenAPISpec.mockResolvedValue({
    info: { version: "2026.03" },
    paths: {
      "/api/v1/ingestion-sources": {},
      "/api/v1/ingestion-sources/{source_id}": {}
    }
  })
  mocks.bgRequest.mockResolvedValue({})

  const { getServerCapabilities } = await importCapabilitiesModule()
  const capabilities = await getServerCapabilities()

  expect(capabilities.hasIngestionSources).toBe(true)
})
```

Add a companion assertion that the fallback spec also reports `hasIngestionSources` once the route is known.

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/services/__tests__/server-capabilities.test.ts`

Expected: FAIL because `ServerCapabilities` does not include `hasIngestionSources`.

**Step 3: Write minimal implementation**

```ts
export type ServerCapabilities = {
  hasChat: boolean
  hasRag: boolean
  hasMedia: boolean
  hasNotes: boolean
  hasIngestionSources: boolean
  // ...
}
```

Update:
- `defaultCapabilities`
- path-to-capability derivation
- fallback spec path list to include `/api/v1/ingestion-sources`

Keep this scoped to route availability. Do not add speculative per-source-type flags yet unless the backend explicitly advertises them.

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/services/__tests__/server-capabilities.test.ts`

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/server-capabilities.ts apps/packages/ui/src/services/__tests__/server-capabilities.test.ts
git commit -m "feat: add ingestion source capability detection"
```

### Task 2: Add ingestion-source DTOs and API client methods

**Files:**
- Create: `apps/packages/ui/src/types/ingestion-sources.ts`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Test: `apps/packages/ui/src/services/__tests__/tldw-api-client.ingestion-sources.test.ts`

**Step 1: Write the failing test**

```ts
it("lists ingestion sources and normalizes ids/counts", async () => {
  mocks.bgRequest.mockResolvedValueOnce({
    sources: [
      {
        id: 7,
        source_type: "archive_snapshot",
        sink_type: "notes",
        enabled: true,
        last_successful_sync_summary: {
          changed_count: 2,
          degraded_count: 1,
          conflict_count: 0
        }
      }
    ],
    total: 1
  })

  const client = new TldwApiClient()
  const result = await client.listIngestionSources()

  expect(result.sources[0].id).toBe("7")
  expect(result.sources[0].last_successful_sync_summary?.degraded_count).toBe(1)
})
```

Add companion tests in the same file for:
- `getIngestionSource(sourceId)`
- `listIngestionSourceItems(sourceId, filters?)`
- `createIngestionSource(payload)`
- `updateIngestionSource(sourceId, payload)`
- `syncIngestionSource(sourceId)`
- `uploadIngestionSourceArchive(sourceId, file)`
- `reattachIngestionSourceItem(sourceId, itemId)`

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/services/__tests__/tldw-api-client.ingestion-sources.test.ts`

Expected: FAIL with missing `TldwApiClient` methods and missing ingestion-source types.

**Step 3: Write minimal implementation**

```ts
export type IngestionSourceType = "local_directory" | "archive_snapshot"
export type IngestionSinkType = "media" | "notes"
export type IngestionLifecyclePolicy = "canonical" | "import_only"

export interface IngestionSourceSummary {
  id: string
  source_type: IngestionSourceType
  sink_type: IngestionSinkType
  enabled: boolean
  last_successful_sync_summary?: {
    changed_count: number
    degraded_count: number
    conflict_count: number
    sink_failure_count?: number
    ingestion_failure_count?: number
  } | null
}
```

Add corresponding request/response interfaces for detail, items, create, patch, sync, upload, and reattach. In `TldwApiClient.ts`, follow the existing client guard-rail pattern by using `this.request(...)` and `this.upload(...)`, not direct `bgRequest`/`bgUpload` calls:

```ts
async listIngestionSources() {
  const response = await this.request({
    path: "/api/v1/ingestion-sources",
    method: "GET"
  })
  return normalizeIngestionSourceListResponse(response)
}

async uploadIngestionSourceArchive(sourceId: string, file: File) {
  const encodedSourceId = encodeURIComponent(sourceId)
  return await this.upload({
    path: `/api/v1/ingestion-sources/${encodedSourceId}/archive`,
    method: "POST",
    fileFieldName: "file",
    file
  })
}
```

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/services/__tests__/tldw-api-client.ingestion-sources.test.ts`

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/types/ingestion-sources.ts apps/packages/ui/src/services/tldw/TldwApiClient.ts apps/packages/ui/src/services/__tests__/tldw-api-client.ingestion-sources.test.ts
git commit -m "feat: add ingestion source api client"
```

### Task 3: Add shared React Query hooks and cache invalidation

**Files:**
- Create: `apps/packages/ui/src/hooks/use-ingestion-sources.ts`
- Test: `apps/packages/ui/src/hooks/__tests__/use-ingestion-sources.test.ts`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`

**Step 1: Write the failing test**

```ts
it("invalidates list and detail queries after syncing a source", async () => {
  const client = { syncIngestionSource: vi.fn(async () => ({ status: "queued" })) }
  const { result } = renderHook(() => useSyncIngestionSourceMutation(client as any), {
    wrapper: createQueryWrapper()
  })

  await act(async () => {
    await result.current.mutateAsync("12")
  })

  expect(client.syncIngestionSource).toHaveBeenCalledWith("12")
  expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ingestionSourceKeys.list() })
})
```

Cover:
- `useIngestionSourcesQuery`
- `useIngestionSourceDetailQuery`
- `useIngestionSourceItemsQuery`
- `useCreateIngestionSourceMutation`
- `useUpdateIngestionSourceMutation`
- `useSyncIngestionSourceMutation`
- `useUploadIngestionSourceArchiveMutation`
- `useReattachIngestionSourceItemMutation`

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/hooks/__tests__/use-ingestion-sources.test.ts`

Expected: FAIL because the hooks and `ingestionSourceKeys` do not exist.

**Step 3: Write minimal implementation**

```ts
export const ingestionSourceKeys = {
  all: () => ["ingestion-sources"] as const,
  list: () => ["ingestion-sources", "list"] as const,
  detail: (sourceId: string) => ["ingestion-sources", "detail", sourceId] as const,
  items: (sourceId: string, filters?: Record<string, unknown>) =>
    ["ingestion-sources", "items", sourceId, filters ?? {}] as const
}
```

Implement hooks with `useQuery` and `useMutation`, and invalidate:
- list after create/update/sync/upload
- detail after update/sync/upload
- items after reattach/upload/detail-affecting actions

Keep the tests easy to isolate, but follow the repo’s shared-client pattern by defaulting these hooks to `useTldwApiClient()` rather than constructing fresh `TldwApiClient` instances inside components.

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/hooks/__tests__/use-ingestion-sources.test.ts`

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/use-ingestion-sources.ts apps/packages/ui/src/hooks/__tests__/use-ingestion-sources.test.ts apps/packages/ui/src/services/tldw/TldwApiClient.ts
git commit -m "feat: add ingestion source query hooks"
```

## Stage 2: Shared Workspace and Create Flow
**Goal:** Build the signed-in user list workspace and dedicated create route in shared UI code, with normal unsupported/offline handling.
**Success Criteria:** `/sources` shows either a capability-aware unavailable state or a live source workspace with quick actions and summary states, and `/sources/new` creates local-directory or archive sources with inline validation.
**Tests:** `bunx vitest run apps/packages/ui/src/i18n/__tests__/sources-locale.test.ts apps/packages/ui/src/components/Option/Sources/__tests__/SourcesWorkspacePage.test.tsx apps/packages/ui/src/components/Option/Sources/__tests__/SourceForm.test.tsx`
**Status:** Not Started

### Task 4: Add i18n namespace and nav labels for Sources

**Files:**
- Create: `apps/packages/ui/src/assets/locale/en/sources.json`
- Modify: `apps/packages/ui/src/i18n/index.ts`
- Modify: `apps/packages/ui/src/i18n/lang/en.ts`
- Modify: `apps/packages/ui/src/assets/locale/en/option.json`
- Test: `apps/packages/ui/src/i18n/__tests__/sources-locale.test.ts`

**Step 1: Write the failing test**

```ts
it("registers the english sources namespace and nav label", () => {
  expect(en.sources.title).toBe("Sources")
  expect(en.option.header.sources).toBe("Sources")
})
```

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/i18n/__tests__/sources-locale.test.ts`

Expected: FAIL because the `sources` namespace and nav label are not registered yet.

**Step 3: Write minimal implementation**

Create `sources.json` with top-level copy used by the workspace:

```json
{
  "title": "Sources",
  "description": "Manage local folders and archive snapshots that sync into notes or media.",
  "offline": "Server is offline. Connect to manage ingestion sources.",
  "actions": {
    "new": "New source",
    "sync": "Sync now",
    "uploadArchive": "Upload archive",
    "reattach": "Reattach"
  }
}
```

Register `sources` in:
- `apps/packages/ui/src/i18n/index.ts` `NAMESPACES`
- `apps/packages/ui/src/i18n/lang/en.ts`
- `apps/packages/ui/src/assets/locale/en/option.json` under `header.sources`

Use fallback strings in components, but keep tokens wired from the start.

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/i18n/__tests__/sources-locale.test.ts`

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/assets/locale/en/sources.json apps/packages/ui/src/i18n/index.ts apps/packages/ui/src/i18n/lang/en.ts apps/packages/ui/src/assets/locale/en/option.json apps/packages/ui/src/i18n/__tests__/sources-locale.test.ts
git commit -m "feat: add ingestion source ui copy"
```

### Task 5: Build the Sources workspace list page

**Files:**
- Create: `apps/packages/ui/src/components/Option/Sources/index.tsx`
- Create: `apps/packages/ui/src/components/Option/Sources/SourcesWorkspacePage.tsx`
- Create: `apps/packages/ui/src/components/Option/Sources/SourceListTable.tsx`
- Create: `apps/packages/ui/src/components/Option/Sources/SourceStatusPanels.tsx`
- Test: `apps/packages/ui/src/components/Option/Sources/__tests__/SourcesWorkspacePage.test.tsx`

**Step 1: Write the failing test**

```tsx
it("renders sources with quick actions and degraded/conflict counts", async () => {
  renderWithQueryClient(<SourcesWorkspacePage />)

  expect(await screen.findByText("Archive Notes")).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Sync now" })).toBeEnabled()
  expect(screen.getByText(/degraded 2/i)).toBeInTheDocument()
  expect(screen.getByText(/detached 1/i)).toBeInTheDocument()
})
```

Also cover:
- offline empty state
- feature-unavailable state when `hasIngestionSources` is false
- create CTA links to `/sources/new`
- enable/disable mutation wiring
- admin view badge when `mode="admin"`

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/components/Option/Sources/__tests__/SourcesWorkspacePage.test.tsx`

Expected: FAIL because the components do not exist.

**Step 3: Write minimal implementation**

Follow the `Collections` and `Notes` page patterns:

```tsx
export const SourcesWorkspacePage = ({ mode = "user" }: { mode?: "user" | "admin" }) => {
  const { t } = useTranslation(["sources", "common", "option"])
  const isOnline = useServerOnline()
  const { capabilities, loading: capsLoading } = useServerCapabilities()
  const sourcesQuery = useIngestionSourcesQuery()

  if (!isOnline) {
    return <PageShell><Empty description={t("sources:offline", "Server is offline.")} /></PageShell>
  }

  if (!capsLoading && capabilities && !capabilities.hasIngestionSources) {
    return <SourcesFeatureUnavailable />
  }

  return (
    <PageShell className="py-6" maxWidthClassName="max-w-7xl">
      <SourceListTable />
    </PageShell>
  )
}
```

Use `PageShell`, `Empty`, `RouteErrorBoundary`, and `OptionLayout` patterns already used by `Collections` and admin pages. Keep the first version table-driven and operational, not tab-heavy.

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/components/Option/Sources/__tests__/SourcesWorkspacePage.test.tsx`

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Sources/index.tsx apps/packages/ui/src/components/Option/Sources/SourcesWorkspacePage.tsx apps/packages/ui/src/components/Option/Sources/SourceListTable.tsx apps/packages/ui/src/components/Option/Sources/SourceStatusPanels.tsx apps/packages/ui/src/components/Option/Sources/__tests__/SourcesWorkspacePage.test.tsx
git commit -m "feat: add ingestion sources workspace"
```

### Task 6: Build the dedicated create form

**Files:**
- Create: `apps/packages/ui/src/components/Option/Sources/SourceForm.tsx`
- Create: `apps/packages/ui/src/routes/option-sources-new.tsx`
- Test: `apps/packages/ui/src/components/Option/Sources/__tests__/SourceForm.test.tsx`

**Step 1: Write the failing test**

```tsx
it("switches fields between local directory and archive source modes", async () => {
  renderWithQueryClient(<SourceForm mode="create" />)

  expect(screen.getByLabelText("Server directory path")).toBeInTheDocument()
  expect(screen.getByText(/path on the tldw server host/i)).toBeInTheDocument()
  await user.click(screen.getByLabelText("Archive snapshot"))
  expect(screen.queryByLabelText("Server directory path")).not.toBeInTheDocument()
  expect(screen.getByText("Upload archive after creation")).toBeInTheDocument()
})
```

Add tests for:
- inline 400 validation errors
- immutable-field hints hidden during create
- successful create navigates to `/sources/:sourceId`

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/components/Option/Sources/__tests__/SourceForm.test.tsx`

Expected: FAIL because the form and route wrapper do not exist.

**Step 3: Write minimal implementation**

```tsx
<Form layout="vertical" onFinish={handleSubmit}>
  <Radio.Group value={sourceType} onChange={(event) => setSourceType(event.target.value)}>
    <Radio value="local_directory">Local directory</Radio>
    <Radio value="archive_snapshot">Archive snapshot</Radio>
  </Radio.Group>

  {sourceType === "local_directory" ? (
    <>
      <Form.Item name="path" label={t("sources:form.path", "Server directory path")}>
        <Input />
      </Form.Item>
      <Typography.Text type="secondary">
        {t(
          "sources:form.pathHelp",
          "This is a path on the tldw server host, not a local browser or extension folder."
        )}
      </Typography.Text>
    </>
  ) : (
    <Alert type="info" message={t("sources:form.archiveHint", "Upload archive after creation")} />
  )}
</Form>
```

Keep the form shared between create and edit modes. Do not expose immutable field editing after first successful sync; surface those fields as read-only summaries in edit mode instead.

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/components/Option/Sources/__tests__/SourceForm.test.tsx`

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Sources/SourceForm.tsx apps/packages/ui/src/routes/option-sources-new.tsx apps/packages/ui/src/components/Option/Sources/__tests__/SourceForm.test.tsx
git commit -m "feat: add ingestion source create form"
```

## Stage 3: Detail Route, Admin Mirror, and App Wiring
**Goal:** Build the dedicated detail page, item management, route wrappers, and app mounts.
**Success Criteria:** `/sources/:sourceId` and `/admin/sources` render shared UI, manual sync and archive upload work, detached items can be reattached, and WebUI page shims resolve to the shared routes.
**Tests:** `bunx vitest run apps/packages/ui/src/components/Option/Sources/__tests__/SourceDetailPage.test.tsx apps/packages/ui/src/routes/__tests__/sources-route-registry.test.tsx apps/tldw-frontend/__tests__/pages/sources-route.test.tsx`
**Status:** Not Started

### Task 7: Build the source detail page and tracked-items table

**Files:**
- Create: `apps/packages/ui/src/components/Option/Sources/SourceDetailPage.tsx`
- Create: `apps/packages/ui/src/components/Option/Sources/SourceItemsTable.tsx`
- Modify: `apps/packages/ui/src/components/Option/Sources/SourceStatusPanels.tsx`
- Create: `apps/packages/ui/src/routes/option-sources-detail.tsx`
- Test: `apps/packages/ui/src/components/Option/Sources/__tests__/SourceDetailPage.test.tsx`

**Step 1: Write the failing test**

```tsx
it("shows detached items and allows reattach without hiding degraded state", async () => {
  renderWithQueryClient(<SourceDetailPage sourceId="42" />)

  expect(await screen.findByText("conflict_detached")).toBeInTheDocument()
  await user.click(screen.getByRole("button", { name: "Reattach" }))
  expect(mockReattachMutation).toHaveBeenCalledWith({ sourceId: "42", itemId: "501" })
})
```

Add detail-page coverage for:
- sync button
- archive upload button only for `archive_snapshot`
- last error banner
- immutable field display after first successful sync
- item filtering for detached/degraded statuses

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/components/Option/Sources/__tests__/SourceDetailPage.test.tsx`

Expected: FAIL because the detail page and items table do not exist.

**Step 3: Write minimal implementation**

```tsx
export const SourceDetailPage = ({ sourceId, mode = "user" }: Props) => {
  const detailQuery = useIngestionSourceDetailQuery(sourceId)
  const itemsQuery = useIngestionSourceItemsQuery(sourceId, filters)

  return (
    <PageShell className="py-6" maxWidthClassName="max-w-7xl">
      <SourceStatusPanels source={detailQuery.data} mode={mode} />
      <SourceForm mode="edit" source={detailQuery.data} />
      <SourceItemsTable sourceId={sourceId} items={itemsQuery.data?.items ?? []} />
    </PageShell>
  )
}
```

Keep mutations item-scoped where possible so a reattach or sync action does not remount the whole page.

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/components/Option/Sources/__tests__/SourceDetailPage.test.tsx`

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Sources/SourceDetailPage.tsx apps/packages/ui/src/components/Option/Sources/SourceItemsTable.tsx apps/packages/ui/src/components/Option/Sources/SourceStatusPanels.tsx apps/packages/ui/src/routes/option-sources-detail.tsx apps/packages/ui/src/components/Option/Sources/__tests__/SourceDetailPage.test.tsx
git commit -m "feat: add ingestion source detail page"
```

### Task 8: Register shared routes and mount them in WebUI/admin

**Files:**
- Create: `apps/packages/ui/src/routes/option-sources.tsx`
- Create: `apps/packages/ui/src/routes/option-admin-sources.tsx`
- Modify: `apps/packages/ui/src/routes/route-registry.tsx`
- Modify: `apps/packages/ui/src/routes/route-paths.ts`
- Create: `apps/tldw-frontend/pages/sources.tsx`
- Create: `apps/tldw-frontend/pages/sources/new.tsx`
- Create: `apps/tldw-frontend/pages/sources/[sourceId].tsx`
- Create: `apps/tldw-frontend/pages/admin/sources.tsx`
- Test: `apps/packages/ui/src/routes/__tests__/sources-route-registry.test.tsx`
- Test: `apps/tldw-frontend/__tests__/pages/sources-route.test.tsx`

**Step 1: Write the failing test**

```tsx
it("mounts shared Sources routes for user and admin pages", async () => {
  expect(ROUTE_DEFINITIONS.some((route) => route.path === "/sources")).toBe(true)
  expect(ROUTE_DEFINITIONS.some((route) => route.path === "/sources/new")).toBe(true)
  expect(ROUTE_DEFINITIONS.some((route) => route.path === "/sources/:sourceId")).toBe(true)
  expect(ROUTE_DEFINITIONS.some((route) => route.path === "/admin/sources")).toBe(true)
})
```

Add a Next.js shim smoke test that `pages/sources.tsx` dynamically imports `@/routes/option-sources`.

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/routes/__tests__/sources-route-registry.test.tsx apps/tldw-frontend/__tests__/pages/sources-route.test.tsx`

Expected: FAIL because the new routes and page shims do not exist.

**Step 3: Write minimal implementation**

Add route wrappers following the existing `OptionLayout` and `RouteErrorBoundary` pattern:

```tsx
export default function OptionSources() {
  return (
    <RouteErrorBoundary routeId="sources" routeLabel="Sources">
      <OptionLayout>
        <SourcesWorkspacePage mode="user" />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}
```

Register in `route-registry.tsx`:

```tsx
{ kind: "options", path: "/sources", element: <OptionSources />, nav: { group: "workspace", labelToken: "option:header.sources", icon: Layers, order: 9.5, beta: true } }
{ kind: "options", path: "/sources/new", element: <OptionSourcesNew /> }
{ kind: "options", path: "/sources/:sourceId", element: <OptionSourcesDetail /> }
{ kind: "options", path: "/admin/sources", element: <OptionAdminSources /> }
```

Mount the shared routes in Next.js with `dynamic(() => import("@/routes/..."), { ssr: false })`.

In v1, keep the admin route as a list/workspace entry point only. `New source` and `Open detail` actions from `/admin/sources` should navigate into `/sources/new` and `/sources/:sourceId` instead of inventing unsupported admin detail routes.

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/routes/__tests__/sources-route-registry.test.tsx apps/tldw-frontend/__tests__/pages/sources-route.test.tsx`

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/option-sources.tsx apps/packages/ui/src/routes/option-admin-sources.tsx apps/packages/ui/src/routes/route-registry.tsx apps/packages/ui/src/routes/route-paths.ts apps/tldw-frontend/pages/sources.tsx apps/tldw-frontend/pages/sources/new.tsx apps/tldw-frontend/pages/sources/[sourceId].tsx apps/tldw-frontend/pages/admin/sources.tsx apps/packages/ui/src/routes/__tests__/sources-route-registry.test.tsx apps/tldw-frontend/__tests__/pages/sources-route.test.tsx
git commit -m "feat: wire ingestion source routes across web and admin"
```

## Stage 4: Extension Validation and Finish Pass
**Goal:** Prove the shared routes work in the extension options app and close the branch with verification coverage.
**Success Criteria:** Extension options can navigate to the new full-page workspace, mocked source data renders, and the touched frontend scope has passing tests.
**Tests:** `bunx vitest run apps/packages/ui/src/components/Option/Sources/__tests__/*.test.tsx apps/packages/ui/src/routes/__tests__/sources-route-registry.test.tsx apps/tldw-frontend/__tests__/pages/sources-route.test.tsx && bunx playwright test apps/extension/tests/e2e/ingestion-sources.spec.ts --reporter=line`
**Status:** Not Started

### Task 9: Add extension full-page smoke coverage and final verification

**Files:**
- Create: `apps/extension/tests/e2e/ingestion-sources.spec.ts`
- Modify: `apps/extension/tests/e2e/utils/real-server.ts` only if the new spec needs shared helper expansion
- Optional Test Fixture: `apps/packages/ui/src/components/Option/Sources/__tests__/test-utils.tsx`

**Step 1: Write the failing test**

```ts
test("opens the Sources workspace in extension options and shows source actions", async () => {
  const { page } = await launchWithExtensionOrSkip(test, extPath, seededConfig)
  await page.goto(`${optionsUrl}#/sources`)
  await expect(page.getByRole("heading", { name: "Sources" })).toBeVisible()
  await expect(page.getByRole("button", { name: "New source" })).toBeVisible()
})
```

Extend the mocked background handler to cover:
- `GET /api/v1/ingestion-sources`
- `POST /api/v1/ingestion-sources/:id/sync`
- `GET /api/v1/ingestion-sources/:id`
- `GET /api/v1/ingestion-sources/:id/items`
- capability detection support, either via `/openapi.json`/docs responses or by relying on the updated fallback spec path list

**Step 2: Run test to verify it fails**

Run: `bunx playwright test apps/extension/tests/e2e/ingestion-sources.spec.ts --reporter=line`

Expected: FAIL because the route does not render or the mocks are incomplete.

**Step 3: Write minimal implementation**

Follow the existing `collections.spec.ts` pattern:
- use full-page options routing, not the sidepanel
- seed extension config for offline-allowed, first-run-complete mode
- inject mocked backend handlers with `context.addInitScript`
- assert the list page and detail navigation both render

Keep the spec small: one route smoke plus one quick action path is enough for v1.

**Step 4: Run full verification**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/services/__tests__/server-capabilities.test.ts \
  apps/packages/ui/src/services/__tests__/tldw-api-client.ingestion-sources.test.ts \
  apps/packages/ui/src/hooks/__tests__/use-ingestion-sources.test.ts \
  apps/packages/ui/src/i18n/__tests__/sources-locale.test.ts \
  apps/packages/ui/src/components/Option/Sources/__tests__/SourcesWorkspacePage.test.tsx \
  apps/packages/ui/src/components/Option/Sources/__tests__/SourceForm.test.tsx \
  apps/packages/ui/src/components/Option/Sources/__tests__/SourceDetailPage.test.tsx \
  apps/packages/ui/src/routes/__tests__/sources-route-registry.test.tsx \
  apps/tldw-frontend/__tests__/pages/sources-route.test.tsx

bunx playwright test apps/extension/tests/e2e/ingestion-sources.spec.ts --reporter=line
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/extension/tests/e2e/ingestion-sources.spec.ts apps/packages/ui/src/services/__tests__/tldw-api-client.ingestion-sources.test.ts apps/packages/ui/src/hooks/__tests__/use-ingestion-sources.test.ts apps/packages/ui/src/components/Option/Sources/__tests__/SourcesWorkspacePage.test.tsx apps/packages/ui/src/components/Option/Sources/__tests__/SourceForm.test.tsx apps/packages/ui/src/components/Option/Sources/__tests__/SourceDetailPage.test.tsx apps/packages/ui/src/routes/__tests__/sources-route-registry.test.tsx apps/tldw-frontend/__tests__/pages/sources-route.test.tsx
git commit -m "test: cover ingestion source webui and extension routes"
```

## Notes for the Implementer

- Reuse shared full-page route patterns already present in:
  - `apps/packages/ui/src/routes/option-collections.tsx`
  - `apps/packages/ui/src/routes/option-admin-server.tsx`
  - `apps/tldw-frontend/pages/collections.tsx`
- Keep the extension implementation route-driven through `apps/packages/ui/src/entries/options/main.tsx`; do not build a separate extension-only page tree.
- Treat `/admin/sources` as a route alias with admin chrome only. Do not introduce fake cross-user selectors before the backend exists.
- Use `useServerCapabilities()` to gate the route and reuse the project’s normal unavailable-state UX when `hasIngestionSources` is false.
- Use `useTldwApiClient()` as the shared client access point inside hooks and components; do not create ad-hoc client instances in the workspace.
- Be explicit that `local_directory` means a server-host filesystem path. Do not imply the browser or extension can pick a local machine directory for the server.
- Keep the create/edit form strict about backend immutability rules. Changing `sink_type`, `source_type`, or source identity after first successful sync should be a display-only field, not an editable control.
- Do not add delete controls unless a backend delete endpoint is implemented first. The approved v1 UI scope is the current backend-supported management surface, not full CRUD.
- Prefer fallback copy in components plus `sources.json` entries, but do not delay shipping on translating every locale file. English registration is enough for this slice because `fallbackLng` is already `en`.
- Before finishing execution, use `superpowers:verification-before-completion` and run any touched-scope verification before claiming success.
