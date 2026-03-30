# MCP Context Search and Retrieval (FTS-first)

Version: v0.1 (implemented)

Author: tldw_server2 team

Status: Implemented (core modules and aggregator available)

## Overview

This design adds context7-like functionality via MCP tools to search and retrieve per-user Notes, Media, Chats, Characters, and Prompts using existing SQLite/FTS indices and DB abstractions. It provides:

- Per-source MCP tools for search/get
- Cross-source aggregator tools for unified search/get
- Strict per-user database derivation (no cross-user access)
- Normalized scoring (0-1) across sources
- Configurable snippet length (default 300)
- Retrieval modes: snippet, chunk, chunk_with_siblings (budgeted), full

Initially, only FTS/keyword search is implemented (no vectors). Later versions can add re-ranking/embeddings without breaking caller contracts. The following are implemented in code now: Notes, Media, Chats, Characters, Prompts source modules, and a Knowledge aggregator with normalized outputs.

## Session & Client Awareness

Add session-aware search and light client adaptation inspired by a reference MCP server:

- Per-session state keyed by `RequestContext.session_id` (WS) or `mcp-session-id` (HTTP). Store a bounded set of previously returned URIs to avoid repeating identical results across successive searches, plus a small recent query history to bias snippets.
- HTTP sessions: accept an optional `mcp-session-id` header or query param. If missing on first initialize, generate one and include it in the response (design-only; implementation later). Optionally support session cleanup via HTTP DELETE with the same header.
- Client detection: read `initialize.params.clientInfo.name` and save in `RequestContext.metadata.client` for compatibility tweaks (e.g., tool aliases or alternate output shapes for specific clients).
- Optional client aliases: when a client requires deep-research naming, expose `search` (alias of `knowledge.search`) and `fetch` (alias of `knowledge.get`). Canonical tools remain available.

## Security & Per-User Enforcement

- MCPProtocol injects immutable per-request `_context` with `{ user_id, client_id, db_paths }` derived from authentication (AuthNZ JWT or API key). Callers cannot supply/override these.
- DB paths are resolved via `DatabasePaths`:
  - `media`: `DatabasePaths.get_media_db_path(user_id)`
  - `chacha`: `DatabasePaths.get_chacha_db_path(user_id)` (Notes, Chats, Characters)
  - `prompts`: `DatabasePaths.get_prompts_db_path(user_id)`
- In single-user mode, `user_id = DatabasePaths.get_single_user_id()`.
- Modules use `_context.db_paths` and never accept `user_id` in input.

## Safe, Per-Request Config (Non-secret)

Permit an optional base64-encoded `config` JSON on HTTP requests. Parsed keys are merged as soft defaults into `RequestContext.metadata.config` and can include:

- `snippet_length` (default 300; clamp bounds)
- `max_tokens` (default ~5000; clamp bounds)
- `sibling_window` (default 1-2; clamp bounds)
- `order_by` ("relevance" | "recent")
- `chars_per_token` (default 4)

Never accept credentials or cross-user hints in this config. WS can pass similar knobs in the first `initialize`.

## Sources & Tools

Implemented sources (read-only v1): `notes`, `media`, `chats`, `characters`, `prompts`.

Each source provides `search` and `get` tools (see schemas). An `aggregator` provides `knowledge.search` and `knowledge.get` to fan-out and normalize across sources.

Read-only hint: include `metadata.readOnlyHint = true` in tool definitions for search/get tools to help UI surfaces.

## Result Schema (Common)

All search results return items with a shared shape:

```
ResultItem = {
  "id": string | number,              // source-native ID
  "source": "notes"|"media"|"chats"|"characters"|"prompts",
  "title": string | null,            // best effort short title/name
  "snippet": string | null,          // <= snippet_length chars; plain text
  "uri": string,                     // canonical pointer (e.g., media://123)
  "score": number,                   // 0..1 normalized
  "score_type": "fts",              // v1
  "created_at": string | null,       // ISO 8601
  "last_modified": string | null,    // ISO 8601
  "version": number | null,
  "tags": string[] | null,
  // optional per-source fields below
  "media_type": string | null,       // media only
  "url": string | null,              // media only
  "conversation_id": string | null,  // chats
  "message_id": string | null,       // chats
  "sender": string | null,           // chats
  // location hint for follow-up retrieval
  "loc": {
    // precise meaning varies per source (see below)
  } | null
}
```

List response:

```
SearchResponse = {
  "results": ResultItem[],
  "has_more": boolean,
  "next_offset": number | null,
  "total_estimated": number | null
}
```

Get response:

```
GetResponse = {
  "meta": ResultItem,
  "content": string | object,      // primary content, possibly chunked
  "attachments": object[] | null   // transcripts, message lists, etc.
}
```

## Scoring Normalization (0-1)

