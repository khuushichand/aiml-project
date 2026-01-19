# Slides/Presentation Module - Developer PRD

## 1. Background
- Users research topics via media ingestion, RAG queries, chat conversations, and note-taking.
- Natural next step: synthesize findings into shareable presentations.
- Aligns with the project's "Illustrated Primer" vision—helping users communicate what they've learned.
- The module will store presentations per-user following the established `Databases/user_databases/{user_id}/` pattern used by Notes, Media, and other modules.
- Reveal.js chosen as primary export format for web-native, offline-capable HTML bundles (HTML + assets).

## 2. Objectives & Success Criteria
- Deliver AI-driven slide generation from multiple content sources (prompts, chat, RAG, media, notes).
- Provide CRUD operations for managing presentations with optimistic locking and soft deletes.
- Export to Reveal.js bundled HTML (primary), Markdown (Marp-compatible), and JSON formats.
- Maintain consistency with existing codebase patterns (database isolation, schemas, dependency injection).
- Support custom CSS and all default Reveal.js themes.
- Enable full-text search across presentations via FTS5.

## 3. Personas & Use Cases
- **Researcher**: Generates a presentation summarizing findings from ingested papers/videos to share with colleagues.
- **Student**: Creates study slides from lecture transcripts or notes for exam review.
- **Content Creator**: Builds slide decks from chat conversations with AI for talks or tutorials.
- **Knowledge Worker**: Exports RAG query results as a presentation for stakeholder briefings.
- **Power User**: Manually edits generated slides, applies custom themes/CSS, and re-exports.

## 4. Scope

### In Scope
- Per-user SQLite database (`Slides.db`) for presentation storage.
- CRUD endpoints for presentations with versioning and soft delete.
- AI generation from: direct prompt, chat conversation, RAG results, media transcript, notes.
- Export formats: Reveal.js bundled HTML (zip), Marp-compatible Markdown, JSON.
- Full-text search via FTS5 on presentation titles and slide content.
- Support for Reveal.js themes (black, white, league, beige, sky, night, serif, simple, solarized, blood, moon, dracula).
- Custom CSS injection in exported presentations.
- Replace-in-place editing (no version history).
- Speaker notes support.

### Out of Scope (v1)
- Image/media embedding in slides (future: base64 in metadata).
- Real-time collaborative editing.
- PDF export (requires headless browser—deferred).
- PPTX export (complex format—deferred).
- Version history / undo.
- Presentation templates beyond Reveal.js built-in themes.
- Slide reordering via drag-and-drop UI (API supports order field).

