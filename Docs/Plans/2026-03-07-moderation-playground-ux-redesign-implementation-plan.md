# Moderation Playground UX Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Decompose the 1,918-line monolithic `ModerationPlayground` into a tabbed shell with 5 focused panels, shared hooks, custom Tailwind components, and full backend feature parity.

**Architecture:** Extract all state management into custom hooks (`useModerationContext`, `useModerationSettings`, `useBlocklist`, `useUserOverrides`, `useModerationTest`). Build a shell component with sticky context bar and custom Tailwind tab bar. Each tab is a self-contained panel component (<300 lines) that consumes hooks. Replace antd Card/Table/Switch/Tags with lightweight Tailwind equivalents where possible; keep antd Modal, Tooltip, Select(tags mode), message.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, antd (selective), react-query, vitest, React Testing Library, Lucide icons, react-i18next

**Design doc:** `docs/plans/2026-03-07-moderation-playground-ux-redesign.md`

---

## File Map

All paths relative to `apps/packages/ui/src/components/Option/ModerationPlayground/`.

```
ModerationPlayground/
  index.tsx                          # Rewire: imports shell, re-exports
  ModerationPlaygroundShell.tsx      # NEW: hero + context bar + tab router
  ModerationContextBar.tsx           # NEW: sticky bar + quick test
  PolicySettingsPanel.tsx            # NEW: tab 1
  BlocklistStudioPanel.tsx           # NEW: tab 2
  UserOverridesPanel.tsx             # NEW: tab 3
  TestSandboxPanel.tsx               # NEW: tab 4
  AdvancedPanel.tsx                  # NEW: tab 5
  moderation-utils.ts                # NEW: extracted pure functions
  hooks/
    useModerationContext.ts          # NEW: scope + userId shared state
    useModerationSettings.ts         # NEW: settings query + mutations
    useBlocklist.ts                  # NEW: blocklist CRUD + lint
    useUserOverrides.ts              # NEW: override CRUD + bulk ops
    useModerationTest.ts             # NEW: test execution + history
  components/
    CategoryPicker.tsx               # NEW: grid with taxonomy metadata
    BlocklistSyntaxRef.tsx           # NEW: collapsible syntax reference
    PolicyStatusBadges.tsx           # NEW: reusable status badge row
    QuickTestInline.tsx              # NEW: context bar mini-tester
  __tests__/
    moderation-utils.test.ts                       # NEW
    useModerationContext.test.ts                    # NEW
    useModerationSettings.test.ts                   # NEW
    useBlocklist.test.ts                            # NEW
    useUserOverrides.test.ts                        # NEW
    useModerationTest.test.ts                       # NEW
    ModerationPlaygroundShell.test.tsx              # NEW
    PolicySettingsPanel.test.tsx                    # NEW
    BlocklistStudioPanel.test.tsx                   # NEW
    UserOverridesPanel.test.tsx                     # NEW
    TestSandboxPanel.test.tsx                       # NEW
    AdvancedPanel.test.tsx                          # NEW
    ModerationPlayground.progressive-disclosure.test.tsx  # UPDATE
    ModerationPlayground.quick-lists.test.tsx             # UPDATE
```

---

## Task 1: Extract Utility Functions

**Files:**
- Create: `ModerationPlayground/moderation-utils.ts`
- Create: `ModerationPlayground/__tests__/moderation-utils.test.ts`
- Modify: `ModerationPlayground/index.tsx` (remove utilities, import from new file)

These pure functions currently live at the top of `index.tsx` (lines 81–267). Move them to a shared utils module so all panels and hooks can import them.

**Step 1: Write failing tests for utilities**

Create `__tests__/moderation-utils.test.ts`:

```typescript
import { describe, expect, it } from "vitest"
import {
  normalizeCategories,
  formatJson,
  normalizeRuleIsRegex,
  formatRulePhase,
  normalizeOverrideRules,
  sortOverrideRules,
  areRulesEquivalent,
  createRuleId,
  buildOverridePayload,
  normalizeSettingsDraft,
  normalizeOverrideForCompare,
  isEqualJson,
  getErrorStatus,
  CATEGORY_SUGGESTIONS,
  ACTION_OPTIONS,
  PRESET_PROFILES
} from "../moderation-utils"

describe("normalizeCategories", () => {
  it("converts array of strings", () => {
    expect(normalizeCategories(["pii", " profanity ", ""])).toEqual(["pii", "profanity"])
  })
  it("splits comma-separated string", () => {
    expect(normalizeCategories("pii,profanity")).toEqual(["pii", "profanity"])
  })
  it("returns empty for null/undefined", () => {
    expect(normalizeCategories(null)).toEqual([])
    expect(normalizeCategories(undefined)).toEqual([])
  })
})

describe("normalizeRuleIsRegex", () => {
  it("returns boolean directly", () => {
    expect(normalizeRuleIsRegex(true)).toBe(true)
    expect(normalizeRuleIsRegex(false)).toBe(false)
  })
  it("returns false for null/undefined", () => {
    expect(normalizeRuleIsRegex(null)).toBe(false)
    expect(normalizeRuleIsRegex(undefined)).toBe(false)
  })
  it("returns null for non-boolean truthy", () => {
    expect(normalizeRuleIsRegex("yes")).toBeNull()
  })
})

describe("formatRulePhase", () => {
  it("formats both", () => {
    expect(formatRulePhase("both")).toBe("Both phases")
  })
  it("formats input", () => {
    expect(formatRulePhase("input")).toBe("Input phase")
  })
  it("formats output", () => {
    expect(formatRulePhase("output")).toBe("Output phase")
  })
})

describe("normalizeOverrideRules", () => {
  it("filters invalid entries", () => {
    const rules = normalizeOverrideRules([
      { id: "r1", pattern: "test", is_regex: false, action: "block", phase: "both" },
      { id: "", pattern: "test", is_regex: false, action: "block", phase: "both" },
      null,
      "garbage"
    ])
    expect(rules).toHaveLength(1)
    expect(rules[0].id).toBe("r1")
  })
  it("normalizes phase to both for unknown values", () => {
    const rules = normalizeOverrideRules([
      { id: "r1", pattern: "test", is_regex: false, action: "block", phase: "unknown" }
    ])
    expect(rules[0].phase).toBe("both")
  })
})

describe("sortOverrideRules", () => {
  it("sorts by id", () => {
    const sorted = sortOverrideRules([
      { id: "b", pattern: "x", is_regex: false, action: "block", phase: "both" },
      { id: "a", pattern: "y", is_regex: false, action: "warn", phase: "both" }
    ])
    expect(sorted[0].id).toBe("a")
    expect(sorted[1].id).toBe("b")
  })
})

describe("areRulesEquivalent", () => {
  it("matches ignoring id and case", () => {
    const a = { id: "1", pattern: "Test", is_regex: false, action: "block" as const, phase: "both" as const }
    const b = { id: "2", pattern: "test", is_regex: false, action: "block" as const, phase: "both" as const }
    expect(areRulesEquivalent(a, b)).toBe(true)
  })
  it("differs on action", () => {
    const a = { id: "1", pattern: "test", is_regex: false, action: "block" as const, phase: "both" as const }
    const b = { id: "2", pattern: "test", is_regex: false, action: "warn" as const, phase: "both" as const }
    expect(areRulesEquivalent(a, b)).toBe(false)
  })
})

describe("createRuleId", () => {
  it("returns a non-empty string", () => {
    expect(createRuleId()).toBeTruthy()
  })
  it("returns unique ids", () => {
    const ids = new Set(Array.from({ length: 10 }, createRuleId))
    expect(ids.size).toBe(10)
  })
})

describe("buildOverridePayload", () => {
  it("omits undefined fields", () => {
    const payload = buildOverridePayload({ enabled: true })
    expect(payload).toEqual({ enabled: true })
    expect(payload).not.toHaveProperty("input_action")
  })
  it("normalizes categories", () => {
    const payload = buildOverridePayload({ categories_enabled: "pii,violence" })
    expect(payload.categories_enabled).toEqual(["pii", "violence"])
  })
})

describe("isEqualJson", () => {
  it("compares equal objects", () => {
    expect(isEqualJson({ a: 1 }, { a: 1 })).toBe(true)
  })
  it("detects different objects", () => {
    expect(isEqualJson({ a: 1 }, { a: 2 })).toBe(false)
  })
})

describe("getErrorStatus", () => {
  it("extracts status from error object", () => {
    expect(getErrorStatus({ status: 403 })).toBe(403)
  })
  it("extracts status from nested response", () => {
    expect(getErrorStatus({ response: { status: 401 } })).toBe(401)
  })
  it("returns null for non-objects", () => {
    expect(getErrorStatus("string")).toBeNull()
    expect(getErrorStatus(null)).toBeNull()
  })
})

describe("constants", () => {
  it("CATEGORY_SUGGESTIONS includes all backend categories", () => {
    const values = CATEGORY_SUGGESTIONS.map((s) => s.value)
    expect(values).toContain("violence")
    expect(values).toContain("self_harm")
    expect(values).toContain("profanity")
    expect(values).toContain("pii")
    expect(values).toContain("drugs_alcohol")
    expect(values).toContain("sexual_content")
    expect(values).toContain("hate_speech")
    expect(values).toContain("gambling")
  })
  it("PRESET_PROFILES has strict/balanced/monitor", () => {
    expect(PRESET_PROFILES).toHaveProperty("strict")
    expect(PRESET_PROFILES).toHaveProperty("balanced")
    expect(PRESET_PROFILES).toHaveProperty("monitor")
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd apps && npx vitest run packages/ui/src/components/Option/ModerationPlayground/__tests__/moderation-utils.test.ts`
Expected: FAIL — module not found

**Step 3: Create `moderation-utils.ts`**

Move these functions from `index.tsx` lines 81–267 into `moderation-utils.ts`:
- `normalizeCategories`
- `formatJson`
- `normalizeRuleIsRegex`
- `formatRulePhase`
- `normalizeOverrideRules`
- `sortOverrideRules`
- `areRulesEquivalent`
- `createRuleId`
- `buildOverridePayload`
- `normalizeSettingsDraft` (plus its helper `stableSort`)
- `normalizeOverrideForCompare`
- `isEqualJson`
- `getErrorStatus`
- `ONBOARDING_KEY` constant
- `CATEGORY_SUGGESTIONS` — **expanded** to include all 8 backend categories plus sub-categories:

```typescript
export const CATEGORY_SUGGESTIONS = [
  { value: "violence", label: "Violence", description: "Kill, murder, weapon, assault, bomb", severity: "critical" },
  { value: "self_harm", label: "Self-Harm", description: "Suicide, self-harm, cutting, overdose", severity: "critical" },
  { value: "sexual_content", label: "Sexual Content", description: "Sex, porn, nude, erotic, nsfw", severity: "high" },
  { value: "hate_speech", label: "Hate Speech", description: "Racist, sexist, homophobic, bigot", severity: "high" },
  { value: "pii", label: "PII (Personal Info)", description: "SSN, credit cards, phone numbers", severity: "high" },
  { value: "pii_email", label: "Email Addresses", description: "Email address patterns", severity: "medium" },
  { value: "pii_phone", label: "Phone Numbers", description: "US phone number patterns", severity: "medium" },
  { value: "profanity", label: "Profanity", description: "Damn, hell, crap", severity: "low" },
  { value: "drugs_alcohol", label: "Drugs & Alcohol", description: "Marijuana, cocaine, alcohol, drunk", severity: "medium" },
  { value: "gambling", label: "Gambling", description: "Casino, poker, slot machine, lottery", severity: "medium" },
  { value: "confidential", label: "Confidential", description: "Custom confidential content rules", severity: "high" }
]
```

- `ACTION_OPTIONS` — unchanged
- `PRESET_PROFILES` — renamed from `presetProfiles`, unchanged content

Also export a new type used by hooks:

```typescript
export type ModerationScope = "server" | "user"

export interface SettingsDraft {
  piiEnabled: boolean
  categoriesEnabled: string[]
  persist: boolean
}
```

**Step 4: Run tests to verify they pass**

Run: `cd apps && npx vitest run packages/ui/src/components/Option/ModerationPlayground/__tests__/moderation-utils.test.ts`
Expected: PASS

**Step 5: Update `index.tsx` to import from `moderation-utils.ts`**

Replace all inline utility function definitions in `index.tsx` with imports from `./moderation-utils`. Do NOT change any behavior yet — just move the functions. The component should still render identically.

**Step 6: Run existing tests to verify no regression**

Run: `cd apps && npx vitest run packages/ui/src/components/Option/ModerationPlayground/__tests__/`
Expected: All existing tests PASS

**Step 7: Commit**

```bash
git add apps/packages/ui/src/components/Option/ModerationPlayground/moderation-utils.ts \
       apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/moderation-utils.test.ts \
       apps/packages/ui/src/components/Option/ModerationPlayground/index.tsx
git commit -m "refactor(moderation): extract utility functions to moderation-utils.ts"
```

---

## Task 2: Extract Shared Hooks

**Files:**
- Create: `ModerationPlayground/hooks/useModerationContext.ts`
- Create: `ModerationPlayground/hooks/useModerationSettings.ts`
- Create: `ModerationPlayground/hooks/useBlocklist.ts`
- Create: `ModerationPlayground/hooks/useUserOverrides.ts`
- Create: `ModerationPlayground/hooks/useModerationTest.ts`
- Create: `ModerationPlayground/__tests__/useModerationContext.test.ts`
- Create: `ModerationPlayground/__tests__/useModerationSettings.test.ts`
- Create: `ModerationPlayground/__tests__/useBlocklist.test.ts`
- Create: `ModerationPlayground/__tests__/useUserOverrides.test.ts`
- Create: `ModerationPlayground/__tests__/useModerationTest.test.ts`

Extract state management from `index.tsx` into 5 custom hooks. Each hook encapsulates a domain concern.

### Step 1: Write failing test for `useModerationContext`

Create `__tests__/useModerationContext.test.ts`:

```typescript
import { act, renderHook } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { useModerationContext } from "../hooks/useModerationContext"

describe("useModerationContext", () => {
  it("defaults to server scope with no user", () => {
    const { result } = renderHook(() => useModerationContext())
    expect(result.current.scope).toBe("server")
    expect(result.current.activeUserId).toBeNull()
  })

  it("sets scope to user", () => {
    const { result } = renderHook(() => useModerationContext())
    act(() => result.current.setScope("user"))
    expect(result.current.scope).toBe("user")
  })

  it("clears activeUserId when switching to server scope", () => {
    const { result } = renderHook(() => useModerationContext())
    act(() => {
      result.current.setScope("user")
      result.current.setActiveUserId("alice")
    })
    expect(result.current.activeUserId).toBe("alice")
    act(() => result.current.setScope("server"))
    expect(result.current.activeUserId).toBeNull()
  })

  it("tracks userIdDraft separately from activeUserId", () => {
    const { result } = renderHook(() => useModerationContext())
    act(() => result.current.setUserIdDraft("bob"))
    expect(result.current.userIdDraft).toBe("bob")
    expect(result.current.activeUserId).toBeNull()
  })

  it("loadUser trims and sets activeUserId", () => {
    const { result } = renderHook(() => useModerationContext())
    act(() => {
      result.current.setScope("user")
      result.current.setUserIdDraft("  alice  ")
      result.current.loadUser()
    })
    expect(result.current.activeUserId).toBe("alice")
  })

  it("loadUser does nothing with empty draft", () => {
    const { result } = renderHook(() => useModerationContext())
    act(() => {
      result.current.setScope("user")
      result.current.loadUser()
    })
    expect(result.current.activeUserId).toBeNull()
  })

  it("clearUser resets activeUserId and userIdDraft", () => {
    const { result } = renderHook(() => useModerationContext())
    act(() => {
      result.current.setScope("user")
      result.current.setUserIdDraft("alice")
      result.current.setActiveUserId("alice")
    })
    act(() => result.current.clearUser())
    expect(result.current.activeUserId).toBeNull()
    expect(result.current.userIdDraft).toBe("")
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps && npx vitest run packages/ui/src/components/Option/ModerationPlayground/__tests__/useModerationContext.test.ts`
Expected: FAIL — module not found

**Step 3: Implement `useModerationContext`**

Create `hooks/useModerationContext.ts`:

```typescript
import React from "react"
import type { ModerationScope } from "../moderation-utils"

export interface ModerationContextState {
  scope: ModerationScope
  setScope: (scope: ModerationScope) => void
  userIdDraft: string
  setUserIdDraft: (value: string) => void
  activeUserId: string | null
  setActiveUserId: (value: string | null) => void
  loadUser: () => void
  clearUser: () => void
}

export function useModerationContext(): ModerationContextState {
  const [scope, setScopeRaw] = React.useState<ModerationScope>("server")
  const [userIdDraft, setUserIdDraft] = React.useState("")
  const [activeUserId, setActiveUserId] = React.useState<string | null>(null)

  const setScope = React.useCallback((next: ModerationScope) => {
    setScopeRaw(next)
    if (next === "server") {
      setActiveUserId(null)
    }
  }, [])

  const loadUser = React.useCallback(() => {
    const trimmed = userIdDraft.trim()
    if (trimmed) {
      setActiveUserId(trimmed)
    }
  }, [userIdDraft])

  const clearUser = React.useCallback(() => {
    setActiveUserId(null)
    setUserIdDraft("")
  }, [])

  return {
    scope,
    setScope,
    userIdDraft,
    setUserIdDraft,
    activeUserId,
    setActiveUserId,
    loadUser,
    clearUser
  }
}
```

**Step 4: Run test to verify it passes**

Run: `cd apps && npx vitest run packages/ui/src/components/Option/ModerationPlayground/__tests__/useModerationContext.test.ts`
Expected: PASS

**Step 5: Write failing test for `useModerationSettings`**

Create `__tests__/useModerationSettings.test.ts`:

```typescript
import { renderHook, act, waitFor } from "@testing-library/react"
import { describe, expect, it, vi, beforeEach } from "vitest"

const useQueryMock = vi.fn()
vi.mock("@tanstack/react-query", () => ({
  useQuery: (opts: unknown) => useQueryMock(opts)
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

vi.mock("@/services/moderation", () => ({
  getModerationSettings: vi.fn(),
  updateModerationSettings: vi.fn(),
  reloadModeration: vi.fn()
}))

import { useModerationSettings } from "../hooks/useModerationSettings"
import * as moderationService from "@/services/moderation"

describe("useModerationSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useQueryMock.mockReturnValue({
      data: { pii_enabled: true, categories_enabled: ["pii"], effective: { pii_enabled: true, categories_enabled: ["pii"] } },
      isFetching: false,
      error: null,
      refetch: vi.fn()
    })
  })

  it("exposes settings draft with initial values from query", () => {
    const { result } = renderHook(() => useModerationSettings())
    expect(result.current.draft).toBeDefined()
    expect(result.current.draft.piiEnabled).toBe(true)
  })

  it("tracks dirty state", () => {
    const { result } = renderHook(() => useModerationSettings())
    expect(result.current.isDirty).toBe(false)
    act(() => result.current.updateDraft({ piiEnabled: false }))
    expect(result.current.isDirty).toBe(true)
  })

  it("reset restores baseline", () => {
    const { result } = renderHook(() => useModerationSettings())
    act(() => result.current.updateDraft({ piiEnabled: false }))
    expect(result.current.isDirty).toBe(true)
    act(() => result.current.reset())
    expect(result.current.isDirty).toBe(false)
  })
})
```

**Step 6: Implement `useModerationSettings`**

Create `hooks/useModerationSettings.ts`:

```typescript
import React from "react"
import { useQuery } from "@tanstack/react-query"
import { useServerOnline } from "@/hooks/useServerOnline"
import {
  getModerationSettings,
  updateModerationSettings,
  reloadModeration,
  getEffectivePolicy,
  type ModerationSettingsResponse
} from "@/services/moderation"
import {
  normalizeCategories,
  normalizeSettingsDraft,
  isEqualJson,
  type SettingsDraft
} from "../moderation-utils"

export function useModerationSettings(activeUserId: string | null = null) {
  const online = useServerOnline()

  const settingsQuery = useQuery<ModerationSettingsResponse>({
    queryKey: ["moderation-settings"],
    queryFn: getModerationSettings,
    enabled: online
  })

  const policyQuery = useQuery<Record<string, any>>({
    queryKey: ["moderation-policy", activeUserId ?? "server"],
    queryFn: () => getEffectivePolicy(activeUserId || undefined),
    enabled: online
  })

  const [draft, setDraft] = React.useState<SettingsDraft>({
    piiEnabled: false,
    categoriesEnabled: [],
    persist: false
  })
  const [baseline, setBaseline] = React.useState<SettingsDraft | null>(null)

  React.useEffect(() => {
    if (!settingsQuery.data) return
    const data = settingsQuery.data
    const categories = data.categories_enabled ?? data.effective?.categories_enabled ?? []
    const piiEnabled =
      data.pii_enabled ??
      (typeof data.effective?.pii_enabled === "boolean" ? data.effective.pii_enabled : false)
    setDraft((prev) => ({ ...prev, piiEnabled, categoriesEnabled: categories || [] }))
    setBaseline((prev) => ({
      piiEnabled,
      categoriesEnabled: categories || [],
      persist: prev?.persist ?? false
    }))
  }, [settingsQuery.data])

  const normalizedDraft = normalizeSettingsDraft(draft)
  const normalizedBaseline = normalizeSettingsDraft(baseline ?? draft)
  const isDirty = baseline !== null && !isEqualJson(normalizedDraft, normalizedBaseline)

  const updateDraft = React.useCallback((partial: Partial<SettingsDraft>) => {
    setDraft((prev) => ({ ...prev, ...partial }))
  }, [])

  const reset = React.useCallback(() => {
    if (!baseline) return
    setDraft({ ...baseline })
  }, [baseline])

  const save = React.useCallback(async () => {
    const payload = {
      pii_enabled: draft.piiEnabled,
      categories_enabled: draft.categoriesEnabled,
      persist: draft.persist
    }
    await updateModerationSettings(payload)
    setBaseline(normalizedDraft)
    await settingsQuery.refetch()
    await policyQuery.refetch()
  }, [draft, normalizedDraft, settingsQuery, policyQuery])

  const reload = React.useCallback(async () => {
    await reloadModeration()
    await settingsQuery.refetch()
    await policyQuery.refetch()
  }, [settingsQuery, policyQuery])

  return {
    draft,
    updateDraft,
    isDirty,
    reset,
    save,
    reload,
    settingsQuery,
    policyQuery,
    policy: policyQuery.data || {},
    online
  }
}
```

**Step 7: Run settings tests**

Run: `cd apps && npx vitest run packages/ui/src/components/Option/ModerationPlayground/__tests__/useModerationSettings.test.ts`
Expected: PASS

**Step 8: Write failing test for `useBlocklist`**

Create `__tests__/useBlocklist.test.ts`:

```typescript
import { renderHook, act } from "@testing-library/react"
import { describe, expect, it, vi, beforeEach } from "vitest"
import * as moderationService from "@/services/moderation"

vi.mock("@/services/moderation", () => ({
  getBlocklist: vi.fn(),
  updateBlocklist: vi.fn(),
  getManagedBlocklist: vi.fn(),
  appendManagedBlocklist: vi.fn(),
  deleteManagedBlocklistItem: vi.fn(),
  lintBlocklist: vi.fn()
}))

import { useBlocklist } from "../hooks/useBlocklist"

describe("useBlocklist", () => {
  beforeEach(() => vi.clearAllMocks())

  it("starts with empty state", () => {
    const { result } = renderHook(() => useBlocklist())
    expect(result.current.rawText).toBe("")
    expect(result.current.managedItems).toEqual([])
    expect(result.current.managedVersion).toBe("")
    expect(result.current.loading).toBe(false)
  })

  it("loadRaw populates rawText", async () => {
    vi.mocked(moderationService.getBlocklist).mockResolvedValue(["badword", "/regex/"])
    const { result } = renderHook(() => useBlocklist())
    await act(() => result.current.loadRaw())
    expect(result.current.rawText).toBe("badword\n/regex/")
  })

  it("loadManaged populates items and version", async () => {
    vi.mocked(moderationService.getManagedBlocklist).mockResolvedValue({
      data: { version: "abc123", items: [{ id: 0, line: "test" }] },
      etag: "abc123"
    })
    const { result } = renderHook(() => useBlocklist())
    await act(() => result.current.loadManaged())
    expect(result.current.managedItems).toHaveLength(1)
    expect(result.current.managedVersion).toBe("abc123")
  })
})
```

**Step 9: Implement `useBlocklist`**

Create `hooks/useBlocklist.ts`:

```typescript
import React from "react"
import {
  getBlocklist,
  updateBlocklist,
  getManagedBlocklist,
  appendManagedBlocklist,
  deleteManagedBlocklistItem,
  lintBlocklist,
  type BlocklistManagedItem,
  type BlocklistLintResponse
} from "@/services/moderation"

export function useBlocklist() {
  const [rawText, setRawText] = React.useState("")
  const [rawLint, setRawLint] = React.useState<BlocklistLintResponse | null>(null)
  const [managedItems, setManagedItems] = React.useState<BlocklistManagedItem[]>([])
  const [managedVersion, setManagedVersion] = React.useState("")
  const [managedLine, setManagedLine] = React.useState("")
  const [managedLint, setManagedLint] = React.useState<BlocklistLintResponse | null>(null)
  const [loading, setLoading] = React.useState(false)

  const loadRaw = React.useCallback(async () => {
    setLoading(true)
    try {
      const lines = await getBlocklist()
      setRawText((lines || []).join("\n"))
      setRawLint(null)
    } finally {
      setLoading(false)
    }
  }, [])

  const saveRaw = React.useCallback(async () => {
    setLoading(true)
    try {
      const lines = rawText.split(/\r?\n/).map((l) => l.trimEnd())
      await updateBlocklist(lines)
    } finally {
      setLoading(false)
    }
  }, [rawText])

  const lintRaw = React.useCallback(async () => {
    setLoading(true)
    try {
      const lines = rawText.split(/\r?\n/)
      const lint = await lintBlocklist({ lines })
      setRawLint(lint)
      return lint
    } finally {
      setLoading(false)
    }
  }, [rawText])

  const loadManaged = React.useCallback(async () => {
    setLoading(true)
    try {
      const { data, etag } = await getManagedBlocklist()
      setManagedItems(data.items || [])
      setManagedVersion(data.version || etag || "")
    } finally {
      setLoading(false)
    }
  }, [])

  const appendManaged = React.useCallback(async (line: string) => {
    if (!managedVersion) throw new Error("Load managed blocklist first")
    setLoading(true)
    try {
      await appendManagedBlocklist(managedVersion, line)
      await loadManaged()
    } finally {
      setLoading(false)
    }
  }, [managedVersion, loadManaged])

  const deleteManaged = React.useCallback(async (itemId: number) => {
    if (!managedVersion) return
    setLoading(true)
    try {
      await deleteManagedBlocklistItem(managedVersion, itemId)
      await loadManaged()
    } finally {
      setLoading(false)
    }
  }, [managedVersion, loadManaged])

  const lintManagedLine = React.useCallback(async (line: string) => {
    setLoading(true)
    try {
      const lint = await lintBlocklist({ line })
      setManagedLint(lint)
      return lint
    } finally {
      setLoading(false)
    }
  }, [])

  return {
    rawText,
    setRawText,
    rawLint,
    loading,
    loadRaw,
    saveRaw,
    lintRaw,
    managedItems,
    managedVersion,
    managedLine,
    setManagedLine,
    managedLint,
    loadManaged,
    appendManaged,
    deleteManaged,
    lintManagedLine
  }
}
```

**Step 10: Run blocklist tests**

Run: `cd apps && npx vitest run packages/ui/src/components/Option/ModerationPlayground/__tests__/useBlocklist.test.ts`
Expected: PASS

**Step 11: Write failing test for `useUserOverrides`**

Create `__tests__/useUserOverrides.test.ts`:

```typescript
import { renderHook, act, waitFor } from "@testing-library/react"
import { describe, expect, it, vi, beforeEach } from "vitest"

const useQueryMock = vi.fn()
vi.mock("@tanstack/react-query", () => ({
  useQuery: (opts: unknown) => useQueryMock(opts)
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

vi.mock("@/services/moderation", () => ({
  getUserOverride: vi.fn(),
  setUserOverride: vi.fn(),
  deleteUserOverride: vi.fn(),
  listUserOverrides: vi.fn()
}))

import { useUserOverrides } from "../hooks/useUserOverrides"
import * as moderationService from "@/services/moderation"

describe("useUserOverrides", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useQueryMock.mockReturnValue({ data: null, isFetching: false, error: null, refetch: vi.fn() })
  })

  it("starts with empty override draft", () => {
    const { result } = renderHook(() => useUserOverrides(null))
    expect(result.current.draft).toEqual({})
    expect(result.current.loaded).toBe(false)
    expect(result.current.isDirty).toBe(false)
  })

  it("loads override when userId provided", async () => {
    vi.mocked(moderationService.getUserOverride).mockResolvedValue({
      exists: true,
      override: { enabled: true, input_action: "block" }
    })
    const { result } = renderHook(() => useUserOverrides("alice"))
    await waitFor(() => {
      expect(result.current.loaded).toBe(true)
    })
    expect(result.current.draft.enabled).toBe(true)
  })

  it("tracks dirty state on draft changes", async () => {
    vi.mocked(moderationService.getUserOverride).mockResolvedValue({
      exists: true,
      override: { enabled: true }
    })
    const { result } = renderHook(() => useUserOverrides("alice"))
    await waitFor(() => expect(result.current.loaded).toBe(true))
    act(() => result.current.updateDraft({ enabled: false }))
    expect(result.current.isDirty).toBe(true)
  })
})
```

**Step 12: Implement `useUserOverrides`**

Create `hooks/useUserOverrides.ts`:

```typescript
import React from "react"
import { useQuery } from "@tanstack/react-query"
import { useServerOnline } from "@/hooks/useServerOnline"
import {
  getUserOverride,
  setUserOverride,
  deleteUserOverride,
  listUserOverrides,
  type ModerationUserOverride,
  type ModerationOverrideRule
} from "@/services/moderation"
import {
  normalizeCategories,
  normalizeOverrideRules,
  buildOverridePayload,
  normalizeOverrideForCompare,
  isEqualJson,
  createRuleId,
  areRulesEquivalent
} from "../moderation-utils"

export function useUserOverrides(activeUserId: string | null) {
  const online = useServerOnline()

  const overridesQuery = useQuery({
    queryKey: ["moderation-overrides"],
    queryFn: listUserOverrides,
    enabled: online
  })

  const [draft, setDraft] = React.useState<ModerationUserOverride>({})
  const [baseline, setBaseline] = React.useState<ModerationUserOverride | null>(null)
  const [loaded, setLoaded] = React.useState(false)
  const [loading, setLoading] = React.useState(false)
  const [userIdError, setUserIdError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (!activeUserId) {
      setDraft({})
      setBaseline({})
      setLoaded(false)
      setUserIdError(null)
      return
    }
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setUserIdError(null)
      try {
        const result = await getUserOverride(activeUserId)
        if (cancelled) return
        if (!result.exists) {
          setDraft({})
          setLoaded(false)
          setUserIdError(`No override found for "${activeUserId}". You can create a new one.`)
          setBaseline({})
          return
        }
        const data = result.override ?? {}
        const normalized: ModerationUserOverride = {
          enabled: data.enabled,
          input_enabled: data.input_enabled,
          output_enabled: data.output_enabled,
          input_action: data.input_action,
          output_action: data.output_action,
          redact_replacement: data.redact_replacement,
          categories_enabled:
            data.categories_enabled === undefined ? undefined : normalizeCategories(data.categories_enabled),
          rules: normalizeOverrideRules(data.rules)
        }
        setDraft(normalized)
        setBaseline(normalized)
        setLoaded(true)
        setUserIdError(null)
      } catch {
        if (!cancelled) setUserIdError("Failed to load user override")
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => { cancelled = true }
  }, [activeUserId])

  const normalizedDraft = normalizeOverrideForCompare(draft)
  const normalizedBaseline = normalizeOverrideForCompare(baseline ?? {})
  const isDirty = Boolean(activeUserId) && !isEqualJson(normalizedDraft, normalizedBaseline)
  const rules = React.useMemo(() => normalizeOverrideRules(draft.rules), [draft.rules])
  const bannedRules = React.useMemo(() => rules.filter((r) => r.action === "block"), [rules])
  const notifyRules = React.useMemo(() => rules.filter((r) => r.action === "warn"), [rules])

  const updateDraft = React.useCallback((partial: Partial<ModerationUserOverride>) => {
    setDraft((prev) => ({ ...prev, ...partial }))
  }, [])

  const reset = React.useCallback(() => {
    if (!baseline) return
    setDraft({
      ...baseline,
      categories_enabled:
        baseline.categories_enabled !== undefined
          ? normalizeCategories(baseline.categories_enabled)
          : undefined,
      rules: normalizeOverrideRules(baseline.rules)
    })
  }, [baseline])

  const save = React.useCallback(async () => {
    if (!activeUserId) return
    const payload = buildOverridePayload(draft)
    await setUserOverride(activeUserId, payload)
    setLoaded(true)
    setBaseline(normalizedDraft)
    await overridesQuery.refetch()
  }, [activeUserId, draft, normalizedDraft, overridesQuery])

  const remove = React.useCallback(async (userId?: string) => {
    const targetId = userId || activeUserId
    if (!targetId) return
    await deleteUserOverride(targetId)
    if (targetId === activeUserId) {
      setDraft({})
      setLoaded(false)
      setUserIdError(null)
      setBaseline({})
    }
    await overridesQuery.refetch()
  }, [activeUserId, overridesQuery])

  const bulkDelete = React.useCallback(async (userIds: string[]) => {
    const failed: string[] = []
    for (const id of userIds) {
      try { await deleteUserOverride(id) } catch { failed.push(id) }
    }
    if (activeUserId && userIds.includes(activeUserId)) {
      setDraft({})
      setLoaded(false)
      setBaseline({})
    }
    await overridesQuery.refetch()
    return failed
  }, [activeUserId, overridesQuery])

  const addRule = React.useCallback((pattern: string, action: "block" | "warn", isRegex: boolean, phase: ModerationOverrideRule["phase"] = "both") => {
    const nextRule: ModerationOverrideRule = {
      id: createRuleId(),
      pattern,
      is_regex: isRegex,
      action,
      phase
    }
    if (rules.some((r) => areRulesEquivalent(r, nextRule))) {
      return false // duplicate
    }
    setDraft((prev) => ({
      ...prev,
      rules: [...normalizeOverrideRules(prev.rules), nextRule]
    }))
    return true
  }, [rules])

  const removeRule = React.useCallback((ruleId: string) => {
    setDraft((prev) => ({
      ...prev,
      rules: normalizeOverrideRules(prev.rules).filter((r) => r.id !== ruleId)
    }))
  }, [])

  const applyPreset = React.useCallback(async (presetPayload: ModerationUserOverride) => {
    if (!activeUserId) return
    const payload = buildOverridePayload(presetPayload)
    await setUserOverride(activeUserId, payload)
    const normalized: ModerationUserOverride = {
      ...payload,
      categories_enabled:
        payload.categories_enabled !== undefined
          ? normalizeCategories(payload.categories_enabled)
          : undefined
    }
    setDraft(normalized)
    setLoaded(true)
    setUserIdError(null)
    setBaseline(normalizeOverrideForCompare(normalized))
    await overridesQuery.refetch()
  }, [activeUserId, overridesQuery])

  return {
    draft,
    updateDraft,
    isDirty,
    loaded,
    loading,
    userIdError,
    rules,
    bannedRules,
    notifyRules,
    reset,
    save,
    remove,
    bulkDelete,
    addRule,
    removeRule,
    applyPreset,
    overridesQuery
  }
}
```

**Step 13: Run user overrides tests**

Run: `cd apps && npx vitest run packages/ui/src/components/Option/ModerationPlayground/__tests__/useUserOverrides.test.ts`
Expected: PASS

**Step 14: Write failing test for `useModerationTest`**

Create `__tests__/useModerationTest.test.ts`:

```typescript
import { renderHook, act } from "@testing-library/react"
import { describe, expect, it, vi, beforeEach } from "vitest"

vi.mock("@/services/moderation", () => ({
  testModeration: vi.fn()
}))

import { useModerationTest } from "../hooks/useModerationTest"
import * as moderationService from "@/services/moderation"

describe("useModerationTest", () => {
  beforeEach(() => vi.clearAllMocks())

  it("starts with empty state", () => {
    const { result } = renderHook(() => useModerationTest())
    expect(result.current.phase).toBe("input")
    expect(result.current.text).toBe("")
    expect(result.current.result).toBeNull()
    expect(result.current.history).toEqual([])
  })

  it("runs test and stores result", async () => {
    const mockResult = { flagged: true, action: "block", sample: "bad", redacted_text: null, effective: {}, category: "profanity" }
    vi.mocked(moderationService.testModeration).mockResolvedValue(mockResult as any)

    const { result } = renderHook(() => useModerationTest())
    act(() => result.current.setText("bad content"))
    await act(() => result.current.runTest())
    expect(result.current.result).toEqual(mockResult)
    expect(result.current.history).toHaveLength(1)
    expect(result.current.history[0].result).toEqual(mockResult)
  })

  it("prepends to history (most recent first)", async () => {
    vi.mocked(moderationService.testModeration)
      .mockResolvedValueOnce({ flagged: false, action: "pass", effective: {} } as any)
      .mockResolvedValueOnce({ flagged: true, action: "block", effective: {} } as any)

    const { result } = renderHook(() => useModerationTest())
    act(() => result.current.setText("first"))
    await act(() => result.current.runTest())
    act(() => result.current.setText("second"))
    await act(() => result.current.runTest())
    expect(result.current.history).toHaveLength(2)
    expect(result.current.history[0].text).toBe("second")
  })

  it("caps history at 20 entries", async () => {
    vi.mocked(moderationService.testModeration).mockResolvedValue({ flagged: false, action: "pass", effective: {} } as any)
    const { result } = renderHook(() => useModerationTest())
    for (let i = 0; i < 25; i++) {
      act(() => result.current.setText(`test-${i}`))
      await act(() => result.current.runTest())
    }
    expect(result.current.history).toHaveLength(20)
  })

  it("clearHistory empties the list", async () => {
    vi.mocked(moderationService.testModeration).mockResolvedValue({ flagged: false, action: "pass", effective: {} } as any)
    const { result } = renderHook(() => useModerationTest())
    act(() => result.current.setText("test"))
    await act(() => result.current.runTest())
    expect(result.current.history).toHaveLength(1)
    act(() => result.current.clearHistory())
    expect(result.current.history).toHaveLength(0)
  })

  it("loadFromHistory restores form state", async () => {
    vi.mocked(moderationService.testModeration).mockResolvedValue({ flagged: false, action: "pass", effective: {} } as any)
    const { result } = renderHook(() => useModerationTest())
    act(() => {
      result.current.setText("old text")
      result.current.setPhase("output")
      result.current.setUserId("alice")
    })
    await act(() => result.current.runTest())

    act(() => {
      result.current.setText("new text")
      result.current.setPhase("input")
    })
    act(() => result.current.loadFromHistory(0))
    expect(result.current.text).toBe("old text")
    expect(result.current.phase).toBe("output")
    expect(result.current.userId).toBe("alice")
  })
})
```

**Step 15: Implement `useModerationTest`**

Create `hooks/useModerationTest.ts`:

```typescript
import React from "react"
import { testModeration, type ModerationTestResponse } from "@/services/moderation"

const MAX_HISTORY = 20

export interface TestHistoryEntry {
  text: string
  phase: "input" | "output"
  userId: string
  result: ModerationTestResponse
  timestamp: number
}

export function useModerationTest() {
  const [phase, setPhase] = React.useState<"input" | "output">("input")
  const [text, setText] = React.useState("")
  const [userId, setUserId] = React.useState("")
  const [result, setResult] = React.useState<ModerationTestResponse | null>(null)
  const [history, setHistory] = React.useState<TestHistoryEntry[]>([])
  const [running, setRunning] = React.useState(false)

  const runTest = React.useCallback(async () => {
    if (!text.trim()) return
    setRunning(true)
    try {
      const payload = {
        user_id: userId.trim() || undefined,
        phase,
        text
      }
      const res = await testModeration(payload)
      setResult(res)
      setHistory((prev) => {
        const entry: TestHistoryEntry = {
          text,
          phase,
          userId: userId.trim(),
          result: res,
          timestamp: Date.now()
        }
        return [entry, ...prev].slice(0, MAX_HISTORY)
      })
      return res
    } finally {
      setRunning(false)
    }
  }, [text, phase, userId])

  const clearHistory = React.useCallback(() => {
    setHistory([])
  }, [])

  const loadFromHistory = React.useCallback((index: number) => {
    const entry = history[index]
    if (!entry) return
    setText(entry.text)
    setPhase(entry.phase)
    setUserId(entry.userId)
    setResult(entry.result)
  }, [history])

  return {
    phase,
    setPhase,
    text,
    setText,
    userId,
    setUserId,
    result,
    running,
    runTest,
    history,
    clearHistory,
    loadFromHistory
  }
}
```

**Step 16: Run all hook tests**

Run: `cd apps && npx vitest run packages/ui/src/components/Option/ModerationPlayground/__tests__/useModerationTest.test.ts`
Expected: PASS

**Step 17: Commit**

