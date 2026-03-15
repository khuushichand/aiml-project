# Watchlist "Chat About This Article" Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "Chat about this" button to Watchlist Items and Outputs tabs that navigates to the chat page with article content pre-loaded in the composer.

**Architecture:** Extends the existing media-chat handoff pattern with a new watchlist-specific payload type and localStorage setting. The Items tab and Output preview drawer get new action buttons. PlaygroundForm detects the new setting on mount and populates the composer. All changes are frontend-only.

**Tech Stack:** React, TypeScript, Ant Design, Zustand, react-router-dom, localStorage

---

### Task 1: Watchlist Chat Handoff Service

**Files:**
- Create: `apps/packages/ui/src/services/tldw/watchlist-chat-handoff.ts`
- Create: `apps/packages/ui/src/services/tldw/__tests__/watchlist-chat-handoff.test.ts`

**Step 1: Write the failing tests**

```typescript
// apps/packages/ui/src/services/tldw/__tests__/watchlist-chat-handoff.test.ts
import { describe, expect, it } from "vitest"
import {
  buildWatchlistChatHint,
  normalizeWatchlistChatHandoffPayload,
  type WatchlistChatArticle,
  type WatchlistChatHandoffPayload
} from "../watchlist-chat-handoff"

describe("normalizeWatchlistChatHandoffPayload", () => {
  it("returns undefined for null", () => {
    expect(normalizeWatchlistChatHandoffPayload(null)).toBeUndefined()
  })

  it("returns undefined for non-object", () => {
    expect(normalizeWatchlistChatHandoffPayload("string")).toBeUndefined()
  })

  it("returns undefined for empty articles array", () => {
    expect(normalizeWatchlistChatHandoffPayload({ articles: [] })).toBeUndefined()
  })

  it("normalizes a single-article payload", () => {
    const input = {
      articles: [{ title: " My Title ", content: "Body text" }]
    }
    const result = normalizeWatchlistChatHandoffPayload(input)
    expect(result).toEqual({
      articles: [{ title: "My Title", content: "Body text" }]
    })
  })

  it("filters out articles with no content and no title", () => {
    const input = {
      articles: [
        { title: "Good", content: "Has content" },
        { content: "  " } // empty after trim
      ]
    }
    const result = normalizeWatchlistChatHandoffPayload(input)
    expect(result!.articles).toHaveLength(1)
    expect(result!.articles[0].title).toBe("Good")
  })

  it("keeps articles that have title but no content", () => {
    const input = {
      articles: [{ title: "Title Only", url: "https://example.com" }]
    }
    const result = normalizeWatchlistChatHandoffPayload(input)
    expect(result!.articles).toHaveLength(1)
  })
})

describe("buildWatchlistChatHint", () => {
  it("builds hint for single article with content", () => {
    const payload: WatchlistChatHandoffPayload = {
      articles: [
        { title: "My Article", content: "Article body here", sourceType: "item" }
      ]
    }
    const hint = buildWatchlistChatHint(payload)
    expect(hint).toContain("I'd like to discuss this article:")
    expect(hint).toContain('--- "My Article" ---')
    expect(hint).toContain("Article body here")
  })

  it("builds hint for multiple articles", () => {
    const payload: WatchlistChatHandoffPayload = {
      articles: [
        { title: "First", content: "Body 1", sourceType: "item" },
        { title: "Second", content: "Body 2", sourceType: "item" }
      ]
    }
    const hint = buildWatchlistChatHint(payload)
    expect(hint).toContain("I'd like to discuss these articles:")
    expect(hint).toContain('--- Article 1: "First" ---')
    expect(hint).toContain('--- Article 2: "Second" ---')
  })

  it("includes URL when available", () => {
    const payload: WatchlistChatHandoffPayload = {
      articles: [
        { title: "With URL", url: "https://example.com", content: "Body", sourceType: "item" }
      ]
    }
    const hint = buildWatchlistChatHint(payload)
    expect(hint).toContain("URL: https://example.com")
  })

  it("handles article with no content — uses title and url fallback", () => {
    const payload: WatchlistChatHandoffPayload = {
      articles: [
        { title: "No Content", url: "https://example.com", sourceType: "item" }
      ]
    }
    const hint = buildWatchlistChatHint(payload)
    expect(hint).toContain("No Content")
    expect(hint).toContain("https://example.com")
    expect(hint).toContain("Full content not available")
  })

  it("returns empty string for empty articles", () => {
    expect(buildWatchlistChatHint({ articles: [] })).toBe("")
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd apps/packages/ui && npx vitest run src/services/tldw/__tests__/watchlist-chat-handoff.test.ts`
Expected: FAIL — module not found

