# Kanban Board User Guide

This guide covers the Kanban Board module for organizing tasks, research workflows, and ideas with full search integration.

---

## Table of Contents

1. [Overview](#overview)
2. [User Guide](#user-guide)
   - [Getting Started](#getting-started)
   - [Boards](#boards)
   - [Lists](#lists)
   - [Cards](#cards)
   - [Labels](#labels)
   - [Checklists](#checklists)
   - [Comments](#comments)
   - [Searching Cards](#searching-cards)
3. [Developer Guide](#developer-guide)
   - [API Endpoints](#api-endpoints)
   - [Search API](#search-api)
   - [Pydantic Schemas](#pydantic-schemas)
   - [Error Handling](#error-handling)
   - [Code Architecture](#code-architecture)
4. [Administrator Guide](#administrator-guide)
   - [Configuration](#configuration)
   - [Search Scoring Configuration](#search-scoring-configuration)
   - [Database Management](#database-management)
   - [Monitoring](#monitoring)

---

## Overview

The Kanban Board module provides Trello-like task management integrated with tldw_server's RAG infrastructure. Key features include:

- **Boards, Lists, and Cards**: Organize work visually across columns
- **Rich Card Features**: Due dates, labels, checklists, comments, and markdown descriptions
- **Full-Text Search**: FTS5-powered search across card titles and descriptions
- **Vector Search** (optional): Semantic search via ChromaDB embeddings
- **Hybrid Search**: Combine keyword and semantic search for best results
- **Content Linking**: Link cards to media items, notes, and research content

---

## User Guide

### Getting Started

Access Kanban boards via the API at `/api/v1/kanban/`. All operations require authentication:

- **Single-user mode**: Use `X-API-KEY` header
- **Multi-user mode**: Use `Authorization: Bearer <token>` header

### Boards

Boards are the top-level containers for organizing work.

**Create a Board**
```bash
curl -X POST "http://localhost:8000/api/v1/kanban/boards" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Research Project", "description": "Track research papers"}'
```

**List Your Boards**
```bash
curl "http://localhost:8000/api/v1/kanban/boards" \
  -H "Authorization: Bearer <token>"
```

**Archive/Restore Boards**
- Archive: `POST /api/v1/kanban/boards/{id}/archive`
- Unarchive: `POST /api/v1/kanban/boards/{id}/unarchive`
- Soft delete: `DELETE /api/v1/kanban/boards/{id}`
- Restore deleted: `POST /api/v1/kanban/boards/{id}/restore`

### Lists

Lists represent columns/stages in your workflow (e.g., "To Do", "In Progress", "Done").

**Create a List**
```bash
curl -X POST "http://localhost:8000/api/v1/kanban/boards/{board_id}/lists" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "To Do"}'
```

**Reorder Lists**
```bash
curl -X POST "http://localhost:8000/api/v1/kanban/boards/{board_id}/lists/reorder" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"ids": [3, 1, 2]}'
```

### Cards

Cards are individual tasks or items within lists.

**Create a Card**
```bash
curl -X POST "http://localhost:8000/api/v1/kanban/lists/{list_id}/cards" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Review paper on transformers",
    "description": "Read and summarize the attention mechanism paper",
    "priority": "high",
    "due_date": "2025-01-15"
  }'
```

**Move a Card**
```bash
curl -X POST "http://localhost:8000/api/v1/kanban/cards/{card_id}/move" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"target_list_id": 5, "position": 0}'
```

**Copy a Card**
```bash
curl -X POST "http://localhost:8000/api/v1/kanban/cards/{card_id}/copy" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"target_list_id": 5, "include_checklists": true, "include_labels": true}'
```

### Labels

Labels are color-coded tags for categorizing cards within a board.

**Create a Label**
```bash
curl -X POST "http://localhost:8000/api/v1/kanban/boards/{board_id}/labels" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Urgent", "color": "red"}'
```

**Add Label to Card**
```bash
curl -X POST "http://localhost:8000/api/v1/kanban/cards/{card_id}/labels/{label_id}" \
  -H "Authorization: Bearer <token>"
```

### Checklists

Checklists track sub-tasks within a card.

**Create a Checklist**
```bash
curl -X POST "http://localhost:8000/api/v1/kanban/cards/{card_id}/checklists" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Reading tasks"}'
```

**Add Checklist Item**
```bash
curl -X POST "http://localhost:8000/api/v1/kanban/checklists/{checklist_id}/items" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"content": "Read abstract", "checked": false}'
```

**Toggle All Items**
```bash
curl -X POST "http://localhost:8000/api/v1/kanban/checklists/{checklist_id}/toggle-all" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"checked": true}'
```

### Comments

Add notes and context to cards via comments.

**Add a Comment**
```bash
curl -X POST "http://localhost:8000/api/v1/kanban/cards/{card_id}/comments" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"content": "Found a related paper on attention mechanisms"}'
```

### Searching Cards

Search across all your cards using keywords, filters, and different search modes.

**Basic Search (GET)**
```bash
curl "http://localhost:8000/api/v1/kanban/search?q=transformer&per_page=20" \
  -H "Authorization: Bearer <token>"
```

**Search with Filters**
```bash
curl "http://localhost:8000/api/v1/kanban/search?q=review&board_id=1&priority=high&label_ids=3,5" \
  -H "Authorization: Bearer <token>"
```

**Search via POST** (for complex queries)
```bash
curl -X POST "http://localhost:8000/api/v1/kanban/search" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning",
    "board_id": 1,
    "label_ids": [3, 5],
    "priority": "high",
    "include_archived": false,
    "search_mode": "fts",
    "page": 1,
    "per_page": 20
  }'
```

**Search Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `q` / `query` | string | Search query (required) |
| `board_id` | int | Filter by board |
| `label_ids` | string/array | Comma-separated label IDs (cards must have ALL) |
| `priority` | string | Filter by priority: low, medium, high, urgent |
| `include_archived` | bool | Include archived cards (default: false) |
| `search_mode` | string | `fts`, `vector`, or `hybrid` (default: fts) |
| `page` | int | Page number (default: 1) |
| `per_page` | int | Results per page, max 100 (default: 20) |

**Search Modes**

1. **FTS (Full-Text Search)**: Fast keyword-based search using SQLite FTS5. Best for exact term matching.

2. **Vector Search**: Semantic search using ChromaDB embeddings. Finds conceptually similar cards even without exact keyword matches. Requires ChromaDB to be configured.

3. **Hybrid Search**: Combines FTS and vector search for best results. Uses weighted scoring:
   - 60% weight on keyword matches (FTS)
   - 40% weight on semantic similarity (vector)
   - Vector-only matches get reduced weight (30%)

**Check Search Status**
```bash
curl "http://localhost:8000/api/v1/kanban/search/status" \
  -H "Authorization: Bearer <token>"
```

Response:
```json
{
  "fts_available": true,
  "vector_available": false,
  "hybrid_available": false,
  "default_mode": "fts",
  "supported_modes": ["fts", "vector", "hybrid"],
  "scoring_weights": {
    "fts_weight": 0.6,
    "vector_weight": 0.4,
    "vector_only_weight": 0.3
  }
}
```

---

## Developer Guide

### API Endpoints

All endpoints are prefixed with `/api/v1/kanban`.

#### Boards
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/boards` | List boards |
| POST | `/boards` | Create board |
| GET | `/boards/{id}` | Get board with lists/cards |
| PATCH | `/boards/{id}` | Update board |
| POST | `/boards/{id}/archive` | Archive board |
| POST | `/boards/{id}/unarchive` | Unarchive board |
| DELETE | `/boards/{id}` | Soft delete board |
| POST | `/boards/{id}/restore` | Restore deleted board |

#### Lists
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/boards/{board_id}/lists` | Get lists for board |
| POST | `/boards/{board_id}/lists` | Create list |
| PATCH | `/lists/{id}` | Update list |
| POST | `/lists/{id}/archive` | Archive list |
| POST | `/lists/{id}/unarchive` | Unarchive list |
| DELETE | `/lists/{id}` | Soft delete list |
| POST | `/lists/{id}/restore` | Restore deleted list |
| POST | `/boards/{board_id}/lists/reorder` | Reorder lists |

#### Cards
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/lists/{list_id}/cards` | Get cards in list |
| POST | `/lists/{list_id}/cards` | Create card |
| GET | `/cards/{id}` | Get card details |
| PATCH | `/cards/{id}` | Update card |
| POST | `/cards/{id}/archive` | Archive card |
| POST | `/cards/{id}/unarchive` | Unarchive card |
| DELETE | `/cards/{id}` | Soft delete card |
| POST | `/cards/{id}/restore` | Restore deleted card |
| POST | `/cards/{id}/move` | Move card |
| POST | `/cards/{id}/copy` | Copy card |
| POST | `/lists/{list_id}/cards/reorder` | Reorder cards |

#### Labels
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/boards/{board_id}/labels` | Get board labels |
| POST | `/boards/{board_id}/labels` | Create label |
| PATCH | `/labels/{id}` | Update label |
| DELETE | `/labels/{id}` | Delete label |
| POST | `/cards/{card_id}/labels/{label_id}` | Add label to card |
| DELETE | `/cards/{card_id}/labels/{label_id}` | Remove label from card |

#### Checklists
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cards/{card_id}/checklists` | Get card checklists |
| POST | `/cards/{card_id}/checklists` | Create checklist |
| PATCH | `/checklists/{id}` | Update checklist |
| DELETE | `/checklists/{id}` | Delete checklist |
| POST | `/checklists/{id}/items` | Add item |
| PATCH | `/checklists/{checklist_id}/items/{item_id}` | Update item |
| DELETE | `/checklists/{checklist_id}/items/{item_id}` | Delete item |
| POST | `/checklists/{id}/toggle-all` | Toggle all items |

#### Comments
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cards/{card_id}/comments` | Get card comments |
| POST | `/cards/{card_id}/comments` | Add comment |
| PATCH | `/comments/{id}` | Update comment |
| DELETE | `/comments/{id}` | Delete comment |

#### Search
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/search` | Search cards (query params) |
| POST | `/search` | Search cards (request body) |
| GET | `/search/status` | Get search capabilities |

### Search API

#### Request Schema (POST)
```python
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    board_id: Optional[int] = None
    label_ids: Optional[List[int]] = None
    priority: Optional[str] = None  # low, medium, high, urgent
    include_archived: bool = False
    search_mode: str = "fts"  # fts, vector, hybrid
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)
```

#### Response Schema
```python
class SearchResponse(BaseModel):
    query: str
    search_mode: str  # actual mode used (may differ if fallback)
    results: List[SearchResultCard]
    pagination: PaginationInfo

class SearchResultCard(BaseModel):
    id: int
    uuid: str
    board_id: int
    board_name: str
    list_id: int
    list_name: str
    title: str
    description: Optional[str]
    priority: Optional[str]
    due_date: Optional[str]
    labels: List[dict]
    created_at: str
    updated_at: str
    relevance_score: Optional[float]

class PaginationInfo(BaseModel):
    total: int
    limit: int
    offset: int
    has_more: bool
```

### Error Handling

The API returns standard HTTP status codes:

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request (validation error, invalid input) |
| 401 | Unauthorized |
| 404 | Not Found |
| 409 | Conflict (e.g., duplicate client_id) |
| 422 | Unprocessable Entity (validation error) |
| 500 | Internal Server Error |

Error response format:
```json
{
  "detail": "Error message describing what went wrong"
}
```

### Code Architecture

**Key Files**

| File | Description |
|------|-------------|
| `app/core/DB_Management/Kanban_DB.py` | Database layer with all CRUD operations |
| `app/core/DB_Management/kanban_vector_search.py` | ChromaDB vector search integration |
| `app/api/v1/endpoints/kanban_*.py` | API endpoint handlers |
| `app/api/v1/schemas/kanban_schemas.py` | Pydantic models |
| `app/api/v1/API_Deps/kanban_deps.py` | FastAPI dependencies |

**Database Schema**

The Kanban module uses SQLite with the following tables:
- `kanban_boards` - Board metadata
- `kanban_lists` - Lists within boards
- `kanban_cards` - Cards within lists
- `kanban_labels` - Board-scoped labels
- `kanban_card_labels` - Card-label associations
- `kanban_checklists` - Checklists on cards
- `kanban_checklist_items` - Items in checklists
- `kanban_comments` - Comments on cards
- `kanban_activities` - Activity log
- `kanban_cards_fts` - FTS5 virtual table for search

**Key Design Patterns**

1. **Soft Delete**: All entities support soft delete with `deleted` flag and `deleted_at` timestamp
2. **Archive**: Separate from delete; archived items are hidden but fully restorable
3. **Position Management**: 0-indexed integers for ordering; gaps are allowed
4. **Version Field**: Optimistic locking support via version increment on updates
5. **User Isolation**: All queries filter by `user_id`; database path is per-user

---

## Administrator Guide

### Configuration

#### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KANBAN_SEARCH_FTS_WEIGHT` | 0.6 | Weight for FTS score in hybrid search |
| `KANBAN_SEARCH_VECTOR_WEIGHT` | 0.4 | Weight for vector score in hybrid search |
| `KANBAN_SEARCH_VECTOR_ONLY_WEIGHT` | 0.3 | Weight multiplier for vector-only matches |

Example `.env`:
```bash
# Hybrid search scoring weights (must sum to 1.0 for normalized scoring)
KANBAN_SEARCH_FTS_WEIGHT=0.6
KANBAN_SEARCH_VECTOR_WEIGHT=0.4
KANBAN_SEARCH_VECTOR_ONLY_WEIGHT=0.3
```

### Search Scoring Configuration

The hybrid search combines full-text search (FTS) and vector similarity scores using configurable weights.

**Scoring Formula**

For cards found by both FTS and vector search:
```
hybrid_score = (FTS_WEIGHT * fts_score) + (VECTOR_WEIGHT * vector_score)
```

For cards found only by vector search (semantic match without keyword match):
```
score = VECTOR_ONLY_WEIGHT * vector_score
```

**Default Weights**

| Weight | Default | Purpose |
|--------|---------|---------|
| FTS_WEIGHT | 0.6 (60%) | Prioritizes keyword/phrase matches |
| VECTOR_WEIGHT | 0.4 (40%) | Supplements with semantic similarity |
| VECTOR_ONLY_WEIGHT | 0.3 (30%) | Reduces rank of pure semantic matches |

**Tuning Guidelines**

- **Increase FTS_WEIGHT** (e.g., 0.8) when users primarily search for exact terms
- **Increase VECTOR_WEIGHT** (e.g., 0.6) when users expect conceptually related results
- **Decrease VECTOR_ONLY_WEIGHT** (e.g., 0.1) to heavily penalize results without keyword matches
- **Note**: FTS_WEIGHT + VECTOR_WEIGHT should equal 1.0 for normalized scoring

### Database Management

**Database Location**

Per-user databases are stored at:
```
Databases/user_databases/{user_id}/Kanban.db
```

**Backup**

SQLite databases can be backed up using standard tools:
```bash
# Direct copy (ensure no active connections)
cp Databases/user_databases/1/Kanban.db backups/

# Using sqlite3
sqlite3 Databases/user_databases/1/Kanban.db ".backup 'backup.db'"
```

For production, consider using Litestream for continuous replication.

**FTS5 Index**

The FTS5 index is automatically maintained via triggers. If you need to rebuild:
```sql
-- Rebuild FTS index
INSERT INTO kanban_cards_fts(kanban_cards_fts) VALUES('rebuild');
```

**ChromaDB Integration**

Vector search requires ChromaDB to be configured. Collections are named:
```
kanban_user_{user_id}
```

To check if vector search is available:
```bash
curl "http://localhost:8000/api/v1/kanban/search/status"
```

### Monitoring

**Key Metrics to Monitor**

1. **Search Performance**
   - P95 latency for `/search` endpoint (target: <200ms)
   - FTS fallback rate (when vector search fails)

2. **Database Health**
   - SQLite database size per user
   - FTS5 index size
   - Active connection count

3. **Usage Patterns**
   - Boards created per user
   - Cards per board
   - Search queries per day
   - Search mode distribution (fts/vector/hybrid)

**Log Messages**

The module logs to the standard application logger. Key log patterns:

```
# Vector search fallback
WARNING - Vector search failed, falling back to FTS: {error}
WARNING - Vector search unavailable, falling back to FTS

# Hybrid search issues
WARNING - Failed to fetch vector-only cards in hybrid search: {error}
WARNING - Hybrid search failed, using FTS only: {error}

# Configuration warnings
WARNING - Invalid float value for KANBAN_SEARCH_FTS_WEIGHT: {value}, using default 0.6
```

**Health Checks**

Check search status endpoint for system health:
```bash
curl "http://localhost:8000/api/v1/kanban/search/status"
```

Expected healthy response:
```json
{
  "fts_available": true,
  "vector_available": true,
  "hybrid_available": true,
  "default_mode": "fts",
  "supported_modes": ["fts", "vector", "hybrid"],
  "scoring_weights": {
    "fts_weight": 0.6,
    "vector_weight": 0.4,
    "vector_only_weight": 0.3
  }
}
```

---

## Troubleshooting

### Common Issues

**"Search query is required" error**
- Ensure the `q` parameter (GET) or `query` field (POST) is provided and not empty

**Search returns 0 results for special characters**
- FTS5 doesn't index special characters like `%`, `_`, `*` as standalone terms
- Search for words containing those characters instead (e.g., search "complete" to find "100% complete")

**Vector/hybrid search falls back to FTS**
- ChromaDB may not be configured or available
- Check `/search/status` endpoint for `vector_available: false`
- Review logs for ChromaDB connection errors

**Slow search performance**
- Large result sets: reduce `per_page` parameter
- Complex label filters: ensure proper indexes exist
- Consider FTS mode for keyword-heavy queries

**409 Conflict on create**
- The `client_id` already exists for this entity type
- Use a unique `client_id` or omit it for server-generated IDs

---

## Version History

- **v0.1** (2025-12): Initial release with full CRUD, search, and vector integration
