# Design: "Chat about this article" for Watchlists

**Date:** 2026-03-13
**Status:** Approved

## Summary

Add a "Chat about this" feature to the Watchlists page that lets users select one or more scraped articles (from Items tab) or rendered outputs (from Outputs tab) and navigate to the chat page with those articles pre-loaded as context in the composer. Users pick their provider/model on the chat page, sessions are persistent by default but deletable.

## Requirements

- Button on individual items in the **Items tab** and on outputs in the **Outputs tab**
- Multi-select support: users can check multiple items and click "Chat about selected"
- Navigates to the chat page (`/`) with article content pre-loaded in the composer
- User picks provider/model on the chat page before sending
- Sessions are persistent by default; user can delete to discard
- Full article `content` is injected; falls back to `summary`, then `title + url`

## Approach: Hybrid — Reuse handoff, extend for multi-article

Reuse the existing media-chat handoff pattern (`media-chat-handoff.ts`, `DISCUSS_MEDIA_PROMPT_SETTING`) but create a **new** watchlist-specific handoff type and setting to avoid breaking existing media handoff consumers.

## Architecture

### New Types

```typescript
// New file or addition to media-chat-handoff.ts

export type WatchlistChatArticle = {
  title?: string
  url?: string
  content: string       // full content, summary, or title fallback
  sourceType: "item" | "output"
  mediaId?: number
}

export type WatchlistChatHandoffPayload = {
  articles: WatchlistChatArticle[]
  mode: "normal"
}
```

### New Setting

```typescript
export const DISCUSS_WATCHLIST_PROMPT_SETTING = defineSetting(
  "tldw:discussWatchlistPrompt",
  undefined as WatchlistChatHandoffPayload | undefined,
  (value) => normalizeWatchlistChatHandoffPayload(value),
  {
    area: "local",
    localStorageKey: "tldw:discussWatchlistPrompt",
    mirrorToLocalStorage: true
  }
)
```

### Handoff Flow

1. User clicks "Chat about this" on a single item, or checks multiple items and clicks "Chat about selected"
2. Build `WatchlistChatHandoffPayload` from selected items
3. Store payload via `setSetting(DISCUSS_WATCHLIST_PROMPT_SETTING, payload)`
4. Dispatch custom event `tldw:discuss-watchlist`
5. Navigate to `/` (chat page)

### Composer Content Format

The `buildWatchlistChatHint()` function concatenates articles into a single string for the composer:

**Single article:**
```
I'd like to discuss this article:

--- "Article Title" ---
URL: https://example.com/article
{full content}
```

**Multiple articles:**
```
I'd like to discuss these articles:

--- Article 1: "First Title" ---
URL: https://example.com/first
{full content}

--- Article 2: "Second Title" ---
URL: https://example.com/second
{full content}
```

This goes into the composer via `setMessageValue()` with `collapseLarge: true` (matching existing pattern). The user can edit before sending.

### Chat Page Integration

Add detection in `PlaygroundForm.tsx` alongside existing media handoff detection:

1. Mount-time: read `DISCUSS_WATCHLIST_PROMPT_SETTING`, apply if present, clear after use
2. Event listener: listen for `tldw:discuss-watchlist` custom event
3. Apply function: call `setChatMode("normal")`, build hint, call `setMessageValue()`
4. If any articles have `mediaId`, optionally call `setRagMediaIds()` so user can toggle RAG

### Session Naming

- Single article: chat session titled `"Chat: {article title}"`
- Multiple articles: `"Chat: {first title} +N more"`
- User can delete session via existing chat deletion UI (no new UI needed for ephemeral option)

## UI Changes

### Items Tab (`ItemsTab.tsx`)

- Add `MessageSquare` icon button in the selected-item action bar (alongside "Open Monitor", "Open Run", etc.)
- When 1+ items are checked via existing checkboxes, show "Chat about selected (N)" in the batch action toolbar
- Button disabled if no items selected (for batch) or no item focused (for single)

### Outputs Tab — OutputPreviewDrawer (`OutputPreviewDrawer.tsx`)

- Add `MessageSquare` icon button in the drawer header `extra` section (alongside Download and Open in New Tab)
- Uses rendered output content as the article content
- `sourceType: "output"` in the payload

## Content Size Handling

- Before handoff, calculate total character count of all selected articles
- If combined content exceeds 80,000 characters, show a confirmation modal:
  - "Selected articles contain {N} characters of content. This may use significant tokens."
  - Options: "Continue with full content", "Use summaries instead", "Cancel"
- "Use summaries instead" swaps `content` for `summary` field on each article

## Fallback Logic

For each article, resolve content in this order:
1. `content` field (full article text)
2. `summary` field
3. `"{title} — {url}"` with note: "Full content not available for this article"
4. `"Untitled article"` if no title either

## Error Handling

- Navigation guard: if user has an active unsaved chat, warn before replacing
- Items with no content, summary, or title: skip with toast notification listing skipped items
- Empty selection: button disabled (no action possible)

## Testing Strategy

### Unit Tests
- `buildWatchlistChatHint()`: single item, multiple items, missing fields, fallback chain
- `normalizeWatchlistChatHandoffPayload()`: valid payloads, invalid payloads, edge cases
- Content size calculation and threshold check

### Component Tests
- Items tab: "Chat about this" button renders in action bar, fires handoff
- Items tab: multi-select toolbar shows "Chat about selected (N)" with correct count
- Output drawer: button renders in header, fires handoff with output content
- Size warning modal appears at threshold, respects user choice

### E2E Tests
- Select single item → click "Chat about this" → chat page loads with article in composer
- Check 2 items → click "Chat about selected" → chat page shows both articles in composer
- Click "Chat about this" on output → chat page shows rendered output in composer

## Scope Exclusions (v1)

- **No "append to existing chat"** — users must select all articles upfront before starting chat. Adding articles to an in-progress chat session is deferred to a future version.
- **No RAG-scoped mode** — chat starts in "normal" mode. Users can manually toggle RAG on the chat page if desired.
- **No backend changes** — all work is frontend-only. The existing `/api/v1/chat/completions` endpoint handles everything.

## Key Files to Modify

| File | Change |
|------|--------|
| `apps/packages/ui/src/services/tldw/media-chat-handoff.ts` | Add `WatchlistChatHandoffPayload` type, `buildWatchlistChatHint()`, `normalizeWatchlistChatHandoffPayload()` |
| `apps/packages/ui/src/services/settings/ui-settings.ts` | Add `DISCUSS_WATCHLIST_PROMPT_SETTING` |
| `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/ItemsTab.tsx` | Add "Chat about this" button and "Chat about selected" batch action |
| `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/OutputPreviewDrawer.tsx` | Add "Chat about this" button in drawer header |
| `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx` | Add watchlist handoff detection (mount + event listener) |