**Step 3: Write the implementation**

```typescript
// apps/packages/ui/src/services/tldw/watchlist-chat-handoff.ts

export type WatchlistChatArticle = {
  title?: string
  url?: string
  content?: string
  sourceType?: "item" | "output"
  mediaId?: number
}

export type WatchlistChatHandoffPayload = {
  articles: WatchlistChatArticle[]
}

const toNonEmptyString = (value: unknown): string | undefined => {
  if (typeof value !== "string") return undefined
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

const normalizeArticle = (raw: unknown): WatchlistChatArticle | undefined => {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return undefined
  const obj = raw as Record<string, unknown>
  const title = toNonEmptyString(obj.title)
  const url = toNonEmptyString(obj.url)
  const content = toNonEmptyString(obj.content)
  // Must have at least a title or content
  if (!title && !content) return undefined
  const article: WatchlistChatArticle = {}
  if (title) article.title = title
  if (url) article.url = url
  if (content) article.content = content
  if (obj.sourceType === "item" || obj.sourceType === "output") {
    article.sourceType = obj.sourceType
  }
  if (typeof obj.mediaId === "number" && Number.isFinite(obj.mediaId) && obj.mediaId > 0) {
    article.mediaId = Math.trunc(obj.mediaId)
  }
  return article
}

export const normalizeWatchlistChatHandoffPayload = (
  value: unknown
): WatchlistChatHandoffPayload | undefined => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined
  const obj = value as Record<string, unknown>
  if (!Array.isArray(obj.articles)) return undefined
  const articles = obj.articles
    .map((a: unknown) => normalizeArticle(a))
    .filter((a): a is WatchlistChatArticle => a != null)
  if (articles.length === 0) return undefined
  return { articles }
}

const formatArticleBlock = (article: WatchlistChatArticle, index?: number): string => {
  const titleText = article.title || "Untitled article"
  const header = index != null
    ? `--- Article ${index + 1}: "${titleText}" ---`
    : `--- "${titleText}" ---`
  const lines: string[] = [header]
  if (article.url) {
    lines.push(`URL: ${article.url}`)
  }
  if (article.content) {
    lines.push(article.content)
  } else {
    lines.push(`${titleText}${article.url ? ` — ${article.url}` : ""}`)
    lines.push("(Full content not available for this article)")
  }
  return lines.join("\n")
}

export const buildWatchlistChatHint = (
  payload: WatchlistChatHandoffPayload
): string => {
  const { articles } = payload
  if (articles.length === 0) return ""

  if (articles.length === 1) {
    const intro = "I'd like to discuss this article:\n\n"
    return intro + formatArticleBlock(articles[0])
  }

  const intro = "I'd like to discuss these articles:\n\n"
  const blocks = articles.map((a, i) => formatArticleBlock(a, i))
  return intro + blocks.join("\n\n")
}

export const getWatchlistChatTotalChars = (
  payload: WatchlistChatHandoffPayload
): number => {
  return payload.articles.reduce(
    (sum, a) => sum + (a.content?.length ?? 0),
    0
  )
}

export const WATCHLIST_CHAT_CONTENT_WARN_THRESHOLD = 80_000
```

**Step 4: Run tests to verify they pass**

Run: `cd apps/packages/ui && npx vitest run src/services/tldw/__tests__/watchlist-chat-handoff.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/watchlist-chat-handoff.ts apps/packages/ui/src/services/tldw/__tests__/watchlist-chat-handoff.test.ts
git commit -m "feat(watchlists): add watchlist chat handoff service and tests"
```

---

### Task 2: Watchlist Chat Setting in UI Settings

**Files:**
- Modify: `apps/packages/ui/src/services/settings/ui-settings.ts` (near line 687, after `DISCUSS_MEDIA_PROMPT_SETTING`)