- PostgreSQL: use `ts_rank(...)`; normalize by dividing by per-query max `ts_rank` in the result set.
- SQLite/FTS5: when available, use `bm25(table)`; map to 0-1 via:
  - `score = (max_bm25 - bm25) / (max_bm25 - min_bm25 + 1e-9)`
  - If BM25 unavailable, fallback to positional decay: `score = 1 / (1 + rank_index)`
- Aggregator merges by normalized score, then by `last_modified` (desc) if `order_by=relevance` (default). `order_by=recent` sorts purely by recency.

## Snippets

- `snippet_length` is configurable (default 300; max clamp e.g., 1,000).
- Prefer fragment centered on first match; otherwise the first `snippet_length` chars.
- Plain text only; collapse whitespace.
- Chats: if message-level match, use the message content; if title match, show conversation title with first message excerpt.
  The `snippet_length` can be supplied via tool input or the safe request config.

## Retrieval Modes

Expose a `retrieval` object for `get` tools and the aggregator `knowledge.get`:

```
RetrievalOptions = {
  "mode": "snippet" | "chunk" | "chunk_with_siblings" | "full" | "auto",  // default "snippet"
  "snippet_length": number,              // optional; overrides default
  "max_tokens": number,                  // budget for chunk_with_siblings
  "chars_per_token": number,             // default 4 (approximation)
  "chunk_size_tokens": number,           // on-the-fly chunking when not prechunked
  "chunk_overlap_tokens": number,        // when chunking
  "sibling_window": number,              // number of chunks on each side to consider
  "prefer_prechunked": boolean           // default true for Media
}
```

Behavior:
- `snippet`: return only snippet (respecting `snippet_length`).
- `chunk`: return the best-matching chunk around the `loc` anchor.
- `chunk_with_siblings`: expand from the anchor chunk to left/right siblings while estimated token sum ≤ `max_tokens`.
- `full`: return full item content (subject to sane hard caps and pagination for huge items).
- `auto`: choose `chunk_with_siblings` when `max_tokens` is present, else `snippet`.

Token estimation uses `chars_per_token` as a multiplier to convert characters → tokens (`tokens ≈ ceil(chars / cpt)`).

Anchor identification (`loc`):
- `media`: prefers stored chunks from `UnvectorizedMediaChunks` (by `chunk_index` or `uuid`). When a prechunked table exists, `media.search` attempts to map the first match offset to a precise `loc.chunk_index`; `media.get` uses `chunk_index`/`chunk_uuid` to anchor and then expands to siblings under the token budget. If no prechunked chunks exist, it falls back to on-the-fly chunking with approximate offsets.
- `notes`: FTS match → approximate offset or sentence-chunk boundary (on-the-fly chunking with `Chunker`).
- `chats`: treat each message as a “chunk”; siblings are adjacent messages. The anchor is `message_id`.
- `characters`/`prompts`: if needed, chunk on-the-fly by sentences/paragraphs.

## Media Types

- Suggested list to display in UIs:
  - `video`, `audio`, `podcast`, `pdf`, `epub`, `docx`, `pptx`, `html`, `markdown`, `txt`, `image`, `article`
- Dynamic discovery via a resource (`media://types`) using `get_distinct_media_types()`.

## Tool Schemas

All tools accept standard pagination: `limit` (1..100; default 10), `offset` (>=0; default 0).

### Notes

```
notes.search
  input: {
    "query": string,
    "limit"?: number,
    "offset"?: number,
    "snippet_length"?: number,
    "keywords"?: string[]
  }
  output: SearchResponse

notes.get
  input: {
    "note_id": string,
    "retrieval"?: RetrievalOptions
  }
  output: GetResponse
```

### Media

```
media.search
  input: {
    "query": string,
    "limit"?: number,
    "offset"?: number,
    "snippet_length"?: number,
    "media_types"?: string[],        // suggested list or free-form
    "date_from"?: string,            // ISO 8601
    "date_to"?: string,
    "order_by"?: "relevance"|"recent"  // default "relevance"
  }
  output: SearchResponse

media.get
  input: {
    "media_id": number | string,
    "retrieval"?: RetrievalOptions
  }
  output: GetResponse

media.transcript
  input: {
    "media_id": number | string,
    "format"?: "text"|"srt"|"vtt"|"json",
    "include_timestamps"?: boolean
  }
  output: { "content": string | object }
```

### Chats

```
chats.search
  input: {
    "query": string,
    "limit"?: number,
    "offset"?: number,
    "snippet_length"?: number,
    "by"?: "both"|"title"|"message",   // default "both"
    "character_id"?: number,
    "sender"?: string
  }
  output: SearchResponse

chats.get
  input: {
    "conversation_id": string,
    "page"?: number,            // default 1
    "page_size"?: number,       // default 50; cap reasonable (e.g., 200)
    "retrieval"?: RetrievalOptions  // if present and mode != full, can limit messages window around anchor
  }
  output: GetResponse
```

### Characters

