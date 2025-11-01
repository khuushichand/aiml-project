# Notes API

The Notes API provides simple note-taking and keyword linking for per-user knowledge management. Notes are stored in the per-user ChaChaNotes database and are available for RAG retrieval and MCP search.

## Base Path

- `/api/v1/notes`

## Authentication

- Same as the rest of the API. The effective database is resolved from the authenticated user context.

## Endpoints

- `GET /api/v1/notes/health` - Lightweight health signal for the Notes subsystem.

- `POST /api/v1/notes/` - Create a note
  - Body: `{"title": "str", "content": "str", "id?": "uuid", "keywords?": ["tag1", "tag2"] | "tag1, tag2"}`
  - Returns: `NoteResponse`
  - Rate limit: 30 creates/min per user (in-memory limiter)

- `GET /api/v1/notes/{note_id}` - Get a note by id
  - Returns: `NoteResponse`

- `GET /api/v1/notes/` - List notes
  - Query: `limit` (1-1000, default 100), `offset` (>=0), `include_keywords` (bool)
  - Returns: `{ "notes": NoteResponse[], "limit": number, "offset": number, "total"?: number }`

- `PATCH /api/v1/notes/{note_id}` - Partially update a note
  - Body: `{ "title?": "str", "content?": "str" }`
  - Header: `expected-version` (optional). If omitted, server fetches current version and applies optimistic update.
  - Returns: `NoteResponse`

- `PUT /api/v1/notes/{note_id}` - Update a note (full semantics)
  - Body: `{ "title?": "str", "content?": "str" }`
  - Header: `expected-version` (required)
  - Returns: `NoteResponse`

- `DELETE /api/v1/notes/{note_id}` - Soft delete
  - Header: `expected-version` (required)
  - Returns: 204 No Content

- `GET /api/v1/notes/search/` - Search notes by title/content (FTS-backed)
  - Query: `query` (required), `limit` (1-100)
  - Returns: `NoteResponse[]`

- `GET /api/v1/notes/export` - Export notes
  - Query: `q` (optional search), `limit` (default 1000), `offset` (default 0), `include_keywords` (bool), `format` (`json` or `csv`, default `json`)
  - JSON Returns: `{ notes: NoteResponse[], count, total, limit, offset, exported_at }`
  - CSV Returns: text/csv with header row

- `POST /api/v1/notes/export` - Export selected notes
  - Body: `{ note_ids: string[], format?: "json" | "csv", include_keywords?: boolean }`
  - JSON Returns: `{ notes: NoteResponse[], count, exported_at }`
  - CSV Returns: text/csv with header row

### Keywords

- `POST /api/v1/notes/keywords/` - Create keyword
  - Body: `{ "keyword": "str" }`
  - Returns: `KeywordResponse`

- `GET /api/v1/notes/keywords/{keyword_id}` - Get keyword by id
- `GET /api/v1/notes/keywords/text/{keyword_text}` - Get keyword by text
- `GET /api/v1/notes/keywords/` - List keywords (limit/offset)
- `GET /api/v1/notes/keywords/search/?query=...` - Search keywords (FTS-backed)
- `DELETE /api/v1/notes/keywords/{keyword_id}` - Soft delete keyword (header `expected-version`)

### Linking

- `POST /api/v1/notes/{note_id}/keywords/{keyword_id}` - Link note to keyword
- `DELETE /api/v1/notes/{note_id}/keywords/{keyword_id}` - Unlink
- `GET /api/v1/notes/{note_id}/keywords/` - Keywords for note
- `GET /api/v1/notes/keywords/{keyword_id}/notes/` - Notes for keyword

## Models

- `NoteResponse`: `{ id, title, content, created_at, last_modified, version, client_id, deleted, keywords? }`
- `KeywordResponse`: `{ id, keyword, created_at, last_modified, version, client_id, deleted }`

## Behaviors & Notes

- Optimistic locking: Update and delete operations require the caller’s `expected-version`. `PATCH` supports omitting the header; the server fetches the latest version and applies the change. Conflicts return `409` with a friendly message.
- Soft deletes: Deleted notes/keywords remain in the DB but are excluded from reads/searches.
- Keyword uniqueness is case-insensitive; creation is idempotent.
- Data limits: Title up to 255 chars; content up to ~5MB.
- RAG: The RAG Notes retriever prefers the ChaChaNotes backend for FTS. The direct-SQL fallback performs simple LIKE-based search over `notes` and intentionally ignores notebook/tag filters.

## WebUI

The integrated WebUI exposes Notes management under the “Notes” tab and consumes these endpoints, including list/search, CRUD, keyword management, and linking.