**Step 1: Add the setting**

Add this import at the top of the file (alongside existing `media-chat-handoff` import):

```typescript
import {
  normalizeWatchlistChatHandoffPayload,
  type WatchlistChatHandoffPayload
} from "../tldw/watchlist-chat-handoff"
```

Then add the setting definition after `DISCUSS_MEDIA_PROMPT_SETTING` (after line 687):

```typescript
export type DiscussWatchlistPrompt = WatchlistChatHandoffPayload

export const DISCUSS_WATCHLIST_PROMPT_SETTING = defineSetting(
  "tldw:discussWatchlistPrompt",
  undefined as DiscussWatchlistPrompt | undefined,
  (value) => normalizeWatchlistChatHandoffPayload(value),
  {
    area: "local",
    localStorageKey: "tldw:discussWatchlistPrompt",
    mirrorToLocalStorage: true
  }
)
```

**Step 2: Verify no type errors**

Run: `cd apps/packages/ui && npx tsc --noEmit --pretty 2>&1 | head -30`
Expected: No new errors (pre-existing errors may exist)

**Step 3: Commit**

```bash
git add apps/packages/ui/src/services/settings/ui-settings.ts
git commit -m "feat(settings): add DISCUSS_WATCHLIST_PROMPT_SETTING for watchlist chat handoff"
```

---

### Task 3: PlaygroundForm — Detect Watchlist Handoff

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx` (near lines 2304-2362)

**Step 1: Add imports**

Add alongside existing media-chat-handoff imports at the top of PlaygroundForm.tsx:

```typescript
import {
  normalizeWatchlistChatHandoffPayload,
  buildWatchlistChatHint
} from "@/services/tldw/watchlist-chat-handoff"
```

And add the setting import (alongside existing `DISCUSS_MEDIA_PROMPT_SETTING`):

```typescript
import { DISCUSS_WATCHLIST_PROMPT_SETTING } from "@/services/settings/ui-settings"
```

**Step 2: Add the apply function**

Add immediately after the `applyDiscussMediaPayload` callback (after line 2338):

```typescript
const applyDiscussWatchlistPayload = React.useCallback(
  (
    rawPayload: unknown,
    options?: { clearAfterUse?: boolean }
  ) => {
    const payload = normalizeWatchlistChatHandoffPayload(rawPayload)
    if (!payload) {
      if (options?.clearAfterUse) {
        void clearSetting(DISCUSS_WATCHLIST_PROMPT_SETTING)
      }
      return
    }
    if (options?.clearAfterUse) {
      void clearSetting(DISCUSS_WATCHLIST_PROMPT_SETTING)
    }
    setChatMode("normal")
    setRagMediaIds(null)
    const hint = buildWatchlistChatHint(payload)
    if (!hint) return
    setMessageValue(hint, { collapseLarge: true, forceCollapse: true })
    textAreaFocus()
  },
  [setChatMode, setMessageValue, setRagMediaIds, textAreaFocus]
)
```

**Step 3: Add mount-time detection**

Add immediately after the existing media mount-time effect (after line 2351):

```typescript
// Seed composer when a watchlist item requests discussion
React.useEffect(() => {
  let cancelled = false
  void (async () => {
    const payload = await getSetting(DISCUSS_WATCHLIST_PROMPT_SETTING)
    if (cancelled || !payload) return
    applyDiscussWatchlistPayload(payload, { clearAfterUse: true })
  })()
  return () => {
    cancelled = true
  }
}, [applyDiscussWatchlistPayload])
```

**Step 4: Add event listener**

Add immediately after the existing media event listener (after line 2362):

```typescript
React.useEffect(() => {
  const handler = (event: Event) => {
    const detail = (event as CustomEvent).detail
    applyDiscussWatchlistPayload(detail)
  }
  window.addEventListener("tldw:discuss-watchlist", handler as any)
  return () => {
    window.removeEventListener("tldw:discuss-watchlist", handler as any)
  }
}, [applyDiscussWatchlistPayload])
```

**Step 5: Verify no type errors**

Run: `cd apps/packages/ui && npx tsc --noEmit --pretty 2>&1 | head -30`
Expected: No new errors

**Step 6: Commit**

```bash
git add apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx
git commit -m "feat(chat): detect watchlist chat handoff payload on mount and via event"
```

---

### Task 4: Items Tab — "Chat About This" Button (Single Item)

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/ItemsTab.tsx`

