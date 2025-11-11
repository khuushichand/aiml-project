# Graphing-Notes-PRD

Status: Draft (MVP scope agreed)
Owner: Notes/RAG Team
Last updated: 2025-11-11 (amended)
Target Release: v0.2.x

## 1. Problem Statement

Users want to visually explore how their notes relate to each other (links, tags, sources, and later similarity) to discover structure, navigate context, and spot clusters. Today there is no server-side API to compute and deliver a graph; clients must approximate via multiple calls and local joins.

## 2. Goals

- Provide a simple, performant API to fetch a graph of notes and their connections for rendering in the client.
- Support explicit manual links, detected wikilinks/backlinks, tag and source relationships out of the box.
- Keep graphs bounded and responsive with sane server-side limits and truncation signals.
- Allow clients to filter by edge type, expand from a center note, and control the size of results.
- Do not persist client layouts server-side; clients fully manage views and layouts.

## 3. Non‑Goals (MVP)

- Saving graph layouts or named views on the server.
- Similarity edges (embedding kNN), NER/topic edges, or real-time graph streaming (WebSocket). These appear in Phase 2+.
- Chunk/paragraph-level graphing; MVP is note-level only.
- Cross-user graphs or public graph publishing.

## 4. Users and Use Cases

- Researchers and students: understand clusters of notes by tag/source; navigate context from a focal note.
- Writers: map ideas and references via manual and wikilinks.
- Engineers/PMs: see connections within a project notebook.

Common flows:
- Open a note → view ego network (neighbors, radius=1) with tag/source nodes visible.
- Search notes → render filtered subgraph by tag or source; toggle edge types.
- Manually add a link between two notes from the graph surface.

## 5. Scope

MVP includes:
- Derived edges: wikilinks/backlinks, note↔tag, note↔source (visible by default).
- Explicit edges: manual links (undirected by default; directed optional).
- Graph fetch endpoints with filters, limits, truncation flags, and pagination cursor.
- Basic create/delete endpoints for manual links with RBAC and rate limits.

## 6. Requirements

### 6.1 Functional Requirements (FR)

1. FR-GraphFetch: Provide `GET /api/v1/notes/graph` returning nodes and edges with filters: `center_note_id?`, `radius=1`, `edge_types`, `tag?`, `source?`, `time_range?`, and size limits.
2. FR-EgoNeighbors: Provide `GET /api/v1/notes/{note_id}/neighbors` equivalent to radius=1 with the same filters/limits.
3. FR-ManualLink-Create: Provide `POST /api/v1/notes/{note_id}/links` to create a manual link to another note. Default `directed=false`.
4. FR-ManualLink-Delete: Provide `DELETE /api/v1/notes/links/{edge_id}` to remove an explicit link.
5. FR-DerivedEdges: Server computes derived edges on demand: wikilinks/backlinks, note↔tag, note↔source.
6. FR-Defaults: Edge types above are visible by default. Manual links are undirected by default.
7. FR-Limits: Enforce sane default limits (nodes, edges, max-degree) and return `{ truncated, truncated_by[], has_more, cursor }` when pruning occurs.
8. FR-Formats: Support default JSON and optional Cytoscape-compatible format via `format=cytoscape`.
9. FR-RBAC: Enforce privileges for read/write operations with appropriate rate limits.

### 6.2 Non‑Functional Requirements (NFR)

1. NFR-Performance: For default limits, 95p graph generation latency ≤ 300 ms on average hardware and datasets ≤ 10k notes per user.
2. NFR-Scalability: Hard caps to prevent pathological queries; deny requests that exceed 2× defaults unless `allow_heavy=true` and caller has admin role.
3. NFR-Reliability: Deterministic pagination with stable ordering; safe truncation strategy.
4. NFR-Observability: Log node/edge counts, types, truncation reasons, and latency; basic counters per edge type.
5. NFR-Security: Respect per-user isolation; validate note ownership; no sensitive content in logs.

## 7. Terminology

