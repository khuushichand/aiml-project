# Design: Cross-Workspace Prompt Search via CommandPalette

**Issue:** rmusser01/tldw_server#1043
**Date:** 2026-04-09

## Problem

Search on the `/prompts` page is scoped to the active workspace tab. Users cannot search across Custom prompts (local) and Studio project prompts (server) simultaneously. The existing Cmd+K command palette shows only ~10 recent/favorite prompts statically.

## Solution

Extend the existing `CommandPalette` (Cmd+K) with live cross-workspace prompt search. When the user types a query, the palette searches both local IndexedDB prompts and server prompts in parallel, showing unified results with source labels.

## Changes

### 1. CommandPalette.tsx — add `onQueryChange` callback

New prop: `onQueryChange?: (query: string) => void`

Called on every input change alongside the existing internal `setQuery`. This lets the parent react to the query without the palette needing to know about search internals.

### 2. usePromptPaletteCommands.ts — accept `query`, return dynamic results

Current: Returns static array of ~10 recent/favorite prompts.

New: Accepts `query: string` param. When `query.length >= 2`:
- **Local search**: Filters cached `getAllPrompts()` data in-memory (title, content, tags match)
- **Server search**: Calls `searchPromptsServer({ searchQuery, searchFields: [...], page: 1, resultsPerPage: 15 })` via React Query with 300ms staleTime
- **Deduplication**: Local prompts with matching `serverId` suppress duplicate server results
- **Result format**: `CommandItem[]` with `category: "prompt"`, source in `description`

When `query.length < 2`: Returns existing static favorites/recent (current behavior).

### 3. Layout.tsx — wire query state

Add `const [paletteQuery, setPaletteQuery] = useState("")` in Layout.
Pass `onQueryChange={setPaletteQuery}` to `CommandPaletteHost`.
Pass `query: paletteQuery` to `usePromptPaletteCommands(paletteQuery)`.

## Result Item Shape

```typescript
{
  id: "prompt-search-local-abc123",
  label: "Research Analyst",
  description: "Local prompt",
  icon: <FileText className="size-4" />,
  category: "prompt",
  keywords: ["research", "analysis"],
  action: () => navigate("/prompts?prompt=abc123")
}
```

Server results:
```typescript
{
  id: "prompt-search-server-42",
  label: "Data Parser",
  description: "Studio: ML Pipeline Project",
  icon: <Cloud className="size-4" />,
  category: "prompt",
  keywords: ["data", "parsing"],
  action: () => navigate("/prompts?tab=studio&prompt=42&source=studio")
}
```

## Error Handling

- Server offline/error: Show local results only, no error notification
- Empty results: Palette shows existing "No commands found" message
- Query cleared: Revert to static favorites/recent

## Verification

1. Open Cmd+K, type "research" — see results from both local and server
2. Click a local result — navigates to `/prompts` and opens the prompt
3. Click a server result — navigates to `/prompts?tab=studio` and opens it
4. Go offline, type query — see local results only, no error
5. Existing palette functionality unchanged (navigation, actions, settings)