**Step 1: Add imports**

Add to the lucide-react import (line 19):

```typescript
import { CheckCircle2, ExternalLink, HelpCircle, MessageSquare, RefreshCw, Rss, Sun } from "lucide-react"
```

Add new imports:

```typescript
import { useNavigate } from "react-router-dom"
import { setSetting } from "@/services/settings"
import { DISCUSS_WATCHLIST_PROMPT_SETTING } from "@/services/settings/ui-settings"
import {
  type WatchlistChatHandoffPayload,
  type WatchlistChatArticle,
  getWatchlistChatTotalChars,
  WATCHLIST_CHAT_CONTENT_WARN_THRESHOLD
} from "@/services/tldw/watchlist-chat-handoff"
```

**Step 2: Add navigate hook and handler**

Inside the `ItemsTab` component (after line 173), add:

```typescript
const navigate = useNavigate()
```

Add the handler function (alongside other handlers, e.g. near `openSelectedItemOriginal`):

```typescript
const handleChatAboutItem = useCallback(
  (item: ScrapedItem) => {
    const article: WatchlistChatArticle = {
      title: item.title || undefined,
      url: item.url || undefined,
      content: item.content || item.summary || undefined,
      sourceType: "item",
      mediaId: item.media_id ?? undefined
    }
    const payload: WatchlistChatHandoffPayload = { articles: [article] }
    void setSetting(DISCUSS_WATCHLIST_PROMPT_SETTING, payload)
    window.dispatchEvent(
      new CustomEvent("tldw:discuss-watchlist", { detail: payload })
    )
    navigate("/")
  },
  [navigate]
)
```

**Step 3: Add the button to the action bar**

In the action buttons `<Space wrap>` section (around line 2407), add a new button after the "Open Original" button and before the "Mark as reviewed" button:

```typescript
<Tooltip title={t("watchlists:items.chatAbout", "Chat about this article")}>
  <Button
    size="small"
    icon={<MessageSquare className="h-3.5 w-3.5" />}
    onClick={() => handleChatAboutItem(selectedItem)}
    disabled={!selectedItem.content && !selectedItem.summary && !selectedItem.title}
    data-testid="watchlists-item-chat-about"
  >
    {t("watchlists:items.chatAboutButton", "Chat")}
  </Button>
</Tooltip>
```

**Step 4: Verify no type errors**

Run: `cd apps/packages/ui && npx tsc --noEmit --pretty 2>&1 | head -30`
Expected: No new errors

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Watchlists/ItemsTab/ItemsTab.tsx
git commit -m "feat(watchlists): add Chat button for single item in Items tab"
```

---

### Task 5: Items Tab — "Chat About Selected" Batch Action

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/ItemsTab.tsx`

**Step 1: Add the batch handler**

Add alongside `handleChatAboutItem`:

```typescript
const handleChatAboutSelected = useCallback(() => {
  const selected = items.filter((item) => selectedItemIdSet.has(item.id))
  if (selected.length === 0) return
  const articles: WatchlistChatArticle[] = selected.map((item) => ({
    title: item.title || undefined,
    url: item.url || undefined,
    content: item.content || item.summary || undefined,
    sourceType: "item" as const,
    mediaId: item.media_id ?? undefined
  }))
  const payload: WatchlistChatHandoffPayload = { articles }
  const totalChars = getWatchlistChatTotalChars(payload)
  if (totalChars > WATCHLIST_CHAT_CONTENT_WARN_THRESHOLD) {
    Modal.confirm({
      title: t("watchlists:items.chatSizeWarningTitle", "Large content warning"),
      content: t(
        "watchlists:items.chatSizeWarningContent",
        "Selected articles contain {{chars}} characters of content. This may use significant tokens. Continue with full content, or use summaries instead?",
        { chars: totalChars.toLocaleString() }
      ),
      okText: t("watchlists:items.chatSizeWarningOk", "Use full content"),
      cancelText: t("watchlists:items.chatSizeWarningCancel", "Cancel"),
      onOk: () => {
        void setSetting(DISCUSS_WATCHLIST_PROMPT_SETTING, payload)
        window.dispatchEvent(
          new CustomEvent("tldw:discuss-watchlist", { detail: payload })
        )
        navigate("/")
      }
    })
    return
  }
  void setSetting(DISCUSS_WATCHLIST_PROMPT_SETTING, payload)
  window.dispatchEvent(
    new CustomEvent("tldw:discuss-watchlist", { detail: payload })
  )
  navigate("/")
}, [items, selectedItemIdSet, navigate, t])
```