- Node types: `note`, `tag`, `source`.
- Edge types: `manual` (explicit), `wikilink`, `backlink`, `tag_membership` (note↔tag), `source_membership` (note↔source).
- Clique mode: Optional conversion of co-membership into note↔note edges (off by default in MVP).

## 8. Data Model Changes

Add support for explicit edges (per-user, within `ChaChaNotes.db`). Do not persist derived edges.

Table: `note_edges`
- `edge_id TEXT PRIMARY KEY`
- `user_id TEXT NOT NULL`
- `from_note_id TEXT NOT NULL`
- `to_note_id TEXT NOT NULL`
- `type TEXT NOT NULL` (values: `manual`)
- `directed INTEGER NOT NULL DEFAULT 0`
- `weight REAL DEFAULT 1.0`
- `created_at DATETIME NOT NULL`
- `created_by TEXT`
- `metadata JSON`

Undirected canonicalization and uniqueness:
- For `directed = 0` (undirected), store endpoints in canonical order: `from_note_id = min(note_a, note_b)` and `to_note_id = max(note_a, note_b)` (lexicographic by UUID). This guarantees uniqueness regardless of creation order.

Indexes:
- `idx_note_edges_user_from_to` on `(user_id, from_note_id, to_note_id)`
- `idx_note_edges_user_type` on `(user_id, type)`
- `idx_note_edges_user_to` on `(user_id, to_note_id)` (accelerates reverse lookups)
- Unique constraint for undirected manual links: `(user_id, type, directed, from_note_id, to_note_id)` after canonicalization

Deletion model:
- Hard delete is acceptable for MVP. Optionally consider soft delete (`deleted_at`) later to align with note recovery semantics.

Derived indices (computed at note save/update):
- Wikilinks/backlinks detection from content (`[[id:UUID]]` or `[[Title]]` match + title resolution).
- Tag and source lookup reuse existing note metadata/tables.

## 9. API Design

### 9.1 Endpoints

1) GET `/api/v1/notes/graph`
- Query params:
  - `center_note_id?`: UUID of focal note.
  - `radius`: integer, default 1; 2 allowed with stricter caps (see Limits). Expansion uses BFS with deterministic ordering.
  - `edge_types`: repeated or CSV; allowed values (enum): `manual`, `wikilink`, `backlink`, `tag_membership`, `source_membership` (default: all visible types).
  - `tag?`, `source?`: filter to notes with a specific tag or source id.
  - `time_range?`: `start`, `end` ISO-8601; applied to `note.updated_at` by default.
  - `time_range_field?`: `created_at` | `updated_at`; default `updated_at`.
  - `max_nodes?`, `max_edges?`, `max_degree?`: override within bounds.
  - `format?`: `default` | `cytoscape`.
  - `cursor?`: pagination token from prior response.
  - `allow_heavy?`: boolean; requires admin role; gate higher caps.

- Response (default format):
```json
{
  "nodes": [
    { "id": "note:123", "type": "note", "label": "Title", "created_at": "...", "degree": 7, "tag_count": 3, "primary_source_id": "source:yt:abcd" },
    { "id": "tag:ml", "type": "tag", "label": "ml" },
    { "id": "source:yt:abcd", "type": "source", "label": "YouTube: ..." }
  ],
  "edges": [
    { "id": "e:1", "source": "note:123", "target": "note:456", "type": "manual", "directed": false, "weight": 1 },
    { "id": "e:2", "source": "note:123", "target": "note:789", "type": "wikilink", "directed": true },
    { "id": "e:3", "source": "note:123", "target": "tag:ml", "type": "tag_membership", "directed": false }
  ],
  "truncated": false,
  "truncated_by": [],
  "has_more": false,
  "cursor": null,
  "limits": { "max_nodes": 300, "max_edges": 1200, "max_degree": 40 }
}
```

2) GET `/api/v1/notes/{note_id}/neighbors`
- Query params: same filters and limits as graph; implicitly `center_note_id=note_id` and `radius=1`.