```
characters.search
  input: {
    "query": string,            // text or tags (comma-separated or list)
    "limit"?: number,
    "offset"?: number,
    "snippet_length"?: number
  }
  output: SearchResponse

characters.get
  input: { "character_id": number }
  output: GetResponse
```

### Prompts

```
prompts.search
  input: {
    "query": string,
    "limit"?: number,
    "offset"?: number,
    "snippet_length"?: number,
    "fields"?: ("name"|"details"|"system_prompt"|"user_prompt"|"author"|"keywords")[]
  }
  output: SearchResponse

prompts.get
  input: { "prompt_id_or_name": string }
  output: GetResponse
```

### Aggregator

```
knowledge.search
  input: {
    "query": string,
    "limit"?: number,                  // default 20
    "offset"?: number,
    "snippet_length"?: number,
    "sources"?: ("notes"|"media"|"chats"|"characters"|"prompts")[],  // default all
    "order_by"?: "relevance"|"recent",
    "filters"?: {
      "media"?: { "media_types"?: string[], "date_from"?: string, "date_to"?: string, "order_by"?: "relevance"|"recent" },
      "notes"?: { "keywords"?: string[] },
      "chats"?: { "by"?: "both"|"title"|"message", "character_id"?: number, "sender"?: string },
      "prompts"?: { "fields"?: string[] },
      "characters"?: { /* reserved */ }
    }
  }
  output: SearchResponse

knowledge.get
  input: {
    "source": "notes"|"media"|"chats"|"characters"|"prompts",
    "id": string | number,
    "retrieval"?: RetrievalOptions
  }
  output: GetResponse

Notes
- `media.search` now returns a more precise `loc` when prechunked data exists: `{ "chunk_index": N }` rather than only `{ "approx_offset" }`.
- `media.get` prefers `UnvectorizedMediaChunks` for `mode = "chunk" | "chunk_with_siblings" | "auto"`. It anchors by `chunk_index` or `chunk_uuid` when provided, otherwise maps an `approx_offset` to a `chunk_index`. If prechunked data is not available, it falls back to on-the-fly chunking.
```

## Location (loc) Semantics by Source

- media: `{ media_id, chunk_index?: number, chunk_uuid?: string }`
- notes: `{ approx_offset?: number, chunk_index?: number }` (best-effort; may be computed on the fly)
- chats: `{ conversation_id, message_id?: string, message_index?: number }`
- prompts/characters: `{ approx_offset?: number, field?: string }`

When `loc` is missing, `get` will attempt to determine an anchor via a light search in the same source. This is best-effort and may be slower.

## Implementation Notes (v1)

- Reuse DB abstractions:
  - Notes/Chats/Characters: `CharactersRAGDB` (ChaChaNotes)
  - Media: `MediaDatabase`
  - Prompts: `PromptsDatabase`
- Media chunk retrieval uses `UnvectorizedMediaChunks` when present; otherwise falls back to full text or summary slices.
- On-the-fly chunking uses `core/Chunking/Chunker` with sentence method by default; `chunk_size_tokens` and `chunk_overlap_tokens` map to approx chars via `chars_per_token`.
- Rate limits: Per-tool caps via existing MCP rate limiter; read-only tools are allowed for typical roles.
- Logging: Use loguru; do not log secrets or raw PII content.

### Session Store

- Maintain `{ seen_uris: Set<string>, recent_queries: string[], defaults: { snippet_length?, max_tokens?, sibling_window?, order_by?, chars_per_token? } }` per session with TTL and capacity limits.
- Aggregator filters out items already in `seen_uris` (dedupe), then updates the set with newly returned items (bounded growth).
- Preference precedence: explicit tool inputs > session defaults > global defaults.

### Client Aliases & Output Shapes (Optional)

- When `metadata.client` indicates a deep-research client, register aliases `search` → `knowledge.search`, `fetch` → `knowledge.get` in tools.list. Preserve canonical tools.
- If the client requests a compact deep-research shape via a mode flag, return a compact list `{id, title, text, url, metadata}`; otherwise use the canonical schema.

### HTTP Sessions (Design)

- Honor `mcp-session-id` on HTTP requests. Create and return one for first-time sessions. Optionally support an HTTP DELETE to clear the session early; otherwise TTL reaper cleans up.

## Testing

- Unit tests per tool (search/get), ensuring:
  - Per-user isolation (user A cannot see B)
  - Media `media_types` filter
  - Snippet length honored; default is 300
  - `chunk_with_siblings` respects token budget
- E2E tests for MCP over HTTP and WebSocket with minimal fixtures.
 - Session dedupe: repeated searches in a session avoid returning identical URIs until the result space is exhausted.
 - Client aliasing/shape: deep-research mode shows aliases and honors shape toggle.

## Open Items

- Exact `bm25` availability varies by SQLite build; where missing, positional decay fallback applies.
- For notes/prompts/characters, FTS does not return offsets by default; `loc.approx_offset` may be best-effort.
- Very large items: enforce hard caps and pagination for `full` mode to avoid oversized responses; document limits in endpoint help.
