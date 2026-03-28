# Chat Stream Hang Design

**Problem:** `/chat` can remain on a pending "Thinking..." state for minutes when the streaming request stays active without producing visible assistant text.

**Observed Cause:** The frontend chat streaming wrapper treats any parsed chunk as activity, even when that chunk does not contain renderable assistant text. The same path does not enforce the configured `chatRequestTimeoutMs` as a hard upper bound for streaming chat requests.

**Design:**

1. Add a hard streaming chat request timeout in `TldwChatService.streamMessage()` using the stored `chatRequestTimeoutMs` setting.
2. Replace the hardcoded 30 second local idle timer with a configurable timeout derived from `chatStreamIdleTimeoutMs`.
3. Reset the local idle timer only when a chunk carries visible user-facing progress:
   - assistant text token content
   - reasoning content
   - terminal/error handling remains immediate
4. Preserve existing transport behavior and avoid broader background-proxy changes in this patch.

**Why this scope:** This addresses the reported "Thinking for multiple minutes" failure mode without redesigning the full stream event model or server heartbeat protocol.

**Tests:**

- `TldwChatService.streamMessage()` aborts after configured hard request timeout even if metadata-only chunks continue arriving.
- `TldwChatService.streamMessage()` does not reset its idle timer for metadata-only chunks.
- `TldwChatService.streamMessage()` still streams normal token content successfully.