3) POST `/api/v1/notes/{note_id}/links`
- Body:
```json
{
  "to_note_id": "note-uuid",
  "directed": false,
  "weight": 1.0,
  "metadata": {"label": "related"}
}
```
- Response: created edge object.

4) DELETE `/api/v1/notes/links/{edge_id}`
- Response: `{ "deleted": true }` if successful.

Notes:
- Cytoscape format: when `format=cytoscape`, return `{ elements: { nodes: [...], edges: [...] }, ... }` following Cytoscape.js conventions.

Example (Cytoscape format):
```json
{
  "elements": {
    "nodes": [
      { "data": { "id": "note:123", "label": "Title", "type": "note", "primary_source_id": "source:yt:abcd" }},
      { "data": { "id": "tag:ml", "label": "ml", "type": "tag" }}
    ],
    "edges": [
      { "data": { "id": "e:1", "source": "note:123", "target": "note:456", "type": "manual", "directed": false }},
      { "data": { "id": "e:3", "source": "note:123", "target": "tag:ml", "type": "tag_membership", "directed": false }}
    ]
  },
  "truncated": false,
  "has_more": false
}
```

### 9.2 Schemas (Pydantic)

- `NoteLinkCreate`: `{ to_note_id: str, directed: bool = false, weight?: float, metadata?: dict }`
- `NoteGraphRequest`: `{ center_note_id?: str, radius: int = 1, edge_types?: List[Literal["manual","wikilink","backlink","tag_membership","source_membership"]], tag?: str, source?: str, time_range?: {start?: datetime, end?: datetime}, time_range_field?: Literal["created_at","updated_at"] = "updated_at", max_nodes?: int, max_edges?: int, max_degree?: int, format?: Literal["default","cytoscape"], cursor?: str, allow_heavy?: bool }`
- `NoteGraphResponse`: `{ nodes: List[Node], edges: List[Edge], truncated: bool, truncated_by: List[str], has_more: bool, cursor?: str, limits: {...} }`
- `Node`: `{ id: str, type: Literal["note","tag","source"], label: str, created_at?: str, degree?: int, tag_count?: int, primary_source_id?: str }`
- `Edge`: `{ id: str, source: str, target: str, type: str, directed: bool, weight?: float, label?: str }`

### 9.3 Errors

- 400: invalid params (e.g., negative radius, unsupported edge type)
- 403: lacking privilege for operation
- 404: note not found or not owned by user
- 409: duplicate manual link (same endpoints, type, and direction)
- 413: request too large (exceeds caps without `allow_heavy`)
- 422: invalid `edge_types` value(s) or incompatible parameter combination

## 10. Defaults, Limits, and Pruning

Sane defaults (configurable):
- `NOTES_GRAPH_MAX_NODES=300`
- `NOTES_GRAPH_MAX_EDGES=1200` (≈4× nodes)
- `NOTES_GRAPH_MAX_DEGREE=40`
- `NOTES_GRAPH_DEFAULT_RADIUS=1`
- Per-type soft caps within max_nodes: note≤250, tag≤75, source≤50 (subject to tuning). These are ceilings within the global `max_nodes`.

Enforcement model:
- Expansion uses BFS layers from `center_note_id` (or a filtered seed set), enforcing `max_degree` per node at expansion time, with deterministic ordering.
- Deterministic ordering: for note neighbors, sort by `updated_at DESC, id ASC`; for tag/source neighbors, sort by `label ASC, id ASC`.
- If the sum of per-type ceilings exceeds `max_nodes`, downscale proportionally by type with deterministic tie-breaking (id ASC).

Pruning order when over limits:
- Co-membership cliques (if enabled) → low-weight tag/source edges → older wikilinks → manual links last.

Cursor semantics:
- Always return truncation metadata and a `cursor` when pruning occurs. The cursor encodes the last expanded layer and position, supporting stable continuation with the ordering above.

Radius=2 caps:
- Unless `allow_heavy=true` (admin), enforce stricter caps when `radius=2`: `max_nodes ≤ 200`, `max_edges ≤ 800`, `max_degree ≤ 20`.