**Step 2: Add the batch button to the batch actions toolbar**

In the batch action toolbar `<div>` (line 2077, the `mt-2 flex flex-wrap` div), add a "Chat about selected" button after the existing batch review buttons:

```typescript
<Button
  size="small"
  icon={<MessageSquare className="h-3.5 w-3.5" />}
  onClick={handleChatAboutSelected}
  disabled={selectedItemIds.length === 0}
  data-testid="watchlists-items-chat-selected"
>
  {t("watchlists:items.batch.chatSelected", "Chat about selected ({{count}})", {
    count: selectedItemIds.length
  })}
</Button>
```

**Step 3: Verify no type errors**

Run: `cd apps/packages/ui && npx tsc --noEmit --pretty 2>&1 | head -30`
Expected: No new errors

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Option/Watchlists/ItemsTab/ItemsTab.tsx
git commit -m "feat(watchlists): add Chat about selected batch action in Items tab"
```

---

### Task 6: Output Preview Drawer — "Chat About This" Button

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/OutputPreviewDrawer.tsx`

**Step 1: Add imports**

Add to the existing lucide-react import:

```typescript
import { Download, ExternalLink, MessageSquare } from "lucide-react"
```

Add new imports:

```typescript
import { useNavigate } from "react-router-dom"
import { setSetting } from "@/services/settings"
import { DISCUSS_WATCHLIST_PROMPT_SETTING } from "@/services/settings/ui-settings"
import type { WatchlistChatHandoffPayload } from "@/services/tldw/watchlist-chat-handoff"
```

**Step 2: Add navigate hook and handler**

Inside the component, add:

```typescript
const navigate = useNavigate()

const handleChatAboutOutput = useCallback(() => {
  if (!output) return
  const payload: WatchlistChatHandoffPayload = {
    articles: [
      {
        title: output.title || `Output #${output.id}`,
        content: content || undefined,
        sourceType: "output",
        mediaId: output.media_item_id ?? undefined
      }
    ]
  }
  void setSetting(DISCUSS_WATCHLIST_PROMPT_SETTING, payload)
  window.dispatchEvent(
    new CustomEvent("tldw:discuss-watchlist", { detail: payload })
  )
  navigate("/")
}, [output, content, navigate])
```

Note: `content` is the existing state variable that holds the fetched output text (already available in this component).

**Step 3: Add the button to the drawer header**

In the drawer `extra` section (around line 188), add the chat button before the download button:

```typescript
<Tooltip title={t("watchlists:outputs.chatAbout", "Chat about this")}>
  <Button
    type="text"
    icon={<MessageSquare className="h-4 w-4" />}
    onClick={handleChatAboutOutput}
    disabled={!content}
    data-testid="watchlists-output-chat-about"
  />
</Tooltip>
```

**Step 4: Verify no type errors**

Run: `cd apps/packages/ui && npx tsc --noEmit --pretty 2>&1 | head -30`
Expected: No new errors

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Watchlists/OutputsTab/OutputPreviewDrawer.tsx
git commit -m "feat(watchlists): add Chat button in output preview drawer"
```

---

### Task 7: Component Tests — Items Tab Chat Buttons

**Files:**
- Create: `apps/packages/ui/src/components/Option/Watchlists/__tests__/ItemsTab.chat-handoff.test.tsx`

**Step 1: Write the tests**

Look at existing test files in `apps/packages/ui/src/components/Option/Watchlists/__tests__/` for patterns (mock setup, providers, render helpers). Follow the same mocking conventions.

Test cases to cover:

```typescript
// apps/packages/ui/src/components/Option/Watchlists/__tests__/ItemsTab.chat-handoff.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest"

// Follow existing test patterns from sibling test files for:
// - Mocking react-router-dom (useNavigate)
// - Mocking @/services/settings (setSetting)
// - Mocking watchlists service (fetchScrapedItems)
// - Rendering ItemsTab with necessary providers

describe("ItemsTab chat handoff", () => {
  // Test 1: "Chat" button renders in item action bar when an item is selected
  it("shows Chat button in action bar for selected item")

  // Test 2: "Chat" button is disabled when item has no content/summary/title
  it("disables Chat button when item has no usable content")

  // Test 3: Clicking "Chat" calls setSetting and dispatches event
  it("stores handoff payload and dispatches event on Chat click")

  // Test 4: Clicking "Chat" navigates to "/"
  it("navigates to root on Chat click")

  // Test 5: "Chat about selected" button shows correct count
  it("shows Chat about selected with count when items are checked")

  // Test 6: "Chat about selected" is disabled when no items selected
  it("disables Chat about selected when no items are checked")
})
```

**Step 2: Run tests**

Run: `cd apps/packages/ui && npx vitest run src/components/Option/Watchlists/__tests__/ItemsTab.chat-handoff.test.tsx`
Expected: PASS

**Step 3: Commit**

```bash
git add apps/packages/ui/src/components/Option/Watchlists/__tests__/ItemsTab.chat-handoff.test.tsx
git commit -m "test(watchlists): add component tests for Items tab chat handoff"
```

---

### Task 8: Component Tests — Output Preview Drawer Chat Button

**Files:**
- Create: `apps/packages/ui/src/components/Option/Watchlists/__tests__/OutputPreviewDrawer.chat-handoff.test.tsx`

**Step 1: Write the tests**

Follow existing test patterns from sibling test files.

Test cases to cover:

```typescript
describe("OutputPreviewDrawer chat handoff", () => {
  // Test 1: Chat button renders in drawer header when output has content
  it("shows Chat button in drawer header when content is loaded")

  // Test 2: Chat button is disabled when content is not loaded
  it("disables Chat button when content is not loaded")

  // Test 3: Clicking Chat stores payload and navigates
  it("stores handoff payload and navigates to root on click")
})
```

**Step 2: Run tests**

Run: `cd apps/packages/ui && npx vitest run src/components/Option/Watchlists/__tests__/OutputPreviewDrawer.chat-handoff.test.tsx`
Expected: PASS

**Step 3: Commit**

```bash
git add apps/packages/ui/src/components/Option/Watchlists/__tests__/OutputPreviewDrawer.chat-handoff.test.tsx
git commit -m "test(watchlists): add component tests for output drawer chat handoff"
```

---

### Task 9: Final Verification

**Step 1: Run all watchlist tests**

Run: `cd apps/packages/ui && npx vitest run src/components/Option/Watchlists/ src/services/tldw/__tests__/watchlist-chat-handoff.test.ts`
Expected: All PASS

**Step 2: Run type check**

Run: `cd apps/packages/ui && npx tsc --noEmit --pretty 2>&1 | head -50`
Expected: No new errors

**Step 3: Commit any remaining fixes if needed**

---

## File Summary

| File | Action | Purpose |
|------|--------|---------|
| `services/tldw/watchlist-chat-handoff.ts` | Create | Handoff types, normalize, hint builder |
| `services/tldw/__tests__/watchlist-chat-handoff.test.ts` | Create | Unit tests for handoff service |
| `services/settings/ui-settings.ts` | Modify | Add `DISCUSS_WATCHLIST_PROMPT_SETTING` |
| `components/Option/Playground/PlaygroundForm.tsx` | Modify | Detect watchlist handoff on mount + event |
| `components/Option/Watchlists/ItemsTab/ItemsTab.tsx` | Modify | "Chat" button + "Chat about selected" batch action |
| `components/Option/Watchlists/OutputsTab/OutputPreviewDrawer.tsx` | Modify | "Chat about this" button in drawer header |
| `components/Option/Watchlists/__tests__/ItemsTab.chat-handoff.test.tsx` | Create | Component tests for Items tab |
| `components/Option/Watchlists/__tests__/OutputPreviewDrawer.chat-handoff.test.tsx` | Create | Component tests for Output drawer |

All paths are relative to `apps/packages/ui/src/`.