## 5. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         API Layer                                │
│  /api/v1/slides/presentations/* (CRUD, search)                  │
│  /api/v1/slides/generate/* (AI generation)                      │
│  /api/v1/slides/presentations/{id}/export (export)              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Service Layer                              │
│  slides_generator.py - LLM-based slide generation               │
│  slides_export.py - Reveal.js/Markdown/JSON rendering           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Database Layer                              │
│  slides_db.py - SlidesDatabase class (CRUD, FTS, sync log)      │
│  Per-user: Databases/user_databases/{user_id}/Slides.db         │
└─────────────────────────────────────────────────────────────────┘
```

### File Structure
```
tldw_Server_API/app/
├── api/v1/
│   ├── endpoints/slides.py           # API routes
│   ├── schemas/slides_schemas.py     # Pydantic models
│   └── API_Deps/Slides_DB_Deps.py    # Dependency injection
├── core/
│   ├── DB_Management/db_path_utils.py  # Add get_slides_db_path()
│   └── Slides/
│       ├── __init__.py
│       ├── slides_db.py              # SlidesDatabase class
│       ├── slides_generator.py       # LLM generation
│       └── slides_export.py          # Export formatters
```

## 6. Functional Requirements

### 6.1 Data Model

**Presentations Table:**
```sql
CREATE TABLE presentations (
    id TEXT PRIMARY KEY,              -- UUID
    title TEXT NOT NULL,
    description TEXT,
    theme TEXT DEFAULT 'black',       -- Reveal.js theme name
    settings TEXT,                    -- JSON: validated allowlist (see Settings Validation)
    slides TEXT NOT NULL,             -- JSON array of Slide objects
    slides_text TEXT NOT NULL,        -- Flattened text for FTS (stored by app)
    source_type TEXT,                 -- 'manual'|'chat'|'rag'|'media'|'notes'|'prompt'
    source_ref TEXT,                  -- Source ID or JSON array for multi-source (e.g., notes)
    source_query TEXT,                -- Original prompt/query
    custom_css TEXT,                  -- User-provided CSS
    created_at DATETIME NOT NULL,
    last_modified DATETIME NOT NULL,
    deleted INTEGER DEFAULT 0,
    client_id TEXT NOT NULL,
    version INTEGER DEFAULT 1
);

CREATE INDEX idx_presentations_deleted ON presentations(deleted);
CREATE INDEX idx_presentations_created ON presentations(created_at);
```

**FTS Table:**
```sql
CREATE VIRTUAL TABLE presentations_fts USING fts5(
    title,
    slides_text,                      -- Flattened slide content
    content=presentations,
    content_rowid=rowid
);
```

**FTS Sync Triggers:**
```sql
CREATE TRIGGER presentations_ai AFTER INSERT ON presentations BEGIN
  INSERT INTO presentations_fts(rowid, title, slides_text)
  VALUES (new.rowid, new.title, new.slides_text);
END;

CREATE TRIGGER presentations_ad AFTER DELETE ON presentations BEGIN
  INSERT INTO presentations_fts(presentations_fts, rowid, title, slides_text)
  VALUES ('delete', old.rowid, old.title, old.slides_text);
END;

CREATE TRIGGER presentations_au AFTER UPDATE ON presentations BEGIN
  INSERT INTO presentations_fts(presentations_fts, rowid, title, slides_text)
  VALUES ('delete', old.rowid, old.title, old.slides_text);
  INSERT INTO presentations_fts(rowid, title, slides_text)
  VALUES (new.rowid, new.title, new.slides_text);
END;
```

**FTS Rebuild (maintenance/migration):**
```sql
INSERT INTO presentations_fts(presentations_fts) VALUES ('rebuild');
```

**Slide Object (JSON):**
```python
class SlideLayout(str, Enum):
    TITLE = "title"
    CONTENT = "content"
    TWO_COLUMN = "two_column"
    QUOTE = "quote"
    SECTION = "section"
    BLANK = "blank"

class Slide(BaseModel):
    order: int
    layout: SlideLayout
    title: Optional[str] = None
    content: str = ""                 # Markdown; may be empty for title/section/blank
    speaker_notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)  # Future: images as base64
```

**Ordering & Validation:**
- `order` is authoritative; server sorts by `order` and ignores JSON array order.
- `order` must be unique non-negative integers; server normalizes to 0..n-1 on write.

**Settings Validation:**
- `settings` must be a JSON object validated against an allowlist; unknown keys or invalid types return 422.
- Allowed keys (initial): `transition`, `backgroundTransition`, `slideNumber`, `controls`, `progress`, `hash`, `center`, `width`, `height`, `margin`, `minScale`, `maxScale`, `viewDistance`, `keyboard`, `touch`, `loop`, `rtl`, `navigationMode`.

### 6.2 API Endpoints

**CRUD:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/slides/presentations` | Create presentation |
| GET | `/api/v1/slides/presentations` | List presentations (paginated, optional `include_deleted`) |
| GET | `/api/v1/slides/presentations/{id}` | Get single presentation (optional `include_deleted`) |
| PUT | `/api/v1/slides/presentations/{id}` | Full update (with If-Match header) |
| PATCH | `/api/v1/slides/presentations/{id}` | Partial update |
| DELETE | `/api/v1/slides/presentations/{id}` | Soft delete |
| POST | `/api/v1/slides/presentations/{id}/restore` | Restore soft-deleted presentation |
| GET | `/api/v1/slides/presentations/search` | FTS search (`?q=...`, optional `include_deleted`) |

**AI Generation:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/slides/generate` | Generate from prompt |
| POST | `/api/v1/slides/generate/from-chat` | Generate from conversation |
| POST | `/api/v1/slides/generate/from-rag` | Generate from RAG results |
| POST | `/api/v1/slides/generate/from-media` | Generate from media item |
| POST | `/api/v1/slides/generate/from-notes` | Generate from selected notes |

**Export:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/slides/presentations/{id}/export?format=revealjs` | ZIP bundle (HTML + assets) |
| GET | `/api/v1/slides/presentations/{id}/export?format=markdown` | Marp MD |
| GET | `/api/v1/slides/presentations/{id}/export?format=json` | Raw JSON |

**Export Examples:**

**Reveal.js ZIP**
Request:
`GET /api/v1/slides/presentations/b1d33d8a-5d2c-4b2f-9d5c-0b33fe2b4d2f/export?format=revealjs`
Response headers:
- `Content-Type: application/zip`
- `Content-Disposition: attachment; filename="presentation_b1d33d8a.zip"`
Body: binary ZIP (see Bundle Layout for file paths).

**Markdown**
Request:
`GET /api/v1/slides/presentations/b1d33d8a-5d2c-4b2f-9d5c-0b33fe2b4d2f/export?format=markdown`
Response (200, `Content-Type: text/markdown`):
```markdown
---
marp: true
theme: default
---

# Q2 Research Summary

---

## Key Findings

- Finding A
- Finding B
```

**JSON**
Request:
`GET /api/v1/slides/presentations/b1d33d8a-5d2c-4b2f-9d5c-0b33fe2b4d2f/export?format=json`
Response (200, `Content-Type: application/json`):
```json
{
  "id": "b1d33d8a-5d2c-4b2f-9d5c-0b33fe2b4d2f",
  "title": "Q2 Research Summary",
  "theme": "black",
  "slides": [
    {
      "order": 0,
      "layout": "title",
      "title": "Q2 Research Summary",
      "content": "",
      "speaker_notes": null,
      "metadata": {}
    }
  ]
}
```

**List/Search Params (initial):**
- `limit`, `offset`, `sort` (e.g., `created_at desc`), `include_deleted`
- `q` for search query

**Routing Note:**
- Keep `/presentations/search` as a static path segment (and define it explicitly) to avoid collisions with `/presentations/{id}`.

### 6.3 AI Generation

**Generation Flow:**
1. Receive source content (prompt text, conversation ID, RAG query, media ID, note IDs)
2. Fetch source material from appropriate database
3. Build LLM prompt with source context
4. Call LLM via `chat_api_call()` requesting JSON output
5. Parse JSON into Presentation model
6. Store with `source_type` and `source_ref` for provenance
7. Return created presentation

**Source Size Controls:**
- Request includes user-defined limits (e.g., `max_source_tokens` or `max_source_chars`).
- Chunking/summarization is optional per request but must be supported; when enabled, chunk to a configurable size and summarize before generation.
- If chunking is disabled and input exceeds the user-defined limit, return 413 with a clear error message.
- Chunking controls (initial): `enable_chunking`, `chunk_size_tokens`, `summary_tokens` (optional).

**System Prompt Template:**
```
You are creating presentation slides. Output valid JSON:
{
  "title": "Presentation Title",
  "slides": [
    {"order": 0, "layout": "title", "title": "...", "content": "..."},
    {"order": 1, "layout": "content", "title": "...", "content": "- Bullet 1\n- Bullet 2"},
    ...
  ]
}

Guidelines:
- 5-12 slides typical length
- Title slide first, conclusion/summary last
- Use markdown formatting (bullets, bold, code)
- 3-6 bullet points per content slide
- Add speaker_notes for details that don't fit slides
```

**Example: Generate from prompt**
Request:
```http
POST /api/v1/slides/generate
```
```json
{
  "title_hint": "Q2 Research Summary",
  "prompt": "Summarize key findings from the last three project updates.",
  "theme": "black",
  "settings": {
    "transition": "fade",
    "slideNumber": true
  },
  "max_source_tokens": 6000,
  "enable_chunking": true,
  "chunk_size_tokens": 1200
}
```
Response (201):
```json
{
  "id": "b1d33d8a-5d2c-4b2f-9d5c-0b33fe2b4d2f",
  "title": "Q2 Research Summary",
  "description": null,
  "theme": "black",
  "settings": {
    "transition": "fade",
    "slideNumber": true
  },
  "slides": [
    {
      "order": 0,
      "layout": "title",
      "title": "Q2 Research Summary",
      "content": "",
      "speaker_notes": null,
      "metadata": {}
    },
    {
      "order": 1,
      "layout": "content",
      "title": "Key Findings",
      "content": "- Finding A\n- Finding B\n- Finding C",
      "speaker_notes": "Expand on sources and confidence.",
      "metadata": {}
    }
  ],
  "source_type": "prompt",
  "source_ref": null,
  "source_query": "Summarize key findings from the last three project updates.",
  "custom_css": null,
  "created_at": "2025-01-14T12:00:00Z",
  "last_modified": "2025-01-14T12:00:00Z",
  "deleted": 0,
  "client_id": "api_client",
  "version": 1
}
```

**Example: Generate from media**
Request:
```http
POST /api/v1/slides/generate/from-media
```
```json
{
  "media_id": "media_2f1c9a",
  "title_hint": "Talk Summary",
  "theme": "night",
  "max_source_chars": 40000,
  "enable_chunking": false
}
```
Response (201): same shape as above, with `"source_type": "media"` and `"source_ref": "media_2f1c9a"`.

**Example: Generate from chat**
Request:
```http
POST /api/v1/slides/generate/from-chat
```
```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "title_hint": "Team Sync Summary",
  "theme": "simple",
  "max_source_tokens": 5000,
  "enable_chunking": true,
  "chunk_size_tokens": 1000
}
```
Response (201): same shape as above, with `"source_type": "chat"` and `"source_ref": "550e8400-e29b-41d4-a716-446655440000"`.

**Example: Generate from notes**
Request:
```http
POST /api/v1/slides/generate/from-notes
```
```json
{
  "note_ids": ["note_12a", "note_12b", "note_12c"],
  "title_hint": "Exam Review",
  "theme": "serif",
  "max_source_tokens": 8000,
  "enable_chunking": true,
  "chunk_size_tokens": 1500,
  "summary_tokens": 400
}
```
Response (201): same shape as above, with `"source_type": "notes"` and `"source_ref": ["note_12a","note_12b","note_12c"]`.

**Example: Generate from RAG**
Request:
```http
POST /api/v1/slides/generate/from-rag
```
```json
{
  "query": "What are the top risks in the 2025 roadmap?",
  "top_k": 8,
  "title_hint": "2025 Roadmap Risks",
  "theme": "moon",
  "max_source_chars": 30000,
  "enable_chunking": false
}
```
Response (201): same shape as above, with `"source_type": "rag"` and `"source_query"` set to the query.

**RAG Error Examples**
- 413 (chunking disabled, input too large):
```json
{
  "detail": "Input exceeds max_source_chars and chunking is disabled.",
  "code": "input_too_large",
  "max_source_chars": 30000
}
```
- 422 (validation error):
```json
{
  "detail": "Invalid settings: unknown keys ['autoSlide']",
  "code": "invalid_settings"
}
```

### 6.4 Export Formats

**Reveal.js Bundle (ZIP):**
- Bundle layout includes `index.html` plus local Reveal.js assets (no CDN required).
- Suggested layout: `index.html`, `assets/reveal/` (css, js, plugins), optional `assets/custom.css`.

**Bundle Layout (exact paths):**
```
presentation.zip
├── index.html
├── LICENSE.revealjs.txt            # required notice
├── NOTICE.revealjs.txt             # required notice (if provided upstream)
└── assets/
    ├── custom.css                  # optional (sanitized)
    └── reveal/
        ├── reveal.css
        ├── reveal.js
        ├── theme/
        │   └── black.css            # plus other theme files as needed
        └── plugin/
            └── notes/
                └── notes.js
```
- If `custom_css` is provided, write it to `assets/custom.css` and link it from `index.html`.
- Include Reveal.js license/notice files at the ZIP root when bundling assets.

**Reveal.js HTML (inside bundle):**
```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{{title}}</title>
  <link rel="stylesheet" href="assets/reveal/reveal.css">
  <link rel="stylesheet" href="assets/reveal/theme/{{theme}}.css">
  {{#if custom_css}}<link rel="stylesheet" href="assets/custom.css">{{/if}}
</head>
<body>
  <div class="reveal">
    <div class="slides">
      {{#each slides}}
      <section data-layout="{{layout}}">
        {{#if title}}<h2>{{title}}</h2>{{/if}}
        <div class="content">{{content_html}}</div>
        {{#if speaker_notes}}<aside class="notes">{{speaker_notes}}</aside>{{/if}}
      </section>
      {{/each}}
    </div>
  </div>
  <script src="assets/reveal/reveal.js"></script>
  <script src="assets/reveal/plugin/notes/notes.js"></script>
  <script>
    const settings = {{settings_json}};
    settings.plugins = [ RevealNotes ];
    Reveal.initialize(settings);
  </script>
</body>
</html>
```

**Marp Markdown:**
```markdown
---
marp: true
theme: {{marp_theme}}
---

# {{title}}

---

## Slide Title

- Bullet 1
- Bullet 2

<!--
Speaker notes here
-->
```
- Marp export requires a theme mapping or a separate `marp_theme` setting; Reveal.js theme names are not valid Marp themes.

**Marp Theme Mapping (initial):**
| Reveal.js theme | Marp theme |
|---|---|
| black | default |
| white | default |
| league | gaia |
| beige | gaia |
| sky | uncover |
| night | uncover |
| serif | gaia |
| simple | default |
| solarized | gaia |
| blood | uncover |
| moon | uncover |
| dracula | uncover |

If a Reveal.js theme is not in the table, default to `default` unless `marp_theme` is explicitly provided.

### 6.4.1 Export Path (Separate from File_Artifacts)

- Slides export is served directly from `/api/v1/slides/presentations/{id}/export` and does **not** use the File_Artifacts API, jobs worker, or `file_artifacts` storage.
- Export generation is synchronous in v1 (target < 1s) and returns the file bytes immediately with `Content-Type` and `Content-Disposition` headers.
- The Slides service (`slides_export.py`) is the single formatter surface for Reveal.js ZIP, Marp Markdown, and JSON outputs.
- No artifacts are persisted beyond the request lifecycle; large/async exports are out of scope for v1 (future: optional adapter under File_Artifacts).
- If Reveal.js assets are unavailable, the export endpoint must return a clear error indicating missing bundled assets.

### 6.5 Concurrency & Error Semantics

**ETag / If-Match Contract:**
- `GET /presentations/{id}` returns `ETag: W/"v{version}"` and `Last-Modified` from `last_modified`.
- `PUT`, `PATCH`, `DELETE`, and `restore` require `If-Match` with the last seen ETag.
- Missing `If-Match` returns 428 (Precondition Required); mismatch returns 412 (Precondition Failed).
- Successful updates increment `version` and return the updated ETag and resource.

**API Error Semantics (Slides):**
- 400: malformed query params, unsupported export `format`, or invalid `If-Match` syntax.
- 404: not found (including soft-deleted by default).
- 409: conflict on create when ID already exists.
- 410: optional when `include_deleted=true` and resource is soft-deleted.
- 412: `If-Match` precondition failed.
- 413: generation input exceeds user-defined limit with chunking disabled.
- 422: schema validation errors, invalid `settings`, or invalid slide layouts.
- 429: rate limited.

### 6.6 Validation & Sanitization

- Markdown rendering uses `markdown-it-py` (or `markdown`) with raw HTML disabled; output is sanitized via `bleach` allowlist (tags/attrs/protocols) before embedding.
- Custom CSS is sanitized using `bleach` CSS sanitizer with an allowlist of safe properties; block `@import` and `url()` to avoid external fetches.
- Speaker notes are treated as plain text and escaped before rendering.

## 7. Non-Functional Requirements

- **Performance**: Slide generation < 30s for typical 10-slide deck; export < 1s.
- **Reliability**: Optimistic locking prevents concurrent edit conflicts; soft deletes enable recovery.
- **Scalability**: Per-user SQLite databases; no shared state between users.
- **Security**: User isolation via per-user DB paths; input validation on all fields; settings allowlist; sanitize markdown/HTML/CSS per Section 6.6.
- **Testing**: Unit tests for DB operations, generation parsing, export rendering; integration tests for API endpoints.

## 8. Configuration & Deployment

- **Database Path**: `Databases/user_databases/{user_id}/Slides.db`
- **Path Resolution**: Add `get_slides_db_path()` to `db_path_utils.py`
- **Router Registration**: Add to `main.py`:
  ```python
  from tldw_Server_API.app.api.v1.endpoints.slides import router as slides_router
  app.include_router(slides_router, prefix="/api/v1/slides", tags=["slides"])
  ```
- **Dependencies**: Existing LLM infrastructure; `markdown` or `markdown-it-py` for HTML conversion; `bleach` for HTML/CSS sanitization.
- **Reveal.js Assets**: Bundle a local Reveal.js dist inside the export ZIP (ship in repo or vendored assets).
- **No Additional Services**: Self-contained module, no external services beyond existing LLM providers.

## 9. Data & Storage

- **Primary Storage**: SQLite database per user at `Databases/user_databases/{user_id}/Slides.db`.
- **Slides Content**: JSON blob in `slides` column containing array of Slide objects; `slides_text` stores flattened text for FTS and is maintained by the application on write.
- **Search Index**: FTS5 virtual table indexing title and `slides_text`; search queries join `presentations` and filter `deleted=0`.
- **Sync Log**: Change tracking for potential future sync/export features.
- **Soft Deletes**: `deleted` column (0/1) with filtered queries and a restore endpoint.
- **No Media Storage**: v1 does not store images; future versions may embed base64 in slide metadata.

## 10. Integrations & Dependencies

**Internal Integrations:**
- `CharactersRAGDB` - Fetch chat conversations for generation
- `MediaDatabase` - Fetch media transcripts/summaries for generation
- Notes endpoints - Fetch notes for generation
- RAG service - Execute queries for generation
- LLM infrastructure - `chat_api_call()` for slide generation

**External Dependencies:**
- Reveal.js (bundled in export ZIP; no CDN at runtime)
- `markdown` or `markdown-it-py` for markdown→HTML conversion
- `bleach` for HTML/CSS sanitization

**Patterns Followed:**
- `ChaChaNotes_DB.py` - Database class structure
- `notes_schemas.py` - Pydantic schema patterns
- `ChaCha_Notes_DB_Deps.py` - Dependency injection
- `document_generator.py` - LLM generation pattern

## 11. Testing Strategy

**Test Location**: `tldw_Server_API/tests/Slides/`

**Unit Tests:**
- `SlidesDatabase` CRUD operations
- Slide JSON parsing and validation
- FTS search functionality
- Export format rendering (Reveal.js, Markdown)
- Generation prompt building

**Integration Tests:**
- API endpoint responses
- Authentication/authorization
- Generation with mocked LLM
- Export download responses

**Mocking:**
- LLM responses for generation tests
- Database fixtures for CRUD tests
- User authentication for endpoint tests

## 12. Monitoring & Operations

- **Logging**: Use `loguru` for all operations (creation, generation, export).
- **Metrics**: Track generation latency, export counts, error rates via existing metrics infrastructure.
- **Health Check**: Optional `/api/v1/slides/health` endpoint for DB connectivity.
- **Rate Limiting**: Apply standard rate limits via `rbac_rate_limit("slides.*")`.

## 13. Risks & Open Issues

| Risk | Mitigation |
|------|------------|
| LLM output parsing failures | Robust JSON parsing with fallback error messages; retry logic |
| Large presentations slow FTS | Limit slide count per presentation (e.g., 50); paginate search |
| Reveal.js assets missing/stale in bundle | Vendor a pinned Reveal.js dist; add CI check for bundle integrity |
| Custom CSS injection attacks | Sanitize CSS; limit allowed properties if needed |
| Markdown XSS in exports | Use safe markdown renderer; sanitize HTML output |

**Decisions:**
- Generation supports streaming (partial slides as they are generated).
- Support presentation templates beyond Reveal.js themes (post-v1).
- Exports include an offline Reveal.js ZIP bundle by default.
- Reveal.js `settings` are validated against an allowlist.
- Slide ordering is determined by the `order` field.
- Source size limits are user-defined; chunking/summarization is optional per request but must be supported.

## 14. Roadmap

### Phase 1: Core (MVP)
- Database schema and `SlidesDatabase` class
- CRUD endpoints with optimistic locking
- Basic Pydantic schemas
- Router registration

### Phase 2: Export
- Reveal.js HTML export with theme support
- Markdown export (Marp-compatible)
- JSON export
- Custom CSS injection

### Phase 3: AI Generation
- Direct prompt generation
- Generation from chat conversations
- Generation from RAG results
- Generation from media items
- Generation from notes

### Phase 4: Search & Polish
- FTS5 search implementation
- API documentation
- Integration tests
- Error handling refinement

### Future Phases
- Image embedding support
- PDF export (headless browser)
- Presentation templates
- Slide reordering UI support
- Version history