Multi-edge semantics:
- The graph is a multigraph: different edge types between the same endpoints (e.g., `manual` + `wikilink`) are emitted as separate edges with distinct ids. Clients may coalesce for rendering if desired.

## 11. Config and Feature Flags

Config keys (env → config.txt → defaults):
- `NOTES_GRAPH_ENABLED=true`
- `NOTES_GRAPH_MAX_NODES=300`
- `NOTES_GRAPH_MAX_EDGES=1200`
- `NOTES_GRAPH_MAX_DEGREE=40`
- `NOTES_GRAPH_DEFAULT_RADIUS=1`
- `NOTES_GRAPH_POPULAR_TAG_CUTOFF=0.15` (ignore tags used by >15% of notes for tag edges)
- `NOTES_GRAPH_CLIQUE_MIN_SHARED_TAGS=2` (used only if clique mode is added later)
- `NOTES_GRAPH_MAX_CLIQUE_EDGES=400` (future guardrail)
- `NOTES_GRAPH_CACHE_TTL=20` (seconds)
- `NOTES_GRAPH_CACHE_MAX_KEYS=1000`

## 12. Security, AuthNZ, RBAC, Rate Limits

- Per-user isolation: all queries scoped to the authenticated user; validate note ownership for manual link writes.
- Required privileges (add to `tldw_Server_API/Config_Files/privilege_catalog.yaml`):
  - `notes.graph.read` (standard rate limit class)
  - `notes.graph.write` (stricter rate limit class)
  - `notes.graph.suggest` (Phase 2, standard)
- Rate limits should follow existing `rbac_rate_limit(...)` mechanism across endpoints.

Token scopes:
- When a JWT is presented, require the `notes` scope; when no token is present (single-user mode), proceed with RBAC checks only. Implementation follows `require_token_scope("notes", require_if_present=True)`.

## 13. Performance and Caching

- Compute derived edges on demand with fast lookups and small caps (e.g., max neighbors per note, popular tag cutoff). For scale, consider store-time indexing of wikilinks/backlinks and lightweight adjacency caches to maintain p95 targets.
- Cache recent graph results per query key for 10–30 seconds to smooth repeated expansions.
- Include simple metrics: counts per edge type, generation time, truncation reasons.

## 14. UX and Client Integration

- Libraries: Cytoscape.js or Sigma.js (Graphology) in `tldw-frontend`.
- Edge visibility: default to showing manual, wikilinks/backlinks, tag membership, and source membership.
- Manual link creation from graph UI posts to `POST /notes/{note_id}/links`.
- Layouts: client-managed (no server persistence). Provide `format=cytoscape` for direct rendering.
- Interactions: click node → open note; double-click/command-click → expand neighbors; chips/toggles for edge types.

## 15. Dependencies & Integration Points

- Notes storage (ChaChaNotes.db) and tagging/source metadata.
- Wikilink/backlink detection uses existing note content storage and title resolution.
- AuthNZ + RBAC for privileges and rate limits.

Resolution details:
- Wikilinks: `[[id:UUID]]` resolves directly. `[[Title]]` resolution prefers (1) exact title match in the same notebook/folder, (2) most recently updated note with that title, then (3) lowest UUID as final tie-breaker. Unresolved titles do not emit edges in MVP.
- Popular tag cutoff: apply both relative and absolute thresholds. Ignore tags used by > `NOTES_GRAPH_POPULAR_TAG_CUTOFF` of notes AND with usage count ≥ 10 (default) to avoid over-pruning on small datasets.
- Source nodes: represent primary content origin (e.g., `source:yt:<video_id>`, `source:url:<domain>`). ID format is implementation-defined but must be stable; expose human-readable `label`.

## 16. Risks and Mitigations