```bash
git add apps/packages/ui/src/components/Option/ModerationPlayground/hooks/ \
       apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/useModerationContext.test.ts \
       apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/useModerationSettings.test.ts \
       apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/useBlocklist.test.ts \
       apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/useUserOverrides.test.ts \
       apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/useModerationTest.test.ts
git commit -m "feat(moderation): extract shared hooks for settings, blocklist, overrides, test"
```

---

## Task 3: Create Shared Sub-Components

**Files:**
- Create: `ModerationPlayground/components/PolicyStatusBadges.tsx`
- Create: `ModerationPlayground/components/BlocklistSyntaxRef.tsx`
- Create: `ModerationPlayground/components/CategoryPicker.tsx`
- Create: `ModerationPlayground/components/QuickTestInline.tsx`

These are lightweight custom Tailwind components used across multiple tabs/context bar.

**Step 1: Create `PolicyStatusBadges.tsx`**

```typescript
import React from "react"

interface PolicyStatusBadgesProps {
  enabled?: boolean
  inputAction?: string
  outputAction?: string
  ruleCount?: number
  compact?: boolean
}

const badgeColor = (active: boolean) =>
  active
    ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
    : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"

const actionColor = (action: string) => {
  switch (action) {
    case "block": return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
    case "redact": return "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300"
    case "warn": return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300"
    default: return "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300"
  }
}

export const PolicyStatusBadges: React.FC<PolicyStatusBadgesProps> = ({
  enabled = false,
  inputAction = "pass",
  outputAction = "pass",
  ruleCount = 0,
  compact = false
}) => {
  const badgeClass = compact
    ? "inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium"
    : "inline-flex items-center px-2 py-1 rounded-md text-xs font-medium"

  return (
    <div className="flex flex-wrap gap-1.5">
      <span className={`${badgeClass} ${badgeColor(enabled)}`}>
        {enabled ? "Enabled" : "Disabled"}
      </span>
      <span className={`${badgeClass} ${actionColor(inputAction)}`}>
        Input: {inputAction}
      </span>
      <span className={`${badgeClass} ${actionColor(outputAction)}`}>
        Output: {outputAction}
      </span>
      <span className={`${badgeClass} bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300`}>
        {ruleCount} rules
      </span>
    </div>
  )
}
```

**Step 2: Create `BlocklistSyntaxRef.tsx`**

```typescript
import React from "react"

export const BlocklistSyntaxRef: React.FC = () => {
  const [open, setOpen] = React.useState(false)

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-medium text-text-muted hover:text-text hover:bg-surface/50 transition-colors"
        onClick={() => setOpen((prev) => !prev)}
      >
        <span>Blocklist Syntax Reference</span>
        <span className={`transition-transform ${open ? "rotate-90" : ""}`}>▶</span>
      </button>
      {open && (
        <div className="px-4 pb-4 border-t border-border">
          <table className="w-full text-sm mt-3">
            <thead>
              <tr className="text-left text-text-muted">
                <th className="pb-2 pr-4 font-medium">Syntax</th>
                <th className="pb-2 font-medium">Example</th>
              </tr>
            </thead>
            <tbody className="font-mono text-xs">
              <tr><td className="py-1 pr-4 text-text-muted">Literal</td><td><code>badword</code></td></tr>
              <tr><td className="py-1 pr-4 text-text-muted">Regex</td><td><code>{"/\\bnsfw\\b/"}</code> or <code>{"/pattern/imsx"}</code></td></tr>
              <tr><td className="py-1 pr-4 text-text-muted">Action</td><td><code>{"pattern -> block|redact|warn"}</code></td></tr>
              <tr><td className="py-1 pr-4 text-text-muted">Redact sub</td><td><code>{"/pat/ -> redact:[MASK]"}</code></td></tr>
              <tr><td className="py-1 pr-4 text-text-muted">Categories</td><td><code>{"/pat/ -> block #pii,confidential"}</code></td></tr>
              <tr><td className="py-1 pr-4 text-text-muted">Comment</td><td><code>{"# This is a comment"}</code></td></tr>
            </tbody>
          </table>
          <p className="mt-3 text-xs text-text-muted">
            Nested quantifiers and patterns {">"} 2000 chars are rejected to prevent ReDoS.
            Case-insensitive matching by default.
          </p>
        </div>
      )}
    </div>
  )
}
```

**Step 3: Create `CategoryPicker.tsx`**

```typescript
import React from "react"
import { Tooltip } from "antd"
import { CATEGORY_SUGGESTIONS } from "../moderation-utils"

interface CategoryPickerProps {
  value: string[]
  onChange: (categories: string[]) => void
  disabled?: boolean
}

const severityColor: Record<string, string> = {
  critical: "text-red-600 dark:text-red-400",
  high: "text-orange-600 dark:text-orange-400",
  medium: "text-yellow-600 dark:text-yellow-400",
  low: "text-gray-600 dark:text-gray-400"
}

export const CategoryPicker: React.FC<CategoryPickerProps> = ({ value, onChange, disabled }) => {
  const [customInput, setCustomInput] = React.useState("")
  const selected = new Set(value)

  const toggle = (cat: string) => {
    if (disabled) return
    const next = new Set(selected)
    if (next.has(cat)) next.delete(cat)
    else next.add(cat)
    onChange([...next])
  }

  const addCustom = () => {
    const trimmed = customInput.trim().toLowerCase()
    if (!trimmed || selected.has(trimmed)) return
    onChange([...value, trimmed])
    setCustomInput("")
  }

  return (
    <div>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {CATEGORY_SUGGESTIONS.map((cat) => {
          const isSelected = selected.has(cat.value)
          return (
            <Tooltip key={cat.value} title={cat.description}>
              <button
                type="button"
                disabled={disabled}
                onClick={() => toggle(cat.value)}
                className={`
                  text-left px-3 py-2 rounded-lg border text-sm transition-all
                  ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer hover:border-blue-400"}
                  ${isSelected
                    ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20 dark:border-blue-400"
                    : "border-border bg-surface/50"
                  }
                `}
              >
                <div className="flex items-center gap-2">
                  <span className={`w-3.5 h-3.5 rounded border flex items-center justify-center text-[10px] ${isSelected ? "bg-blue-500 border-blue-500 text-white" : "border-gray-300 dark:border-gray-600"}`}>
                    {isSelected ? "✓" : ""}
                  </span>
                  <span className="font-medium">{cat.label}</span>
                </div>
                <div className={`text-xs mt-0.5 ml-5.5 ${severityColor[cat.severity ?? "low"]}`}>
                  {cat.severity}
                </div>
              </button>
            </Tooltip>
          )
        })}
      </div>
      <div className="flex gap-2 mt-3">
        <input
          type="text"
          placeholder="Add custom category..."
          value={customInput}
          onChange={(e) => setCustomInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addCustom()}
          disabled={disabled}
          className="flex-1 px-3 py-1.5 text-sm border border-border rounded-md bg-bg text-text placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
        />
        <button
          type="button"
          onClick={addCustom}
          disabled={disabled || !customInput.trim()}
          className="px-3 py-1.5 text-sm border border-border rounded-md hover:bg-surface disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Add
        </button>
      </div>
      <p className="text-xs text-text-muted mt-1.5">
        Leave all unchecked to monitor all categories.
      </p>
    </div>
  )
}
```

**Step 4: Create `QuickTestInline.tsx`**

```typescript
import React from "react"
import { X, Zap } from "lucide-react"
import type { ModerationTestResponse } from "@/services/moderation"

interface QuickTestInlineProps {
  open: boolean
  onClose: () => void
  onRunTest: (text: string, phase: "input" | "output") => Promise<ModerationTestResponse | undefined>
  onOpenFull: () => void
  userId?: string
}

const resultLabel: Record<string, { text: string; color: string }> = {
  pass: { text: "PASS", color: "text-green-600 dark:text-green-400" },
  block: { text: "BLOCKED", color: "text-red-600 dark:text-red-400" },
  redact: { text: "REDACTED", color: "text-orange-600 dark:text-orange-400" },
  warn: { text: "WARNED", color: "text-yellow-600 dark:text-yellow-400" }
}

export const QuickTestInline: React.FC<QuickTestInlineProps> = ({
  open,
  onClose,
  onRunTest,
  onOpenFull,
  userId
}) => {
  const [text, setText] = React.useState("")
  const [phase, setPhase] = React.useState<"input" | "output">("input")
  const [result, setResult] = React.useState<ModerationTestResponse | null>(null)
  const [running, setRunning] = React.useState(false)
  const inputRef = React.useRef<HTMLInputElement>(null)

  React.useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [open])

  React.useEffect(() => {
    if (!open) return
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", handleEsc)
    return () => window.removeEventListener("keydown", handleEsc)
  }, [open, onClose])

  const handleRun = async () => {
    if (!text.trim()) return
    setRunning(true)
    try {
      const res = await onRunTest(text, phase)
      if (res) setResult(res)
    } finally {
      setRunning(false)
    }
  }

  if (!open) return null

  const label = result ? resultLabel[result.action] ?? resultLabel.pass : null

  return (
    <div className="border-b border-border bg-surface/80 backdrop-blur-sm px-4 py-3">
      <div className="flex items-center gap-2 max-w-7xl mx-auto">
        <Zap className="h-4 w-4 text-text-muted flex-shrink-0" />
        <input
          ref={inputRef}
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleRun()}
          placeholder="Quick test text..."
          className="flex-1 min-w-0 px-2 py-1 text-sm border border-border rounded bg-bg text-text placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <select
          value={phase}
          onChange={(e) => setPhase(e.target.value as "input" | "output")}
          className="px-2 py-1 text-sm border border-border rounded bg-bg text-text"
        >
          <option value="input">Input</option>
          <option value="output">Output</option>
        </select>
        <button
          type="button"
          onClick={handleRun}
          disabled={running || !text.trim()}
          className="px-3 py-1 text-sm font-medium rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {running ? "..." : "Run"}
        </button>
        {result && (
          <span className="flex items-center gap-1.5 text-sm">
            <span className={`font-semibold ${label?.color}`}>{label?.text}</span>
            {result.category && (
              <span className="text-text-muted">· {result.category}</span>
            )}
            <button
              type="button"
              onClick={onOpenFull}
              className="text-blue-500 hover:underline text-xs ml-1"
            >
              Full results
            </button>
          </span>
        )}
        <button type="button" onClick={onClose} className="p-1 hover:bg-surface rounded">
          <X className="h-4 w-4 text-text-muted" />
        </button>
      </div>
    </div>
  )
}
```

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/ModerationPlayground/components/
git commit -m "feat(moderation): add shared sub-components — badges, syntax ref, category picker, quick test"
```

---

## Task 4: Create Shell + Context Bar

**Files:**
- Create: `ModerationPlayground/ModerationPlaygroundShell.tsx`
- Create: `ModerationPlayground/ModerationContextBar.tsx`
- Create: `ModerationPlayground/__tests__/ModerationPlaygroundShell.test.tsx`

The shell is the main layout component. It renders the hero, context bar, and tab content.

**Step 1: Write failing test for shell**

Create `__tests__/ModerationPlaygroundShell.test.tsx`:

```typescript
import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: null, isFetching: false, error: null, refetch: vi.fn() })
}))
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (_k: string, fb?: string) => fb || _k })
}))
vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))
vi.mock("@/services/moderation", () => ({
  getModerationSettings: vi.fn(),
  getEffectivePolicy: vi.fn(),
  reloadModeration: vi.fn(),
  listUserOverrides: vi.fn(),
  testModeration: vi.fn()
}))

