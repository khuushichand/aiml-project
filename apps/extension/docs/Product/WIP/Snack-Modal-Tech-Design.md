# Snack Modal — Technical Design

## Summary
The Snack Modal is a selection-triggered, in-page Copilot popup that streams a response and optionally replaces the selected text after a confirm preview. It is triggered explicitly via a right-click context menu item. The UI is rendered in a Shadow DOM to avoid page CSS conflicts and communicates with the background via message passing.

## Goals
- Explicit trigger only (context menu selection).
- Streaming response in a small anchored popup.
- Confirmed replace flow for editable selections.
- Safe fallback to open the sidepanel.

## Non-Goals
- Auto-popup on selection.
- Multi-range selection support.
- Rich-text replacement.
- Full-page translation.

---

## Architecture

### Components
- **Background**: Adds context menu item; dispatches `tldw:popup:open` to the active tab/frame.
- **Content Script Host**: Listens for open messages; captures selection; mounts/unmounts the popup; positions it.
- **Popup UI**: React component tree rendered in Shadow DOM; manages streaming, preview, replace, and close actions.
- **Streaming Service**: Dedicated `TldwChatService` instance per content script.
- **Selection Replace Helpers**: Utility for inputs/textareas and contenteditable replacement.

### Message Flow
1) User selects text → right-click → `tldw > Contextual action`.
2) Background handles click and calls `tabs.sendMessage` → `{ type: 'tldw:popup:open', payload }`.
3) Content script receives message, captures selection + anchor rect, mounts popup.
4) Popup triggers streaming via `TldwChatService.streamMessage`.
5) On stream completion, popup shows preview and “Replace selection” if applicable.
6) User replaces selection or closes popup. Optional “Open sidepanel.”

---

## Content Script Details

### Selection Capture
- Use `window.getSelection()` and `Range` for anchor rect.
- Capture `selectionText` from `Selection.toString()`.
- Determine replacement target:
  - `textarea` / `input` with a selection range.
  - `contenteditable` ancestor containing the selection range.

### Positioning
- Anchor via `range.getBoundingClientRect()`.
- Clamp to viewport with padding.
- Recompute on `scroll` and `resize` via `requestAnimationFrame` throttling.

### Popup Host
- Inject a single root container per frame.
- Attach Shadow DOM and inject scoped styles.
- Unmount on close and clean event listeners.

---

## Streaming

### Service
- Use `TldwChatService` in content script; do not reuse sidepanel state.
- Read model from storage (`selectedModel` in extension storage).
- Cancel on close, Stop, or new trigger.
- Cleanup on unmount and frame navigation:
  - Register `pagehide` and `beforeunload` listeners to cancel active streams and unmount the popup.
  - On content script teardown, call a `dispose()`/`stop()` on `TldwChatService`, disconnect any ports, and clear timers.
  - Remove listeners when popup unmounts to avoid leaks if the popup is reopened.

### Error Handling & Retry
- Distinguish error states and surface specific messages:
  - `noModel`: “Select a model to continue.”
  - `network`: “Network error — check your connection.”
  - `timeout`: “Stream timed out — try again.”
  - `server`: “Model error — try again or pick a different model.”
  - `canceled`: “Streaming stopped.”
- Retry policy:
  - Offer a “Retry” action for `network`, `timeout`, and `server` errors.
  - Do not auto-retry on `noModel` or `canceled`.
  - Use a requestId to ignore late chunks from a canceled stream.

### Timeouts & Resource Limits
- `streamInactivityTimeoutMs`: cancel if no chunk arrives within 30s (configurable).
- `maxStreamDurationMs`: cancel after 2 minutes total (configurable).
- `maxOutputChars`: cap buffered output (e.g., 8k chars) to prevent memory growth.
- If limits are hit, stop streaming, surface a timeout/limit message, and allow Retry.

### Payload
- Build a single user message containing selected text.
- Optional system prompt: “Respond helpfully to the selected text.”

---

## Replace Confirmation

### Inputs / Textareas
- Use `setRangeText(previewText, start, end, 'end')` to preserve undo.

### Contenteditable
- `range.deleteContents()` + `range.insertNode(document.createTextNode(previewText))`.
- Collapse selection to end.

### Guardrails
- Disable Replace if selection target is invalid or detached.

---

## UI States
- **Idle**: popup opens, no stream started yet.
  - Show a lightweight skeleton/ellipsis and disable Replace.
  - Fast transition: if the first chunk arrives within 100ms, skip Idle render.
  - Actions: Close only.
- **Streaming**: enter when the first chunk arrives (or after 100ms if still pending).
  - Incremental text updates + spinner; Stop and Close available.
  - Replace is disabled; Copy can be enabled for partial text if desired.
- **Done**: response complete or canceled.
  - Preview presentation: side-by-side “Original” vs “Proposed” with inline highlights.
  - Actions: Replace (if eligible), Copy, Open sidepanel, Close, Retry.
- **Error**: stream failure or no model selected.
  - Show specific error message; actions: Retry, Open sidepanel, Close.

---

## Files & Ownership

### New Files
- `src/entries/copilot-popup.content.tsx`
- `src/components/CopilotPopup/*` (or colocated in the content script)
- `src/utils/selection-replace.ts`

### Modified Files
- `src/entries/shared/background-init.ts` (menu item)
- `src/entries/background.ts` (menu click handling)
- `src/assets/locale/en/*.json` (strings)

---

## i18n Keys (proposed)
- `contextCopilotPopup` → “Contextual action”
- `popupStop` → “Stop”
- `popupOpenSidepanel` → “Open sidepanel”
- `popupCopy` → “Copy”
- `popupReplace` → “Replace selection”
- `popupCancel` → “Cancel”
- `popupNoSelection` → “No selection found”
- `popupNoModel` → “Select a model to continue”
- `popupStreaming` → “Streaming…”

---

## Risks
- Cross-origin frames may block selection capture → fallback to sidepanel.
- Styling collisions if Shadow DOM isn’t used.
- Replacement correctness in complex `contenteditable` trees.
- Navigation during streaming (SPA route changes/back/forward) → cancel stream on `pagehide`/`beforeunload`/`popstate`, close popup, and show “Selection no longer valid.”
- Multiple rapid triggers → debounce context menu actions, cancel previous stream, and ignore stale responses by requestId.
- Performance on low-end devices / large documents → throttle DOM updates, cap output length, and delay diffing until Done.
- Browser compatibility (Shadow DOM/selection APIs) → detect `attachShadow` and fall back to scoped light-DOM styles if missing.
- Extension context invalidation (extension reload) → catch `chrome.runtime.lastError`, surface a recoverable error, and require a reopen.
- Injection restrictions (chrome://, view-source:, PDFs) → detect disallowed URLs and route to sidepanel.

---

## Testing
- Manual: context menu availability, streaming, replace in input/textarea/contenteditable.
- Unit: selection replacement helper logic, range-to-target detection.
- E2E (required): selection → popup → stream → preview → replace.
- Edge cases: multiple frames, cross-origin iframes, dynamic DOM changes, rapid triggers, navigation during streaming.
- Error conditions: network failures, model errors, invalid selections, detached elements.
- Accessibility: keyboard navigation, focus management, screen reader announcements for streaming/done/error.
- Browser compatibility: Shadow DOM support, Selection API differences (Chrome/Firefox/Edge).
- Performance: large documents, long-running streams, memory leak detection.