- Dense graphs (hairballs) degrade UX → enforce max nodes/edges/degree; provide truncation signals.
- Popular tags create hubs → ignore ubiquitous tags via `NOTES_GRAPH_POPULAR_TAG_CUTOFF`.
- Large sources (e.g., many notes from same source) → treat as bipartite edges by default; avoid note↔note co-origin cliques.
- Performance regressions under radius=2 → reduce caps and/or require `allow_heavy`.

## 17. Rollout Plan

1. Implement DB table, schemas, endpoints, and guardrails.
2. Add privilege catalog entries; wire `rbac_rate_limit`.
3. Add unit and integration tests; verify perf locally with synthetic data.
4. Add minimal docs under `Docs/Notes/Graph.md` and link from README.
5. Release behind `NOTES_GRAPH_ENABLED` (true by default); monitor metrics.

## 18. Testing and Acceptance Criteria

### 18.1 Test Plan

- Unit tests:
  - Manual link create/delete; duplicate prevention; undirected default semantics.
  - Wikilink/backlink parsing from content; title resolution edge cases.
  - Tag/source membership edge generation with popular-tag cutoff.
- Integration tests:
  - `GET /notes/graph` default filters; radius=1; truncation flags at limits.
  - Ego neighbors for a center note; correct node/edge counts and types.
  - RBAC: read vs write privileges; rate-limited suggest (Phase 2 placeholder).
  - Pagination/cursor continuity under stable order.
- Performance checks:
  - Default query ≤ 300 ms p95 on representative dataset; enforce caps.

### 18.2 Acceptance Criteria

- AC1: With defaults, `GET /notes/graph` returns nodes and edges including manual, wikilinks/backlinks, tag, and source relationships, with truncation fields present.
- AC2: Creating a manual link yields an undirected edge unless `directed=true` is specified.
- AC3: `GET /notes/{id}/neighbors` returns radius=1 ego network consistent with the graph endpoint.
- AC4: Limits (`max_nodes`, `max_edges`, `max_degree`) are enforced; responses indicate truncation and provide a usable cursor.
- AC5: RBAC/Rate limits enforced per privilege; unauthorized access is rejected appropriately.

## 19. Phase 2+ (Not in MVP)

- Similarity edges (embedding-based kNN) with `NOTES_GRAPH_SIMILARITY_ENABLED`, `K`, and `THRESHOLD` settings.
- LLM/heuristic link suggestions: `POST /api/v1/notes/graph/suggest` with strategy flag and rate limit `notes.graph.suggest`.
- Optional NER/topic co-mention edges.
- WebSocket for realtime upserts of nodes/edges.
- Server-side saved views (filters/layout seeds) if demanded by users.

## 20. Open Questions

- Exact popular-tag cutoff default (start at 0.15, tune with telemetry).
- Source node labeling conventions and maximum number in default responses.
- Whether to expose "clique mode" for tag/source co-membership as an advanced toggle post-MVP.

## 21. Implementation Notes (Appendix)

- BFS expansion and ordering
  - Perform BFS starting from `center_note_id` (when provided) or a seed set filtered by `tag`/`source`.
  - Per-node neighbor ordering (stable): notes by `updated_at DESC, id ASC`; tags/sources by `label ASC, id ASC`.
  - Enforce `max_degree` at expansion time to bound frontiers deterministically.

- Cursor encoding
  - Cursor represents the last expanded layer and the last processed neighbor position within that layer.
  - Recommended encoding: base64-encoded JSON: `{ "layer": <int>, "pos": <int>, "last_id": "<id>" }` with optional filters snapshot for validation.
  - On resume, reconstruct the frontier and continue from `(layer, pos)` with the same deterministic sort. Reject cursors when filters differ.

- Edge typing and multigraph
  - Preserve separate edges per type between the same endpoints (multigraph). Clients may coalesce visually.

- Undirected uniqueness
  - For `directed=false`, canonicalize manual links by sorting endpoints and enforce unique `(user_id, type, directed, from_id, to_id)` after canonicalization.

- Query parsing (edge_types)
  - Accept both repeated query params and CSV. Normalize to the enum set {manual, wikilink, backlink, tag_membership, source_membership}.