import { ModerationPlaygroundShell } from "../ModerationPlaygroundShell"

describe("ModerationPlaygroundShell", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.setItem("moderation-playground-onboarded", "true")
  })

  it("renders 5 tab buttons", () => {
    render(<ModerationPlaygroundShell />)
    expect(screen.getByRole("tab", { name: /policy/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /blocklist/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /overrides/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /test/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /advanced/i })).toBeInTheDocument()
  })

  it("shows Policy tab content by default", () => {
    render(<ModerationPlaygroundShell />)
    expect(screen.getByText(/personal data protection/i)).toBeInTheDocument()
  })

  it("switches to Blocklist tab on click", () => {
    render(<ModerationPlaygroundShell />)
    fireEvent.click(screen.getByRole("tab", { name: /blocklist/i }))
    expect(screen.getByText(/syntax reference/i)).toBeInTheDocument()
  })

  it("renders context bar with scope selector", () => {
    render(<ModerationPlaygroundShell />)
    expect(screen.getByText(/server/i)).toBeInTheDocument()
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps && npx vitest run packages/ui/src/components/Option/ModerationPlayground/__tests__/ModerationPlaygroundShell.test.tsx`
Expected: FAIL

**Step 3: Implement `ModerationContextBar.tsx`**

```typescript
import React from "react"
import { Tooltip } from "antd"
import { RefreshCw, Zap } from "lucide-react"
import { PolicyStatusBadges } from "./components/PolicyStatusBadges"
import { QuickTestInline } from "./components/QuickTestInline"
import type { ModerationScope } from "./moderation-utils"
import type { ModerationTestResponse } from "@/services/moderation"

interface ModerationContextBarProps {
  scope: ModerationScope
  onScopeChange: (scope: ModerationScope) => void
  userIdDraft: string
  onUserIdDraftChange: (value: string) => void
  onLoadUser: () => void
  activeUserId: string | null
  onClearUser: () => void
  userLoading: boolean
  policy: Record<string, any>
  hasUnsavedChanges: boolean
  onReload: () => void
  onRunQuickTest: (text: string, phase: "input" | "output") => Promise<ModerationTestResponse | undefined>
  onOpenTestTab: () => void
}

export const ModerationContextBar: React.FC<ModerationContextBarProps> = ({
  scope,
  onScopeChange,
  userIdDraft,
  onUserIdDraftChange,
  onLoadUser,
  activeUserId,
  onClearUser,
  userLoading,
  policy,
  hasUnsavedChanges,
  onReload,
  onRunQuickTest,
  onOpenTestTab
}) => {
  const [quickTestOpen, setQuickTestOpen] = React.useState(false)

  React.useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "t") {
        e.preventDefault()
        setQuickTestOpen((prev) => !prev)
      }
    }
    window.addEventListener("keydown", handleKey)
    return () => window.removeEventListener("keydown", handleKey)
  }, [])

  return (
    <>
      <div className="sticky top-0 z-10 border-b border-border bg-bg/95 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3 py-2.5 flex-wrap">
            {/* Scope selector */}
            <select
              value={scope}
              onChange={(e) => onScopeChange(e.target.value as ModerationScope)}
              className="px-2 py-1 text-sm border border-border rounded bg-bg text-text"
            >
              <option value="server">Server (Global)</option>
              <option value="user">User (Individual)</option>
            </select>

            {/* User ID input */}
            {scope === "user" && !activeUserId && (
              <>
                <input
                  type="text"
                  placeholder="Enter User ID"
                  value={userIdDraft}
                  onChange={(e) => onUserIdDraftChange(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && onLoadUser()}
                  className="px-2 py-1 text-sm border border-border rounded bg-bg text-text placeholder:text-text-muted w-40 sm:w-52"
                />
                <button
                  type="button"
                  onClick={onLoadUser}
                  disabled={userLoading}
                  className="px-2 py-1 text-sm border border-border rounded hover:bg-surface disabled:opacity-50"
                >
                  Load
                </button>
              </>
            )}

            {/* Active user badge */}
            {activeUserId && (
              <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-sm font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
                Configuring: {activeUserId}
                <button type="button" onClick={onClearUser} className="hover:text-blue-600 ml-0.5">×</button>
              </span>
            )}

            {/* Spacer */}
            <div className="flex-1" />

            {/* Status badges — hidden on mobile */}
            <div className="hidden sm:block">
              <PolicyStatusBadges
                enabled={policy.enabled}
                inputAction={policy.input_action}
                outputAction={policy.output_action}
                ruleCount={policy.blocklist_count ?? 0}
                compact
              />
            </div>

            {/* Unsaved indicator */}
            {hasUnsavedChanges && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300">
                <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                Unsaved
              </span>
            )}

            {/* Quick test toggle */}
            <Tooltip title="Quick Test (Ctrl+T)">
              <button
                type="button"
                onClick={() => setQuickTestOpen((prev) => !prev)}
                className={`p-1.5 rounded hover:bg-surface ${quickTestOpen ? "bg-surface" : ""}`}
              >
                <Zap className="h-4 w-4 text-text-muted" />
              </button>
            </Tooltip>

            {/* Reload */}
            <Tooltip title="Reload config from disk">
              <button type="button" onClick={onReload} className="p-1.5 rounded hover:bg-surface">
                <RefreshCw className="h-4 w-4 text-text-muted" />
              </button>
            </Tooltip>
          </div>
        </div>

        {/* Mobile status badges */}
        <div className="sm:hidden border-t border-border px-4 py-1.5">
          <PolicyStatusBadges
            enabled={policy.enabled}
            inputAction={policy.input_action}
            outputAction={policy.output_action}
            ruleCount={policy.blocklist_count ?? 0}
            compact
          />
        </div>
      </div>

      {/* Quick test slide-down */}
      <QuickTestInline
        open={quickTestOpen}
        onClose={() => setQuickTestOpen(false)}
        onRunTest={onRunQuickTest}
        onOpenFull={onOpenTestTab}
        userId={activeUserId || undefined}
      />
    </>
  )
}
```

**Step 4: Implement `ModerationPlaygroundShell.tsx`**

This is the main shell that composes hero + context bar + tab bar + panels. Wire up all hooks and pass props down to each panel. Each panel component will be created in subsequent tasks — for now, use placeholder `<div>` elements so the shell test passes:

```typescript
import React from "react"
import { useTranslation } from "react-i18next"
import { message } from "antd"
import { ShieldCheck } from "lucide-react"
import { useServerOnline } from "@/hooks/useServerOnline"
import { testModeration } from "@/services/moderation"
import { ModerationContextBar } from "./ModerationContextBar"
import { useModerationContext } from "./hooks/useModerationContext"
import { useModerationSettings } from "./hooks/useModerationSettings"
import { useBlocklist } from "./hooks/useBlocklist"
import { useUserOverrides } from "./hooks/useUserOverrides"
import { useModerationTest } from "./hooks/useModerationTest"
import { ONBOARDING_KEY } from "./moderation-utils"

// Lazy panel imports — replace with real components in Tasks 5-9
const PolicySettingsPanel = React.lazy(() => import("./PolicySettingsPanel"))
const BlocklistStudioPanel = React.lazy(() => import("./BlocklistStudioPanel"))
const UserOverridesPanel = React.lazy(() => import("./UserOverridesPanel"))
const TestSandboxPanel = React.lazy(() => import("./TestSandboxPanel"))
const AdvancedPanel = React.lazy(() => import("./AdvancedPanel"))

const TABS = [
  { key: "policy", label: "Policy & Settings" },
  { key: "blocklist", label: "Blocklist Studio" },
  { key: "overrides", label: "User Overrides" },
  { key: "test", label: "Test Sandbox" },
  { key: "advanced", label: "Advanced" }
] as const

type TabKey = (typeof TABS)[number]["key"]

const HERO_STYLE: React.CSSProperties = {
  background:
    "linear-gradient(180deg, var(--moderation-hero-start) 0%, var(--moderation-hero-end) 100%)",
  border: "1px solid var(--moderation-hero-border)",
  boxShadow: "0 24px 70px var(--moderation-hero-shadow)"
}
const HERO_GRID_STYLE: React.CSSProperties = {
  backgroundImage:
    "linear-gradient(var(--moderation-hero-grid-1) 1px, transparent 1px), linear-gradient(90deg, var(--moderation-hero-grid-2) 1px, transparent 1px)",
  backgroundSize: "28px 28px",
  opacity: "var(--moderation-hero-grid-opacity)"
}

