# Slides/Presentation Module - Developer PRD

## 1. Background
- Users research topics via media ingestion, RAG queries, chat conversations, and note-taking.
- Natural next step: synthesize findings into shareable presentations.
- Aligns with the project's "Illustrated Primer" vision—helping users communicate what they've learned.
- The module will store presentations per-user following the established `Databases/user_databases/{user_id}/` pattern used by Notes, Media, and other modules.
- Reveal.js chosen as primary export format for web-native, self-contained HTML slideshows.

## 2. Objectives & Success Criteria
- Deliver AI-driven slide generation from multiple content sources (prompts, chat, RAG, media, notes).
- Provide CRUD operations for managing presentations with optimistic locking and soft deletes.
- Export to Reveal.js HTML (primary), Markdown (Marp-compatible), and JSON formats.
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
- Export formats: Reveal.js HTML, Marp-compatible Markdown, JSON.
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
    settings TEXT,                    -- JSON: {transition, slideNumber, controls, etc.}
    slides TEXT NOT NULL,             -- JSON array of Slide objects
    source_type TEXT,                 -- 'manual'|'chat'|'rag'|'media'|'notes'|'prompt'
    source_ref TEXT,                  -- ID of source entity
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
    content: str                      # Markdown
    speaker_notes: Optional[str] = None
    metadata: Dict[str, Any] = {}     # Future: images as base64
```

### 6.2 API Endpoints

**CRUD:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/slides/presentations` | Create presentation |
| GET | `/api/v1/slides/presentations` | List presentations (paginated) |
| GET | `/api/v1/slides/presentations/{id}` | Get single presentation |
| PUT | `/api/v1/slides/presentations/{id}` | Full update (with If-Match header) |
| PATCH | `/api/v1/slides/presentations/{id}` | Partial update |
| DELETE | `/api/v1/slides/presentations/{id}` | Soft delete |
| GET | `/api/v1/slides/presentations/search` | FTS search (`?q=...`) |

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
| GET | `/api/v1/slides/presentations/{id}/export?format=revealjs` | HTML bundle |
| GET | `/api/v1/slides/presentations/{id}/export?format=markdown` | Marp MD |
| GET | `/api/v1/slides/presentations/{id}/export?format=json` | Raw JSON |

### 6.3 AI Generation

**Generation Flow:**
1. Receive source content (prompt text, conversation ID, RAG query, media ID, note IDs)
2. Fetch source material from appropriate database
3. Build LLM prompt with source context
4. Call LLM via `chat_api_call()` requesting JSON output
5. Parse JSON into Presentation model
6. Store with `source_type` and `source_ref` for provenance
7. Return created presentation

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

### 6.4 Export Formats

**Reveal.js HTML:**
```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{{title}}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@5/dist/reveal.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@5/dist/theme/{{theme}}.css">
  {{#if custom_css}}<style>{{custom_css}}</style>{{/if}}
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
  <script src="https://cdn.jsdelivr.net/npm/reveal.js@5/dist/reveal.js"></script>
  <script>Reveal.initialize({{settings_json}});</script>
</body>
</html>
```

**Marp Markdown:**
```markdown
---
marp: true
theme: {{theme}}
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

## 7. Non-Functional Requirements

- **Performance**: Slide generation < 30s for typical 10-slide deck; export < 1s.
- **Reliability**: Optimistic locking prevents concurrent edit conflicts; soft deletes enable recovery.
- **Scalability**: Per-user SQLite databases; no shared state between users.
- **Security**: User isolation via per-user DB paths; input validation on all fields; no XSS in exported HTML (sanitize markdown).
- **Testing**: Unit tests for DB operations, generation parsing, export rendering; integration tests for API endpoints.

## 8. Configuration & Deployment

- **Database Path**: `Databases/user_databases/{user_id}/Slides.db`
- **Path Resolution**: Add `get_slides_db_path()` to `db_path_utils.py`
- **Router Registration**: Add to `main.py`:
  ```python
  from tldw_Server_API.app.api.v1.endpoints.slides import router as slides_router
  app.include_router(slides_router, prefix="/api/v1/slides", tags=["slides"])
  ```
- **Dependencies**: Existing LLM infrastructure, `markdown` or `markdown-it-py` for HTML conversion.
- **No Additional Services**: Self-contained module, no external dependencies beyond existing LLM providers.

## 9. Data & Storage

- **Primary Storage**: SQLite database per user at `Databases/user_databases/{user_id}/Slides.db`.
- **Slides Content**: JSON blob in `slides` column containing array of Slide objects.
- **Search Index**: FTS5 virtual table indexing title and flattened slide content.
- **Sync Log**: Change tracking for potential future sync/export features.
- **Soft Deletes**: `deleted` column (0/1) with filtered queries.
- **No Media Storage**: v1 does not store images; future versions may embed base64 in slide metadata.

## 10. Integrations & Dependencies

**Internal Integrations:**
- `CharactersRAGDB` - Fetch chat conversations for generation
- `MediaDatabase` - Fetch media transcripts/summaries for generation
- Notes endpoints - Fetch notes for generation
- RAG service - Execute queries for generation
- LLM infrastructure - `chat_api_call()` for slide generation

**External Dependencies:**
- Reveal.js (CDN-linked, no local installation)
- `markdown` or `markdown-it-py` for markdown→HTML conversion

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
| Reveal.js CDN unavailable | Document offline bundle option; consider local fallback |
| Custom CSS injection attacks | Sanitize CSS; limit allowed properties if needed |
| Markdown XSS in exports | Use safe markdown renderer; sanitize HTML output |

**Open Questions:**
- Should generation support streaming (partial slides as they're generated)?
- Should we support presentation templates beyond Reveal.js themes?
- Should exports include offline Reveal.js bundle option?

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