export const ModerationPlaygroundShell: React.FC = () => {
  const { t } = useTranslation(["option", "common"])
  const online = useServerOnline()
  const [messageApi, contextHolder] = message.useMessage()
  const [activeTab, setActiveTab] = React.useState<TabKey>("policy")

  const ctx = useModerationContext()
  const settings = useModerationSettings(ctx.activeUserId)
  const blocklist = useBlocklist()
  const overrides = useUserOverrides(ctx.activeUserId)
  const tester = useModerationTest()

  const hasUnsavedChanges = settings.isDirty || overrides.isDirty

  const [showOnboarding, setShowOnboarding] = React.useState(() => {
    if (typeof window === "undefined") return false
    return !localStorage.getItem(ONBOARDING_KEY)
  })
  const dismissOnboarding = () => {
    setShowOnboarding(false)
    if (typeof window !== "undefined") localStorage.setItem(ONBOARDING_KEY, "true")
  }

  // Ctrl+S save shortcut
  React.useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault()
        if (settings.isDirty) void settings.save().then(() => messageApi.success("Settings saved")).catch((err: any) => messageApi.error(err?.message || "Save failed"))
        if (overrides.isDirty) void overrides.save().then(() => messageApi.success("Override saved")).catch((err: any) => messageApi.error(err?.message || "Save failed"))
      }
    }
    window.addEventListener("keydown", handleKey)
    return () => window.removeEventListener("keydown", handleKey)
  }, [settings, overrides, messageApi])

  // beforeunload warning
  React.useEffect(() => {
    if (!hasUnsavedChanges) return
    const handler = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = "" }
    window.addEventListener("beforeunload", handler)
    return () => window.removeEventListener("beforeunload", handler)
  }, [hasUnsavedChanges])

  // Sync test userId from context
  React.useEffect(() => {
    if (ctx.activeUserId && !tester.userId) tester.setUserId(ctx.activeUserId)
  }, [ctx.activeUserId, tester])

  const handleReload = async () => {
    try {
      await settings.reload()
      messageApi.success("Reloaded moderation config")
    } catch (err: any) {
      messageApi.error(err?.message || "Reload failed")
    }
  }

  const handleQuickTest = async (text: string, phase: "input" | "output") => {
    try {
      return await testModeration({
        user_id: ctx.activeUserId || undefined,
        phase,
        text
      })
    } catch (err: any) {
      messageApi.error(err?.message || "Test failed")
      return undefined
    }
  }

  const renderPanel = () => {
    switch (activeTab) {
      case "policy":
        return (
          <React.Suspense fallback={<div className="py-8 text-center text-text-muted">Loading...</div>}>
            <PolicySettingsPanel settings={settings} messageApi={messageApi} />
          </React.Suspense>
        )
      case "blocklist":
        return (
          <React.Suspense fallback={<div className="py-8 text-center text-text-muted">Loading...</div>}>
            <BlocklistStudioPanel blocklist={blocklist} messageApi={messageApi} />
          </React.Suspense>
        )
      case "overrides":
        return (
          <React.Suspense fallback={<div className="py-8 text-center text-text-muted">Loading...</div>}>
            <UserOverridesPanel ctx={ctx} overrides={overrides} messageApi={messageApi} />
          </React.Suspense>
        )
      case "test":
        return (
          <React.Suspense fallback={<div className="py-8 text-center text-text-muted">Loading...</div>}>
            <TestSandboxPanel tester={tester} messageApi={messageApi} />
          </React.Suspense>
        )
      case "advanced":
        return (
          <React.Suspense fallback={<div className="py-8 text-center text-text-muted">Loading...</div>}>
            <AdvancedPanel
              settings={settings}
              blocklist={blocklist}
              overrides={overrides}
              messageApi={messageApi}
            />
          </React.Suspense>
        )
    }
  }

  return (
    <div className="space-y-0">
      {contextHolder}

      {/* Onboarding */}
      {showOnboarding && (
        <div className="mx-4 sm:mx-6 lg:mx-8 mb-4 p-4 border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <p className="text-sm font-medium">Welcome to Moderation Playground</p>
          <p className="text-sm text-text-muted mt-1">Configure content safety rules, test them live, and manage per-user overrides.</p>
          <button type="button" onClick={dismissOnboarding} className="text-sm text-blue-600 hover:underline mt-2">
            Got it, let's start
          </button>
        </div>
      )}

      {/* Hero */}
      <div className="relative overflow-hidden rounded-[28px] mx-4 sm:mx-6 lg:mx-8 p-6 sm:p-8 text-text" style={HERO_STYLE}>
        <div className="absolute inset-0" style={HERO_GRID_STYLE} />
        <div className="relative flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl sm:text-2xl font-display font-bold">
              {t("option:moderationPlayground.title", "Moderation Playground")}
            </h2>
            <p className="text-text-muted text-sm mt-1">
              {t("option:moderationPlayground.subtitle", "Family safety controls and server guardrails in one place.")}
            </p>
            <div className="mt-2">
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${online ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300" : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"}`}>
                {online ? "Server online" : "Server offline"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Context bar */}
      <ModerationContextBar
        scope={ctx.scope}
        onScopeChange={ctx.setScope}
        userIdDraft={ctx.userIdDraft}
        onUserIdDraftChange={ctx.setUserIdDraft}
        onLoadUser={ctx.loadUser}
        activeUserId={ctx.activeUserId}
        onClearUser={ctx.clearUser}
        userLoading={overrides.loading}
        policy={settings.policy}
        hasUnsavedChanges={hasUnsavedChanges}
        onReload={handleReload}
        onRunQuickTest={handleQuickTest}
        onOpenTestTab={() => setActiveTab("test")}
      />

      {/* Offline warning */}
      {!online && (
        <div className="mx-4 sm:mx-6 lg:mx-8 p-3 border border-yellow-200 dark:border-yellow-800 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg text-sm text-yellow-800 dark:text-yellow-300">
          Connect to your tldw server to use moderation controls.
        </div>
      )}

      {/* Tab bar */}
      <div className="border-b border-border mx-4 sm:mx-6 lg:mx-8">
        <div className="flex overflow-x-auto -mb-px" role="tablist">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              role="tab"
              aria-selected={activeTab === tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`
                px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors
                ${activeTab === tab.key
                  ? "border-blue-500 text-blue-600 dark:text-blue-400"
                  : "border-transparent text-text-muted hover:text-text hover:border-gray-300"
                }
              `}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="mx-4 sm:mx-6 lg:mx-8 py-6">
        {renderPanel()}
      </div>
    </div>
  )
}
```

**Step 5: Create stub panel files so imports resolve**

Create these 5 files as minimal default exports. Each will be fully implemented in Tasks 5–9:

`PolicySettingsPanel.tsx`:
```typescript
import React from "react"
const PolicySettingsPanel: React.FC<any> = ({ settings }) => (
  <div>
    <h3 className="font-semibold">Personal Data Protection</h3>
    <p className="text-text-muted text-sm">Policy settings panel — coming soon</p>
  </div>
)
export default PolicySettingsPanel
```

(Same pattern for `BlocklistStudioPanel.tsx`, `UserOverridesPanel.tsx`, `TestSandboxPanel.tsx`, `AdvancedPanel.tsx` — each with a placeholder that includes the text the shell test expects, e.g., BlocklistStudioPanel includes "Syntax Reference")

**Step 6: Run shell test**

Run: `cd apps && npx vitest run packages/ui/src/components/Option/ModerationPlayground/__tests__/ModerationPlaygroundShell.test.tsx`
Expected: PASS

**Step 7: Commit**

```bash
git add apps/packages/ui/src/components/Option/ModerationPlayground/ModerationPlaygroundShell.tsx \
       apps/packages/ui/src/components/Option/ModerationPlayground/ModerationContextBar.tsx \
       apps/packages/ui/src/components/Option/ModerationPlayground/PolicySettingsPanel.tsx \
       apps/packages/ui/src/components/Option/ModerationPlayground/BlocklistStudioPanel.tsx \
       apps/packages/ui/src/components/Option/ModerationPlayground/UserOverridesPanel.tsx \
       apps/packages/ui/src/components/Option/ModerationPlayground/TestSandboxPanel.tsx \
       apps/packages/ui/src/components/Option/ModerationPlayground/AdvancedPanel.tsx \
       apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/ModerationPlaygroundShell.test.tsx
git commit -m "feat(moderation): add shell with context bar, tab routing, and stub panels"
```

---

## Task 5: Implement PolicySettingsPanel

**Files:**
- Modify: `ModerationPlayground/PolicySettingsPanel.tsx` (replace stub)
- Create: `ModerationPlayground/__tests__/PolicySettingsPanel.test.tsx`

**Step 1: Write failing test**

Create `__tests__/PolicySettingsPanel.test.tsx`:

```typescript
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (_k: string, fb?: string) => fb || _k })
}))

import PolicySettingsPanel from "../PolicySettingsPanel"

const makeSettings = (overrides = {}) => ({
  draft: { piiEnabled: false, categoriesEnabled: [], persist: false },
  updateDraft: vi.fn(),
  isDirty: false,
  reset: vi.fn(),
  save: vi.fn().mockResolvedValue(undefined),
  reload: vi.fn(),
  settingsQuery: { data: null, isFetching: false },
  policyQuery: { data: null },
  policy: { enabled: true, input_action: "block", output_action: "redact", blocklist_count: 5 },
  online: true,
  ...overrides
})

describe("PolicySettingsPanel", () => {
  it("renders PII toggle", () => {
    render(<PolicySettingsPanel settings={makeSettings()} messageApi={{ success: vi.fn(), error: vi.fn(), warning: vi.fn() }} />)
    expect(screen.getByText(/personal data protection/i)).toBeInTheDocument()
  })

  it("renders category picker", () => {
    render(<PolicySettingsPanel settings={makeSettings()} messageApi={{ success: vi.fn(), error: vi.fn(), warning: vi.fn() }} />)
    expect(screen.getByText(/violence/i)).toBeInTheDocument()
    expect(screen.getByText(/gambling/i)).toBeInTheDocument()
  })

  it("shows unsaved indicator when dirty", () => {
    render(<PolicySettingsPanel settings={makeSettings({ isDirty: true })} messageApi={{ success: vi.fn(), error: vi.fn(), warning: vi.fn() }} />)
    expect(screen.getByText(/save/i)).toBeInTheDocument()
    expect(screen.getByText(/reset/i)).toBeInTheDocument()
  })

  it("disables reset when not dirty", () => {
    render(<PolicySettingsPanel settings={makeSettings({ isDirty: false })} messageApi={{ success: vi.fn(), error: vi.fn(), warning: vi.fn() }} />)
    expect(screen.getByRole("button", { name: /reset/i })).toBeDisabled()
  })
})
```

**Step 2: Implement `PolicySettingsPanel.tsx`**

Replace the stub with the full implementation per the design doc Section 2: master toggle (enabled), input/output split controls with enabled toggles + action selectors, PII toggle, CategoryPicker grid, persist toggle with confirmation modal, save/reset buttons, active policy summary.

Use `CategoryPicker` from `./components/CategoryPicker`. Use antd `Modal.confirm` for persist warning, antd `Tooltip` for help text, antd `Select` for action dropdowns (since they need option descriptions). All layout via Tailwind.

The panel receives `settings` (from `useModerationSettings`) and `messageApi` as props.

**Step 3: Run test**

Run: `cd apps && npx vitest run packages/ui/src/components/Option/ModerationPlayground/__tests__/PolicySettingsPanel.test.tsx`
Expected: PASS

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Option/ModerationPlayground/PolicySettingsPanel.tsx \
       apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/PolicySettingsPanel.test.tsx
git commit -m "feat(moderation): implement PolicySettingsPanel with full server config controls"
```

---

## Task 6: Implement BlocklistStudioPanel

**Files:**
- Modify: `ModerationPlayground/BlocklistStudioPanel.tsx` (replace stub)
- Create: `ModerationPlayground/__tests__/BlocklistStudioPanel.test.tsx`

**Step 1: Write failing test**

Test the managed rules view (add form with structured fields, rules table) and raw editor view (textarea, load/validate/save buttons), plus syntax reference collapsible.

**Step 2: Implement `BlocklistStudioPanel.tsx`**

Per design doc Section 3. Two sub-views via internal tab state ("managed" | "raw"). Structured add-rule form with: pattern input, action dropdown, categories multi-select (antd Select tags mode), phase selector. Inline lint result below form. Rules table with columns: #, pattern, type tag, action tag, categories, delete button. Version footer. Raw editor with monospace textarea, buttons, lint table. `BlocklistSyntaxRef` component at bottom.

The panel receives `blocklist` (from `useBlocklist`) and `messageApi` as props.

Auto-load managed list on mount via `useEffect` calling `blocklist.loadManaged()`.

**Step 3: Run test, verify pass**

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Option/ModerationPlayground/BlocklistStudioPanel.tsx \
       apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/BlocklistStudioPanel.test.tsx
git commit -m "feat(moderation): implement BlocklistStudioPanel with structured add form and syntax ref"
```

---

## Task 7: Implement UserOverridesPanel

**Files:**
- Modify: `ModerationPlayground/UserOverridesPanel.tsx` (replace stub)
- Create: `ModerationPlayground/__tests__/UserOverridesPanel.test.tsx`

**Step 1: Write failing test**

Test: user picker renders, preset buttons render, phrase list add form with phase selector, banned/notify split, overrides table with search and bulk delete.

**Step 2: Implement `UserOverridesPanel.tsx`**

Per design doc Section 4. User picker (searchable input with existing override suggestions from `overrides.overridesQuery.data`). Two-column layout: left = presets + toggles + action selectors + categories; right = phrase list builder + banned/notify lists. All Overrides table at bottom with search, row selection, bulk delete. Uses antd `Modal.confirm` for delete confirmations.

The panel receives `ctx` (from `useModerationContext`), `overrides` (from `useUserOverrides`), and `messageApi` as props.

**Step 3: Run test, verify pass**

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Option/ModerationPlayground/UserOverridesPanel.tsx \
       apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/UserOverridesPanel.test.tsx
git commit -m "feat(moderation): implement UserOverridesPanel with picker, phrase lists, and bulk ops"
```

---

## Task 8: Implement TestSandboxPanel

**Files:**
- Modify: `ModerationPlayground/TestSandboxPanel.tsx` (replace stub)
- Create: `ModerationPlayground/__tests__/TestSandboxPanel.test.tsx`

**Step 1: Write failing test**

Test: phase selector renders, quick sample buttons render, run test button calls tester.runTest, result displays with before/after, test history table renders with rerun/load actions.

**Step 2: Implement `TestSandboxPanel.tsx`**

Per design doc Section 5. Phase segmented control + user ID input. TextArea for sample text. Quick sample buttons (derived from `CATEGORY_SUGGESTIONS` keywords). Run Test button. Results section with status badge, two-column match details / before-after comparison. Effective policy collapsible JSON. Test history table with truncated input, phase, result badge, Rerun and Load buttons.

Quick samples array:
```typescript
const QUICK_SAMPLES = [
  { label: "PII: email", text: "Contact me at john.doe@example.com for details" },
  { label: "PII: phone", text: "My phone number is 555-123-4567" },
  { label: "Profanity", text: "That was a damn stupid thing to do" },
  { label: "Violence", text: "I want to kill the process and bomb the deployment" },
  { label: "Clean text", text: "The weather is nice today and I enjoy reading books" }
]
```

Before/After comparison: highlight matched span in original text using `result.sample` to find the match position. Show redacted text below/beside. Use colored backgrounds for highlighting.

The panel receives `tester` (from `useModerationTest`) and `messageApi` as props.

**Step 3: Run test, verify pass**

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Option/ModerationPlayground/TestSandboxPanel.tsx \
       apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/TestSandboxPanel.test.tsx
git commit -m "feat(moderation): implement TestSandboxPanel with quick samples, before/after, and history"
```

---

## Task 9: Implement AdvancedPanel

**Files:**
- Modify: `ModerationPlayground/AdvancedPanel.tsx` (replace stub)
- Create: `ModerationPlayground/__tests__/AdvancedPanel.test.tsx`

**Step 1: Write failing test**

Test: performance tuning fields render with values from policy, export buttons render, reload button renders, per-user overrides toggle renders, config viewer collapsible works.

**Step 2: Implement `AdvancedPanel.tsx`**

Per design doc Section 6. Performance tuning section with read-only fields showing values from effective policy snapshot (max_scan_chars, max_replacements_per_pattern, match_window_chars, blocklist_write_debounce_ms) with descriptions. Export/import section with download/upload buttons for blocklist and overrides. System operations section with reload button and per-user overrides toggle. Config viewer with collapsible JSON.

Export: download creates a Blob from API data and triggers `URL.createObjectURL` + click.
Import: uses `<input type="file">` with onChange handler, reads file, calls appropriate API.

The panel receives `settings`, `blocklist`, `overrides`, and `messageApi` as props.

**Step 3: Run test, verify pass**

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Option/ModerationPlayground/AdvancedPanel.tsx \
       apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/AdvancedPanel.test.tsx
git commit -m "feat(moderation): implement AdvancedPanel with perf tuning, export/import, and config viewer"
```

---

## Task 10: Wire Up index.tsx and Update Route

**Files:**
- Modify: `ModerationPlayground/index.tsx` (replace with thin re-export)
- Modify: `routes/option-moderation-playground.tsx` (point to shell)

**Step 1: Replace `index.tsx`**

Replace the entire 1,918-line file with:

```typescript
export { ModerationPlaygroundShell as ModerationPlayground } from "./ModerationPlaygroundShell"
```

**Step 2: Verify route file still works**

Read `apps/packages/ui/src/routes/option-moderation-playground.tsx` — it imports `ModerationPlayground` from the index. Since we're re-exporting `ModerationPlaygroundShell` as `ModerationPlayground`, the route needs no changes.

**Step 3: Run all tests**

Run: `cd apps && npx vitest run packages/ui/src/components/Option/ModerationPlayground/__tests__/`
Expected: All new tests PASS. Existing tests will need updates (Task 11).

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Option/ModerationPlayground/index.tsx
git commit -m "refactor(moderation): replace monolith with thin re-export of shell"
```

---

## Task 11: Update Existing Tests

**Files:**
- Modify: `ModerationPlayground/__tests__/ModerationPlayground.progressive-disclosure.test.tsx`
- Modify: `ModerationPlayground/__tests__/ModerationPlayground.quick-lists.test.tsx`

The existing tests import `ModerationPlayground` from `../index` and test the monolithic component. After the rewrite, they need to test the new shell+panel architecture.

**Step 1: Update progressive-disclosure tests**

The progressive disclosure concept changes:
- Onboarding banner → still exists on shell, test dismissal + localStorage
- "Advanced mode" toggle → replaced by tabs; test tab navigation instead
- Permission error → still handled by shell, test 403 error display
- Server scope default → test that Policy & Settings tab is default

Update imports and selectors to match new DOM structure (tabs instead of Advanced toggle, etc.).

**Step 2: Update quick-lists tests**

Quick lists are now in `UserOverridesPanel`. Tests need to:
- Navigate to "User Overrides" tab first
- Use the new user picker (searchable input instead of Segmented control)
- Assertions on phrase list rendering remain similar

Update the `switchToUserScopeAndLoadUser` helper to use the new context bar scope selector and user picker.

**Step 3: Run all moderation tests**

Run: `cd apps && npx vitest run packages/ui/src/components/Option/ModerationPlayground/__tests__/`
Expected: All PASS

**Step 4: Run broader test suite to check for regressions**

Run: `cd apps && npx vitest run packages/ui/src/services/__tests__/moderation.service.contract.test.ts`
Expected: PASS (service layer unchanged)

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/
git commit -m "test(moderation): update existing tests for new tabbed architecture"
```

---

## Task 12: Cleanup and Final Verification

**Files:**
- Review all new files for unused imports, dead code

**Step 1: Run full test suite**

Run: `cd apps && npx vitest run packages/ui/src/components/Option/ModerationPlayground/`
Expected: All tests PASS

**Step 2: Verify build compiles**

Run: `cd apps && npx tsc --noEmit -p packages/ui/tsconfig.json 2>&1 | head -30`
Expected: No errors in ModerationPlayground files

**Step 3: Visual smoke test checklist**

Manually verify (or note for QA):
- [ ] Page loads at `/moderation-playground`
- [ ] Hero renders with server status
- [ ] Context bar sticks on scroll
- [ ] All 5 tabs render content
- [ ] Scope selector switches between Server/User
- [ ] Quick Test opens/closes with Ctrl+T
- [ ] Ctrl+S saves current tab changes
- [ ] Mobile layout collapses properly at 640px and 768px breakpoints
- [ ] Category picker shows all 8+ categories with descriptions
- [ ] Blocklist syntax reference collapses/expands
- [ ] Test history persists within session, clears on page reload

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore(moderation): cleanup and finalize playground redesign"
```

---

## Dependency Graph

```
Task 1 (utils) ──────────┐
                          ├──→ Task 3 (sub-components) ──→ Task 4 (shell) ──┐
Task 2 (hooks) ──────────┘                                                   │
                                                                             ├──→ Task 10 (wire up)
Task 5 (PolicyPanel) ────────────────────────────────────────────────────────┤
Task 6 (BlocklistPanel) ─────────────────────────────────────────────────────┤
Task 7 (UserOverridesPanel) ─────────────────────────────────────────────────┤
Task 8 (TestSandboxPanel) ───────────────────────────────────────────────────┤
Task 9 (AdvancedPanel) ──────────────────────────────────────────────────────┘
                                                                             │
Task 11 (update tests) ←─────────────────────────────────────────────────────┤
Task 12 (cleanup) ←──────────────────────────────────────────────────────────┘
```

Tasks 5–9 can be parallelized after Task 4 completes.
Tasks 1 and 2 can be parallelized.
Task 3 depends on Task 1 (imports from `moderation-utils`).
Task 4 depends on Tasks 2 and 3.
