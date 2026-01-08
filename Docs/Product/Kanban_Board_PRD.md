# PRD: Kanban Board Module for tldw_server

Version: 0.1
Owner: Core Maintainers (Server/API)
Status: Draft
Updated: 2025-12-16

Related: Project_Guidelines.md, AGENTS.md, Content_Collections_PRD.md, Workflows_PRD.md

---

## 1. Summary

Add a Trello-like Kanban board module to tldw_server, enabling users to organize tasks, ideas, and research workflows visually. The module provides boards, lists (columns), and cards with rich features including checklists, comments, labels, and due dates. Cards integrate with the existing RAG infrastructure for search and can be linked to media items, notes, and other content.

**Key differentiators from generic Kanban:**
- Full RAG integration: Cards are searchable via FTS5 and vector embeddings
- Content linking: Cards can reference media items, notes, and research content
- Workflow compatibility: Kanban state can be queried/updated via the Workflows module

---

## 2. Goals and Non-Goals

### Goals (MVP)
- [x] Single-user Kanban boards with full CRUD operations
- [x] Lists (columns) with drag-and-drop ordering support via position field
- [x] Cards with: title, description (markdown), position, due dates, labels
- [x] Checklists: multiple per card, with items that can be checked/unchecked
- [x] Comments: flat comments on cards with timestamps
- [x] Activity log: track all changes to cards, lists, and boards
- [x] Labels: board-scoped, color-coded labels assignable to cards
- [x] FTS5 search across card titles and descriptions
- [x] ChromaDB embeddings for vector search
- [x] Link cards to existing media items and notes
- [x] REST API following existing tldw_server patterns

### Non-Goals (MVP)
- Multi-user collaboration / board sharing
- File attachments on cards
- Member assignment to cards
- WebSocket real-time sync (frontend will poll or use optimistic updates)
- Automation rules / Butler-style triggers
- Board templates
- Custom fields
- Card cover images

### Future Considerations (v0.2+)
- Board templates and duplication
- Automation rules (when card moves to X, do Y)
- Custom fields per board
- Card attachments
- WebSocket for real-time collaboration
- Board activity dashboard
- Calendar view of cards by due date

---

## 3. Personas and Value

- **Researcher**: Organize research projects across stages (To Read, Reading, Summarized, Archived)
- **Content Creator**: Track content pipeline (Ideas, Drafting, Review, Published)
- **Power User**: Manage complex workflows with multiple boards and cross-linked content
- **Casual User**: Simple task tracking integrated with their knowledge base

Primary value: Visual task organization that integrates with tldw_server's knowledge management, search, and RAG capabilities.

---

## 4. Success Metrics

- Board creation and usage rate
- Cards created per user per week
- Search queries that include Kanban content
- Average cards per board
- Checklist completion rate
- API response latency P95 < 200ms for board operations

---

## 5. Scope

### In-Scope
- Boards: CRUD, archive/restore, search
- Lists: CRUD, reorder within board
- Cards: CRUD, move between lists, reorder within list
- Card features: description (markdown), due dates, labels, checklists, comments
- Activity log for boards, lists, and cards
- FTS5 indexing of card content
- ChromaDB embeddings for cards
- Links to media items and notes
- Per-user database isolation following existing patterns

### Out-of-Scope (MVP)
- Board sharing / collaboration
- File attachments
- Member assignments
- Real-time WebSocket updates
- Automation / triggers
- Custom fields
- Board templates

---

## 6. User Stories (MVP)

1. As a user, I can create a board to organize a research project
2. As a user, I can add lists (columns) to represent workflow stages
3. As a user, I can create cards with titles, descriptions, and due dates
4. As a user, I can drag cards between lists to update their status
5. As a user, I can add checklists to cards to track sub-tasks
6. As a user, I can comment on cards to add notes or context
7. As a user, I can label cards with color-coded tags for categorization
8. As a user, I can search across all my cards using keywords
9. As a user, I can link a card to an existing media item or note
10. As a user, I can view the activity history of a card
11. As a user, I can archive boards/lists/cards and restore them later

---

## 7. UX Flows (API-Focused for Frontend Handoff)

### Board Management
- `GET /api/v1/kanban/boards` - List all boards with counts (excludes archived/deleted by default)
  - Query params: `include_archived`, `include_deleted`
- `POST /api/v1/kanban/boards` - Create new board
- `GET /api/v1/kanban/boards/{id}` - Get board with all lists and cards (nested)
- `PATCH /api/v1/kanban/boards/{id}` - Update board name/description/settings (including activity_retention_days)
- `POST /api/v1/kanban/boards/{id}/archive` - Archive board (hidden, fully restorable)
- `POST /api/v1/kanban/boards/{id}/unarchive` - Unarchive board
- `DELETE /api/v1/kanban/boards/{id}` - Soft delete (marked for cleanup after retention period)
- `POST /api/v1/kanban/boards/{id}/restore` - Restore soft-deleted board (within retention period)

### List Management
- `GET /api/v1/kanban/boards/{board_id}/lists` - Get lists for board (excludes archived/deleted by default)
  - Query params: `include_archived`, `include_deleted`
- `POST /api/v1/kanban/boards/{board_id}/lists` - Create list
- `PATCH /api/v1/kanban/lists/{id}` - Update list (name, position)
- `POST /api/v1/kanban/lists/{id}/archive` - Archive list (and its cards)
- `POST /api/v1/kanban/lists/{id}/unarchive` - Unarchive list (and its cards)
- `DELETE /api/v1/kanban/lists/{id}` - Soft delete list
- `POST /api/v1/kanban/lists/{id}/restore` - Restore soft-deleted list
- `POST /api/v1/kanban/boards/{board_id}/lists/reorder` - Batch reorder all lists in board

### Card Management
- `GET /api/v1/kanban/lists/{list_id}/cards` - Get cards in list (excludes archived/deleted by default)
  - Query params: `include_archived`, `include_deleted`
- `POST /api/v1/kanban/lists/{list_id}/cards` - Create card
- `GET /api/v1/kanban/cards/{id}` - Get card with all details
- `PATCH /api/v1/kanban/cards/{id}` - Update card fields
- `POST /api/v1/kanban/cards/{id}/archive` - Archive card
- `POST /api/v1/kanban/cards/{id}/unarchive` - Unarchive card
- `DELETE /api/v1/kanban/cards/{id}` - Soft delete card
- `POST /api/v1/kanban/cards/{id}/restore` - Restore soft-deleted card
- `POST /api/v1/kanban/cards/{id}/move` - Move to different list
- `POST /api/v1/kanban/cards/{id}/copy` - Duplicate card (with checklists)
- `POST /api/v1/kanban/lists/{list_id}/cards/reorder` - Batch reorder cards in list

### Bulk Operations
- `POST /api/v1/kanban/cards/bulk-move` - Move multiple cards to a list
- `POST /api/v1/kanban/cards/bulk-archive` - Archive multiple cards
- `POST /api/v1/kanban/cards/bulk-delete` - Soft delete multiple cards
- `POST /api/v1/kanban/cards/bulk-label` - Add/remove labels from multiple cards

### Filtering
- `GET /api/v1/kanban/boards/{id}/cards` - Get all cards in board with filters
  - Query params: `label_ids`, `due_before`, `due_after`, `overdue` (true = due_date < now AND due_complete = false), `has_due_date` (true|false), `priority`, `has_checklist`, `is_complete`

### Card Features
- `GET /api/v1/kanban/cards/{id}/checklists` - Get checklists
- `POST /api/v1/kanban/cards/{id}/checklists` - Add checklist
- `PATCH /api/v1/kanban/checklists/{id}` - Update checklist
- `DELETE /api/v1/kanban/checklists/{id}` - Delete checklist
- `POST /api/v1/kanban/checklists/{id}/items` - Add item
- `PATCH /api/v1/kanban/checklist-items/{id}` - Toggle/update item
- `DELETE /api/v1/kanban/checklist-items/{id}` - Delete item
- `POST /api/v1/kanban/checklists/{id}/toggle-all` - Check or uncheck all items in checklist
  - Body: `{"checked": true}` or `{"checked": false}`

- `GET /api/v1/kanban/cards/{id}/comments` - Get comments
- `POST /api/v1/kanban/cards/{id}/comments` - Add comment
- `PATCH /api/v1/kanban/comments/{id}` - Edit comment
- `DELETE /api/v1/kanban/comments/{id}` - Delete comment

- `GET /api/v1/kanban/cards/{id}/activities` - Get activity log for card
- `GET /api/v1/kanban/lists/{id}/activities` - Get activity log for list
- `GET /api/v1/kanban/boards/{id}/activities` - Get board-level activities
  - Query params: `created_after`, `created_before`, `action_type`, `entity_type`, `list_id`, `card_id`

### Labels
- `GET /api/v1/kanban/boards/{id}/labels` - Get board labels
- `POST /api/v1/kanban/boards/{id}/labels` - Create label
- `PATCH /api/v1/kanban/labels/{id}` - Update label
- `DELETE /api/v1/kanban/labels/{id}` - Delete label
- `POST /api/v1/kanban/cards/{id}/labels/{label_id}` - Assign label to card
- `DELETE /api/v1/kanban/cards/{id}/labels/{label_id}` - Remove label from card

### Content Links
- `GET /api/v1/kanban/cards/{id}/links` - Get linked content
- `POST /api/v1/kanban/cards/{id}/links` - Link media item or note
- `DELETE /api/v1/kanban/cards/{id}/links/{link_id}` - Remove link

### Search
- `GET /api/v1/kanban/search?q=...` - Search across cards (FTS + vector)
  - Query params: `q`, `board_id`, `label_ids`, `priority`, `include_archived`, `search_mode` (fts|vector|hybrid, default: fts)

### Export/Import
- `GET /api/v1/kanban/boards/{id}/export` - Export board as JSON (includes lists, cards, checklists, labels)
  - Export format matches the nested board response structure (see "Get Board with Lists and Cards" example)
  - Includes: board metadata, all labels, all lists with their cards, all checklists/items, all comments
  - Excludes: activity log (too large), internal IDs (uses UUIDs for portability)
- `POST /api/v1/kanban/boards/import` - Import board from JSON (tldw format or Trello format)
  - Trello import maps: boards→boards, lists→lists, cards→cards, checklists→checklists, labels→labels
  - Trello features not imported: attachments, members, power-ups, custom fields, stickers

---

## 8. Functional Requirements

### 8.1 Boards
- Fields: id, uuid, user_id, client_id, name, description, archived, archived_at, activity_retention_days, created_at, updated_at, deleted, deleted_at, version, metadata
- **Archive vs Delete**:
  - `archived=1`: Board is archived (hidden from default views, fully restorable with all content)
  - `deleted=1`: Board is soft-deleted (marked for cleanup, can be recovered within retention period)
  - Hard delete: Permanent removal (only via explicit purge or retention cleanup)
- Boards are user-scoped (no sharing)
- Maximum 50 boards per user (configurable)

### 8.2 Lists
- Fields: id, uuid, board_id, client_id, name, position, archived, archived_at, created_at, updated_at, deleted, deleted_at, version
- Position is 0-indexed integer for ordering
- Lists belong to exactly one board
- **Archive**: Hides list and its cards from default views; fully restorable
- **Soft delete**: Marks for cleanup; cascades to cards
- Maximum 20 lists per board (configurable)

### 8.3 Cards
- Fields: id, uuid, board_id, list_id, client_id, title, description, position, due_date, due_complete, start_date, priority, archived, archived_at, created_at, updated_at, deleted, deleted_at, version, metadata
- `board_id` denormalized for efficient queries (activity logging, search, filtering)
- Description supports markdown (64KB limit)
- Position for ordering within list
- Due date with completion flag; optional start_date for planning
- Priority: nullable enum (`low`, `medium`, `high`, `urgent`)
- **Archive**: Hides card from default views; fully restorable
- **Soft delete**: Marks for cleanup; preserves history until retention expires
- Maximum 500 cards per board, 200 cards per list (configurable)

### 8.4 Labels
- Fields: id, uuid, board_id, name, color, created_at, updated_at
- Board-scoped (each board has its own labels)
- Predefined color palette (red, orange, yellow, green, blue, purple, pink, gray)
- Many-to-many relationship with cards via card_labels join table
- Maximum 20 labels per board

### 8.5 Checklists
- Fields: id, uuid, card_id, name, position, created_at, updated_at
- Multiple checklists per card
- Position for ordering checklists on card
- No `client_id`: Checklists are always created in context of a card and don't require offline-first sync

### 8.6 Checklist Items
- Fields: id, uuid, checklist_id, name, position, checked, checked_at, created_at, updated_at
- Position for ordering within checklist
- checked_at timestamp when item is completed

### 8.7 Comments
- Fields: id, uuid, card_id, user_id, content, created_at, updated_at, deleted
- Markdown support in content (16KB limit)
- Soft delete for audit trail
- Flat comments only (no threading in MVP; can add `parent_comment_id` in v0.2)

### 8.8 Activity Log
- Fields: id, uuid, board_id, list_id (nullable), card_id (nullable), user_id, action_type, entity_type, entity_id, details_json, created_at
- Track all entity changes:
  - Board: `board_created`, `board_updated`, `board_archived`, `board_unarchived`, `board_deleted`, `board_restored`
  - List: `list_created`, `list_updated`, `list_moved`, `list_archived`, `list_unarchived`, `list_deleted`, `list_restored`
  - Card: `card_created`, `card_updated`, `card_moved`, `card_archived`, `card_unarchived`, `card_deleted`, `card_restored`
  - Labels: `label_created`, `label_assigned`, `label_removed`
  - Checklists: `checklist_added`, `checklist_item_checked`, `checklist_item_unchecked`
  - Comments: `comment_added`, `comment_edited`, `comment_deleted`
- Queryable by board, list, card, or date range (via `created_after`, `created_before` params)
- **Retention** (no soft-delete; pruned directly):
  - Default: 30 days (configurable via `KANBAN_ACTIVITY_RETENTION_DAYS`)
  - User can extend/shorten per board via board settings
  - Background job prunes old activities based on retention settings
  - Activities for deleted entities are pruned when entity is hard-deleted

### 8.9 Content Links
- Fields: id, uuid, card_id, linked_type (media|note), linked_id, created_at
- Bidirectional lookup: cards by linked content, content by card

### 8.10 Search & RAG Integration
- FTS5 virtual table over card titles and descriptions
- FTS triggers must handle soft delete: remove from index when `deleted=1`, restore when `deleted=0`
- ChromaDB collection: `kanban_user_{user_id}` (underscore naming for compatibility)
- Embeddings include: title, description, labels, checklist items
- Embedding strategy:
  - Async embedding via Redis queue (like other modules)
  - Re-embed on card content change (title, description, labels, checklist items)
  - Graceful degradation: search works without embeddings if queue is down
- Expose via existing RAG search endpoints with `source=kanban`

---

## 9. Non-Functional Requirements

- Performance: Board load (with all lists/cards) < 500ms for typical boards
- Reliability: Soft delete for all entities; optimistic locking via version field
- Storage: Per-user SQLite database at `<USER_DB_BASE_DIR>/<user_id>/Kanban.db`
- Concurrency: Thread-safe database access with proper connection management
- Limits: Configurable via environment variables (KANBAN_MAX_BOARDS, etc.)

---

## 10. Data Model

### Database: `<USER_DB_BASE_DIR>/<user_id>/Kanban.db`

```sql
-- Boards
CREATE TABLE kanban_boards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL DEFAULT (lower(hex(randomblob(16)))),
    user_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    archived INTEGER DEFAULT 0,
    archived_at TIMESTAMP,
    activity_retention_days INTEGER,  -- NULL means use system default
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0,
    deleted_at TIMESTAMP,
    version INTEGER DEFAULT 1,
    metadata JSON
);
CREATE INDEX idx_boards_user_archived ON kanban_boards(user_id, archived);
CREATE INDEX idx_boards_deleted ON kanban_boards(deleted, deleted_at) WHERE deleted = 1;
CREATE UNIQUE INDEX idx_boards_client_id ON kanban_boards(user_id, client_id);

-- Lists
CREATE TABLE kanban_lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL DEFAULT (lower(hex(randomblob(16)))),
    board_id INTEGER NOT NULL REFERENCES kanban_boards(id) ON DELETE CASCADE,
    client_id TEXT NOT NULL,
    name TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    archived INTEGER DEFAULT 0,
    archived_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0,
    deleted_at TIMESTAMP,
    version INTEGER DEFAULT 1
);
CREATE INDEX idx_lists_board_position ON kanban_lists(board_id, position);
CREATE INDEX idx_lists_board_archived ON kanban_lists(board_id, archived);
CREATE INDEX idx_lists_deleted ON kanban_lists(deleted, deleted_at) WHERE deleted = 1;
CREATE UNIQUE INDEX idx_lists_client_id ON kanban_lists(board_id, client_id);

-- Cards
CREATE TABLE kanban_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL DEFAULT (lower(hex(randomblob(16)))),
    board_id INTEGER NOT NULL REFERENCES kanban_boards(id) ON DELETE CASCADE,
    list_id INTEGER NOT NULL REFERENCES kanban_lists(id) ON DELETE CASCADE,
    client_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    position INTEGER NOT NULL DEFAULT 0,
    due_date TIMESTAMP,
    due_complete INTEGER DEFAULT 0,
    start_date TIMESTAMP,
    priority TEXT CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    archived INTEGER DEFAULT 0,
    archived_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0,
    deleted_at TIMESTAMP,
    version INTEGER DEFAULT 1,
    metadata JSON
);
CREATE INDEX idx_cards_board ON kanban_cards(board_id);
CREATE INDEX idx_cards_list_position ON kanban_cards(list_id, position);
CREATE INDEX idx_cards_list_archived ON kanban_cards(list_id, archived);
CREATE INDEX idx_cards_due_date ON kanban_cards(due_date) WHERE due_date IS NOT NULL;
CREATE INDEX idx_cards_priority ON kanban_cards(board_id, priority) WHERE priority IS NOT NULL;
CREATE INDEX idx_cards_deleted ON kanban_cards(deleted, deleted_at) WHERE deleted = 1;
CREATE UNIQUE INDEX idx_cards_client_id ON kanban_cards(board_id, client_id);

-- Labels
CREATE TABLE kanban_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL DEFAULT (lower(hex(randomblob(16)))),
    board_id INTEGER NOT NULL REFERENCES kanban_boards(id) ON DELETE CASCADE,
    name TEXT,
    color TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_labels_board ON kanban_labels(board_id);

-- Card-Label join
CREATE TABLE kanban_card_labels (
    card_id INTEGER NOT NULL REFERENCES kanban_cards(id) ON DELETE CASCADE,
    label_id INTEGER NOT NULL REFERENCES kanban_labels(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (card_id, label_id)
);

-- Checklists
CREATE TABLE kanban_checklists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL DEFAULT (lower(hex(randomblob(16)))),
    card_id INTEGER NOT NULL REFERENCES kanban_cards(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_checklists_card ON kanban_checklists(card_id);

-- Checklist Items
CREATE TABLE kanban_checklist_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL DEFAULT (lower(hex(randomblob(16)))),
    checklist_id INTEGER NOT NULL REFERENCES kanban_checklists(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    checked INTEGER DEFAULT 0,
    checked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_checklist_items_checklist ON kanban_checklist_items(checklist_id);

-- Comments
CREATE TABLE kanban_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL DEFAULT (lower(hex(randomblob(16)))),
    card_id INTEGER NOT NULL REFERENCES kanban_cards(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0
);
CREATE INDEX idx_comments_card ON kanban_comments(card_id);

-- Activity Log
CREATE TABLE kanban_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL DEFAULT (lower(hex(randomblob(16)))),
    board_id INTEGER NOT NULL REFERENCES kanban_boards(id) ON DELETE CASCADE,
    list_id INTEGER REFERENCES kanban_lists(id) ON DELETE SET NULL,
    card_id INTEGER REFERENCES kanban_cards(id) ON DELETE SET NULL,
    user_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    details JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_activities_board ON kanban_activities(board_id, created_at DESC);
CREATE INDEX idx_activities_list ON kanban_activities(list_id) WHERE list_id IS NOT NULL;
CREATE INDEX idx_activities_card ON kanban_activities(card_id) WHERE card_id IS NOT NULL;
CREATE INDEX idx_activities_created ON kanban_activities(created_at);  -- For retention cleanup

-- Content Links
CREATE TABLE kanban_card_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL DEFAULT (lower(hex(randomblob(16)))),
    card_id INTEGER NOT NULL REFERENCES kanban_cards(id) ON DELETE CASCADE,
    linked_type TEXT NOT NULL CHECK (linked_type IN ('media', 'note')),
    linked_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(card_id, linked_type, linked_id)
);
CREATE INDEX idx_card_links_card ON kanban_card_links(card_id);
CREATE INDEX idx_card_links_linked ON kanban_card_links(linked_type, linked_id);

-- FTS5 for card search
CREATE VIRTUAL TABLE kanban_cards_fts USING fts5(
    title,
    description,
    content='kanban_cards',
    content_rowid='id'
);

-- Triggers for FTS sync (handles archive and soft delete)
-- Only index cards that are neither archived nor deleted
CREATE TRIGGER kanban_cards_ai AFTER INSERT ON kanban_cards
WHEN NEW.deleted = 0 AND NEW.archived = 0 BEGIN
    INSERT INTO kanban_cards_fts(rowid, title, description)
    VALUES (NEW.id, NEW.title, NEW.description);
END;

CREATE TRIGGER kanban_cards_ad AFTER DELETE ON kanban_cards BEGIN
    INSERT INTO kanban_cards_fts(kanban_cards_fts, rowid, title, description)
    VALUES ('delete', OLD.id, OLD.title, OLD.description);
END;

-- Handle content updates, archive, and soft delete/restore
CREATE TRIGGER kanban_cards_au AFTER UPDATE ON kanban_cards BEGIN
    -- Remove old entry
    INSERT INTO kanban_cards_fts(kanban_cards_fts, rowid, title, description)
    VALUES ('delete', OLD.id, OLD.title, OLD.description);
    -- Only re-add if not deleted AND not archived
    INSERT INTO kanban_cards_fts(rowid, title, description)
    SELECT NEW.id, NEW.title, NEW.description
    WHERE NEW.deleted = 0 AND NEW.archived = 0;
END;
```

Notes on FTS sync behavior:
- Restore/unarchive operations (transition to deleted=0 and archived=0) re-index via `kanban_cards_au`; tests should assert this path.
- If a card is archived and later soft-deleted, restoring deleted=0 while archived=1 keeps it out of FTS until unarchived; only the (deleted=0, archived=0) state is searchable.
- Edge case to test: archived=1 -> deleted=1 -> deleted=0 should still be excluded from FTS until archived=0.

### ChromaDB Collection
- Collection name: `kanban_user_{user_id}` (underscore for compatibility)
- Document: Card title + description + label names + checklist item names
- Metadata: card_id, board_id, list_id, due_date, priority, labels, created_at

---

## 11. API Design

### Base Path: `/api/v1/kanban`

### Authentication
- Uses existing AuthNZ (single-user API key or multi-user JWT)
- All endpoints require authentication
- User isolation enforced at database level

### Client ID
- `client_id` is a required field on boards, lists, and cards for idempotency and sync
- Client generates a unique ID (UUID recommended) and includes it in create requests
- Server rejects duplicates with 409 Conflict if same `client_id` already exists for user
- Enables safe retries and offline-first sync patterns

### Rate Limiting
- `kanban.boards.create`: 10/minute (conservative; assumes 1-2 boards/day per user)
- `kanban.cards.create`: 60/minute (~1/sec burst). Typical active work is ~3-5 cards/min; headroom allows quick-capture bursts and sync replays while staying low enough to protect DB/FTS load.
- `kanban.cards.bulk_*`: 20/minute (bulk move, archive, label operations; supports batch workflows)
- `kanban.search`: 30/minute (interactive search without heavy load)
- Others: default limits

Tuning guidance: start conservative.
- Monitor 429 response rates and DB query latency (target P95 < 200ms for card creation).
- If <1% of requests hit 429 and DB latency is healthy, increase limits by 50% increments via RG policy.
- All limits are per-user (no cross-user quota sharing).
- Expect short bursts from power users to hit limits briefly; keep as acceptable UX or raise after observing sustained 429s.

### Response Format
All responses follow existing tldw_server patterns:
```json
{
    "id": 1,
    "uuid": "abc123...",
    "name": "My Board",
    "created_at": "2025-12-13T10:00:00Z",
    "updated_at": "2025-12-13T10:00:00Z",
    "version": 1
}
```

### Pagination
List endpoints support:
- `page`: Page number (default 1)
- `per_page`: Items per page (default 20, max 100)
- `include_archived`: Include archived items (default false)
- `include_deleted`: Include soft-deleted items (default false)

### Optimistic Locking
Update endpoints accept `X-Expected-Version` header for conflict detection.

### API Examples

#### Create Board
```http
POST /api/v1/kanban/boards
Content-Type: application/json
Authorization: Bearer <token>

{
    "client_id": "cli_a1b2c3d4e5f6",
    "name": "Research Project Alpha",
    "description": "Tracking all research tasks for Project Alpha"
}
```

Response (201 Created):
```json
{
    "id": 1,
    "uuid": "a1b2c3d4e5f6...",
    "client_id": "cli_a1b2c3d4e5f6",
    "name": "Research Project Alpha",
    "description": "Tracking all research tasks for Project Alpha",
    "user_id": "user_123",
    "created_at": "2025-12-13T10:00:00Z",
    "updated_at": "2025-12-13T10:00:00Z",
    "version": 1,
    "archived": false,
    "deleted": false
}
```

#### Get Board with Lists and Cards
```http
GET /api/v1/kanban/boards/1?include_lists=true&include_cards=true
Authorization: Bearer <token>
```

Response (200 OK):
```json
{
    "id": 1,
    "uuid": "a1b2c3d4e5f6...",
    "name": "Research Project Alpha",
    "description": "Tracking all research tasks for Project Alpha",
    "created_at": "2025-12-13T10:00:00Z",
    "updated_at": "2025-12-13T10:00:00Z",
    "version": 1,
    "labels": [
        {"id": 1, "uuid": "lbl1...", "name": "Urgent", "color": "red"},
        {"id": 2, "uuid": "lbl2...", "name": "Research", "color": "blue"}
    ],
    "total_cards": 1,
    "lists": [
        {
            "id": 1,
            "uuid": "lst1...",
            "name": "To Do",
            "position": 0,
            "card_count": 1,
            "archived": false,
            "cards": [
                {
                    "id": 1,
                    "uuid": "crd1...",
                    "title": "Review paper on ML transformers",
                    "description": "Read and summarize the key findings",
                    "position": 0,
                    "due_date": "2025-12-20T00:00:00Z",
                    "due_complete": false,
                    "start_date": null,
                    "priority": "medium",
                    "archived": false,
                    "labels": [{"id": 2, "name": "Research", "color": "blue"}],
                    "checklist_count": 1,
                    "checklist_complete": 2,
                    "checklist_total": 5,
                    "comment_count": 3,
                    "created_at": "2025-12-13T10:05:00Z"
                }
            ]
        },
        {
            "id": 2,
            "uuid": "lst2...",
            "name": "In Progress",
            "position": 1,
            "card_count": 0,
            "archived": false,
            "cards": []
        },
        {
            "id": 3,
            "uuid": "lst3...",
            "name": "Done",
            "position": 2,
            "card_count": 0,
            "archived": false,
            "cards": []
        }
    ]
}
```

#### Create List
```http
POST /api/v1/kanban/boards/1/lists
Content-Type: application/json
Authorization: Bearer <token>

{
    "client_id": "cli_lst_review_001",
    "name": "Review",
    "position": 2
}
```

Response (201 Created):
```json
{
    "id": 4,
    "uuid": "lst4...",
    "client_id": "cli_lst_review_001",
    "board_id": 1,
    "name": "Review",
    "position": 2,
    "created_at": "2025-12-13T11:00:00Z",
    "updated_at": "2025-12-13T11:00:00Z",
    "version": 1
}
```

#### Create Card
```http
POST /api/v1/kanban/lists/1/cards
Content-Type: application/json
Authorization: Bearer <token>

{
    "client_id": "cli_crd_transformer_001",
    "title": "Summarize transformer paper",
    "description": "## Key Points\n\n- Architecture overview\n- Training methodology\n- Results comparison",
    "due_date": "2025-12-25T00:00:00Z",
    "label_ids": [2]
}
```

Response (201 Created):
```json
{
    "id": 2,
    "uuid": "crd2...",
    "client_id": "cli_crd_transformer_001",
    "board_id": 1,
    "list_id": 1,
    "title": "Summarize transformer paper",
    "description": "## Key Points\n\n- Architecture overview\n- Training methodology\n- Results comparison",
    "position": 1,
    "due_date": "2025-12-25T00:00:00Z",
    "due_complete": false,
    "labels": [{"id": 2, "name": "Research", "color": "blue"}],
    "created_at": "2025-12-13T11:05:00Z",
    "updated_at": "2025-12-13T11:05:00Z",
    "version": 1
}
```

#### Move Card to Different List
```http
POST /api/v1/kanban/cards/2/move
Content-Type: application/json
Authorization: Bearer <token>

{
    "target_list_id": 2,
    "position": 0
}
```

Response (200 OK):
```json
{
    "id": 2,
    "uuid": "crd2...",
    "list_id": 2,
    "title": "Summarize transformer paper",
    "position": 0,
    "version": 2,
    "updated_at": "2025-12-13T12:00:00Z"
}
```

#### Add Checklist to Card
```http
POST /api/v1/kanban/cards/2/checklists
Content-Type: application/json
Authorization: Bearer <token>

{
    "name": "Summary Tasks",
    "items": [
        {"name": "Read introduction"},
        {"name": "Understand architecture diagram"},
        {"name": "Note key results"},
        {"name": "Write summary paragraph"}
    ]
}
```

Response (201 Created):
```json
{
    "id": 1,
    "uuid": "chk1...",
    "card_id": 2,
    "name": "Summary Tasks",
    "position": 0,
    "items": [
        {"id": 1, "uuid": "itm1...", "name": "Read introduction", "position": 0, "checked": false},
        {"id": 2, "uuid": "itm2...", "name": "Understand architecture diagram", "position": 1, "checked": false},
        {"id": 3, "uuid": "itm3...", "name": "Note key results", "position": 2, "checked": false},
        {"id": 4, "uuid": "itm4...", "name": "Write summary paragraph", "position": 3, "checked": false}
    ],
    "created_at": "2025-12-13T12:10:00Z"
}
```

#### Toggle Checklist Item
```http
PATCH /api/v1/kanban/checklist-items/1
Content-Type: application/json
Authorization: Bearer <token>

{
    "checked": true
}
```

Response (200 OK):
```json
{
    "id": 1,
    "uuid": "itm1...",
    "name": "Read introduction",
    "position": 0,
    "checked": true,
    "checked_at": "2025-12-13T14:00:00Z",
    "updated_at": "2025-12-13T14:00:00Z"
}
```

#### Add Comment to Card
```http
POST /api/v1/kanban/cards/2/comments
Content-Type: application/json
Authorization: Bearer <token>

{
    "content": "Found a related paper that might be useful: [Link to paper](https://example.com/paper.pdf)"
}
```

Response (201 Created):
```json
{
    "id": 1,
    "uuid": "cmt1...",
    "card_id": 2,
    "user_id": "user_123",
    "content": "Found a related paper that might be useful: [Link to paper](https://example.com/paper.pdf)",
    "created_at": "2025-12-13T15:00:00Z",
    "updated_at": "2025-12-13T15:00:00Z"
}
```

#### Create Label
```http
POST /api/v1/kanban/boards/1/labels
Content-Type: application/json
Authorization: Bearer <token>

{
    "name": "High Priority",
    "color": "red"
}
```

Response (201 Created):
```json
{
    "id": 3,
    "uuid": "lbl3...",
    "board_id": 1,
    "name": "High Priority",
    "color": "red",
    "created_at": "2025-12-13T10:30:00Z",
    "updated_at": "2025-12-13T10:30:00Z"
}
```

#### Assign Label to Card
```http
POST /api/v1/kanban/cards/2/labels/3
Authorization: Bearer <token>
```

Response (200 OK):
```json
{
    "card_id": 2,
    "label_id": 3,
    "created_at": "2025-12-13T15:30:00Z"
}
```

#### Link Card to Media Item
```http
POST /api/v1/kanban/cards/2/links
Content-Type: application/json
Authorization: Bearer <token>

{
    "linked_type": "media",
    "linked_id": "media_abc123"
}
```

Response (201 Created):
```json
{
    "id": 1,
    "uuid": "lnk1...",
    "card_id": 2,
    "linked_type": "media",
    "linked_id": "media_abc123",
    "created_at": "2025-12-13T16:00:00Z"
}
```

#### Search Cards
```http
GET /api/v1/kanban/search?q=transformer&board_id=1&include_archived=false
Authorization: Bearer <token>
```

Response (200 OK):
```json
{
    "results": [
        {
            "id": 2,
            "uuid": "crd2...",
            "title": "Summarize transformer paper",
            "description": "## Key Points\n\n- Architecture overview...",
            "board_id": 1,
            "board_name": "Research Project Alpha",
            "list_id": 2,
            "list_name": "In Progress",
            "due_date": "2025-12-25T00:00:00Z",
            "labels": [{"name": "Research", "color": "blue"}],
            "score": 0.95,
            "highlight": "Summarize <mark>transformer</mark> paper"
        }
    ],
    "total": 1,
    "page": 1,
    "per_page": 20
}
```

#### Get Card Activity
```http
GET /api/v1/kanban/cards/2/activities?page=1&per_page=20
Authorization: Bearer <token>
```

Response (200 OK):
```json
{
    "activities": [
        {
            "id": 5,
            "uuid": "act5...",
            "action_type": "comment_added",
            "entity_type": "comment",
            "entity_id": 1,
            "user_id": "user_123",
            "details": {"content_preview": "Found a related paper..."},
            "created_at": "2025-12-13T15:00:00Z"
        },
        {
            "id": 4,
            "uuid": "act4...",
            "action_type": "checklist_item_checked",
            "entity_type": "checklist_item",
            "entity_id": 1,
            "user_id": "user_123",
            "details": {"item_name": "Read introduction"},
            "created_at": "2025-12-13T14:00:00Z"
        },
        {
            "id": 3,
            "uuid": "act3...",
            "action_type": "card_moved",
            "entity_type": "card",
            "entity_id": 2,
            "user_id": "user_123",
            "details": {"from_list": "To Do", "to_list": "In Progress"},
            "created_at": "2025-12-13T12:00:00Z"
        },
        {
            "id": 2,
            "uuid": "act2...",
            "action_type": "checklist_added",
            "entity_type": "checklist",
            "entity_id": 1,
            "user_id": "user_123",
            "details": {"checklist_name": "Summary Tasks"},
            "created_at": "2025-12-13T12:10:00Z"
        },
        {
            "id": 1,
            "uuid": "act1...",
            "action_type": "card_created",
            "entity_type": "card",
            "entity_id": 2,
            "user_id": "user_123",
            "details": {"title": "Summarize transformer paper"},
            "created_at": "2025-12-13T11:05:00Z"
        }
    ],
    "total": 5,
    "page": 1,
    "per_page": 20
}
```

#### Reorder Lists
```http
POST /api/v1/kanban/boards/1/lists/reorder
Content-Type: application/json
Authorization: Bearer <token>

{
    "list_positions": [
        {"list_id": 1, "position": 0},
        {"list_id": 4, "position": 1},
        {"list_id": 2, "position": 2},
        {"list_id": 3, "position": 3}
    ]
}
```

Response (200 OK):
```json
{
    "success": true,
    "updated_count": 4
}
```

#### Bulk Move Cards
```http
POST /api/v1/kanban/cards/bulk-move
Content-Type: application/json
Authorization: Bearer <token>

{
    "card_ids": [1, 2, 3],
    "target_list_id": 2,
    "position": 0
}
```

Response (200 OK):
```json
{
    "success": true,
    "moved_count": 3,
    "cards": [
        {"id": 1, "list_id": 2, "position": 0, "version": 2},
        {"id": 2, "list_id": 2, "position": 1, "version": 2},
        {"id": 3, "list_id": 2, "position": 2, "version": 2}
    ]
}
```

#### Bulk Archive Cards
```http
POST /api/v1/kanban/cards/bulk-archive
Content-Type: application/json
Authorization: Bearer <token>

{
    "card_ids": [4, 5, 6]
}
```

Response (200 OK):
```json
{
    "success": true,
    "archived_count": 3
}
```

#### Bulk Delete Cards
```http
POST /api/v1/kanban/cards/bulk-delete
Content-Type: application/json
Authorization: Bearer <token>

{
    "card_ids": [7, 8]
}
```

Response (200 OK):
```json
{
    "success": true,
    "deleted_count": 2
}
```

#### Bulk Label Cards
```http
POST /api/v1/kanban/cards/bulk-label
Content-Type: application/json
Authorization: Bearer <token>

{
    "card_ids": [1, 2, 3],
    "add_label_ids": [1, 2],
    "remove_label_ids": [3]
}
```

Response (200 OK):
```json
{
    "success": true,
    "updated_count": 3
}
```

---

## 12. File Structure

```bash
tldw_Server_API/app/
├── api/v1/
│   ├── endpoints/
│   │   ├── kanban_boards.py      # Board CRUD endpoints
│   │   ├── kanban_lists.py       # List CRUD endpoints
│   │   ├── kanban_cards.py       # Card CRUD + features
│   │   └── kanban_search.py      # Search endpoint
│   ├── schemas/
│   │   └── kanban_schemas.py     # All Pydantic models
│   └── API_Deps/
│       └── kanban_deps.py        # DB dependency injection
├── core/
│   ├── DB_Management/
│   │   └── Kanban_DB.py          # Database class
│   └── Kanban/
│       ├── __init__.py
│       ├── board_manager.py      # Board business logic
│       ├── card_manager.py       # Card business logic
│       ├── search.py             # FTS + vector search
│       └── embeddings.py         # ChromaDB integration
└── tests/
    └── kanban/
        ├── test_boards.py
        ├── test_lists.py
        ├── test_cards.py
        ├── test_checklists.py
        ├── test_search.py
        └── conftest.py           # Fixtures
```

---

## 13. Security & Permissions

- User isolation: All queries scoped to authenticated user
- Input validation: Pydantic models with field constraints
- SQL injection: Parameterized queries only (via DB abstractions)
- XSS: Markdown rendering is frontend responsibility; store raw markdown
- Rate limiting: Per-user rate limits on all mutating endpoints

---

## 14. Error Handling

Standard HTTP status codes:
- 400: Invalid input (validation errors)
- 404: Resource not found
- 409: Conflict (version mismatch, duplicate)
- 429: Rate limited
- 500: Internal server error

Error response format:
```json
{
    "detail": "Board not found",
    "error_code": "BOARD_NOT_FOUND"
}
```

---

## 15. Testing Strategy

- Unit: Board/list/card CRUD, position reordering, activity logging
- Integration: Full API endpoint tests with auth
- Property-based: Position ordering invariants; FTS sync invariants across archive/delete transitions (restore/unarchive re-indexing, archived-only restores stay excluded)
- Mocks: ChromaDB for embedding tests
- Markers: `unit`, `integration`
- Coverage target: >= 80%

Example property-based tests (Hypothesis; illustrative):

Note: Fixtures and DB methods below are illustrative pseudo-code; see `conftest.py` for actual implementations.

```python
# tldw_Server_API/tests/kanban/property/test_kanban_properties.py
import pytest
from hypothesis import HealthCheck, given, settings, strategies as st


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
@given(st.lists(st.integers(min_value=1, max_value=10000), min_size=2, max_size=20, unique=True))
def test_positions_monotonic_after_reorder(db, seeded_kanban_list, card_ids):
    # seeded_kanban_list is a fixture that creates a list with the given card_ids
    list_id = seeded_kanban_list(db, card_ids)
    new_order = list(reversed(card_ids))
    db.reorder_cards(list_id=list_id, card_ids=new_order)
    positions = [c.position for c in db.list_cards(list_id=list_id)]
    assert positions == sorted(positions)


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
@given(st.lists(st.tuples(st.booleans(), st.booleans()), min_size=1, max_size=6))
def test_fts_visibility_matches_state(db, seeded_card, transitions):
    # seeded_card is a fixture that inserts a searchable card in the test DB
    card_id = seeded_card(db, title="needle", description="needle")
    for archived, deleted in transitions:
        db.update_card(card_id=card_id, archived=archived, deleted=deleted)
        result_ids = db.search_card_ids(query="needle")
        assert (card_id in result_ids) == (not archived and not deleted)
```

---

## 16. Implementation Roadmap

### Phase 1: Core Data Model & CRUD
- [ ] Kanban_DB.py with schema creation (all tables, indexes, FTS triggers)
- [ ] Board CRUD (create, read, update, soft delete, restore)
- [ ] List CRUD with position management and batch reorder
- [ ] Card CRUD with position management, move, copy
- [ ] Basic Pydantic schemas for all entities
- [ ] API endpoints for boards, lists, cards
- [ ] Restore endpoints for all entities
- [ ] Unit tests for DB layer

### Phase 2: Card Features
- [ ] Labels (board-scoped, assign/remove from cards)
- [ ] Checklists and checklist items with position
- [ ] Comments (flat, with edit/delete)
- [ ] Due dates, start dates, priority field
- [ ] Activity logging (all entity types, all actions)
- [ ] Extended schemas and endpoints
- [ ] Integration tests for card features

### Phase 3: Bulk Operations & Filtering
- [ ] Bulk move/archive/label endpoints
- [ ] Filter endpoint for board cards
- [ ] Card copy with checklists
- [ ] Bulk operation tests

### Phase 4: Search & RAG
- [ ] FTS5 virtual table with soft-delete-aware triggers
- [ ] ChromaDB embedding integration via Redis queue
- [ ] Search endpoint (FTS + vector hybrid)
- [ ] Expose kanban as RAG source
- [ ] Graceful degradation when embeddings unavailable
- [ ] Search tests

### Phase 5: Content Integration
- [ ] Card links to media items
- [ ] Card links to notes
- [ ] Bidirectional lookup endpoints
- [ ] Link validation (check target exists)
- [ ] Link tests

### Phase 6: Export/Import
- [ ] Export board to JSON (full nested structure)
- [ ] Import from tldw JSON format
- [ ] Import from Trello JSON format (basic entities)
- [ ] Import/export tests

### Phase 7: Polish & Docs
- [ ] OpenAPI documentation with examples
- [ ] Rate limiting configuration
- [ ] Performance testing (board load, search latency)
- [ ] Handoff documentation for frontend team

---

## 17. Configuration

Environment variables:
```bash
# Limits
KANBAN_MAX_BOARDS_PER_USER=50
KANBAN_MAX_LISTS_PER_BOARD=20
KANBAN_MAX_CARDS_PER_BOARD=500
KANBAN_MAX_CARDS_PER_LIST=200
KANBAN_MAX_LABELS_PER_BOARD=20
KANBAN_MAX_CHECKLISTS_PER_CARD=10
KANBAN_MAX_CHECKLIST_ITEMS_PER_CHECKLIST=50
KANBAN_MAX_COMMENTS_PER_CARD=500
KANBAN_MAX_DESCRIPTION_SIZE=65536  # 64KB
KANBAN_MAX_COMMENT_SIZE=16384      # 16KB

# Retention
KANBAN_ACTIVITY_RETENTION_DAYS=30         # Default activity log retention
KANBAN_ACTIVITY_RETENTION_MIN_DAYS=7      # Minimum user can set
KANBAN_ACTIVITY_RETENTION_MAX_DAYS=365    # Maximum user can set
KANBAN_DELETED_RETENTION_DAYS=30          # How long to keep soft-deleted items

# Embeddings
KANBAN_EMBEDDING_MODEL=default  # Uses system default
KANBAN_EMBEDDING_QUEUE=redis    # redis or sync
```

---

## 18. Deployment & Migration

- **First-run initialization**:
  - Timing: On app startup, validate `USER_DB_BASE_DIR` exists and is writable; on first user request, auto-create per-user directory and `Kanban.db`
  - Error handling: Fail fast with a clear message if `USER_DB_BASE_DIR` is missing/unwritable or per-user directory creation fails (e.g., `KANBAN_DB_INIT_FAILED: insufficient permissions`)
  - Idempotent: Subsequent accesses re-use existing DB without re-initialization
- **Legacy path migration**: if an earlier Kanban path or shared DB existed, provide a one-time migration helper to move/merge into per-user databases.
- **Schema versioning/migrations**: use `PRAGMA user_version` in each per-user `Kanban.db`; apply idempotent migrations at first access via `kanban_db.py` initialization (no external Alembic required for MVP; revisit if complexity grows).
- **Upgrade/rollback**: take a backup before migrations; on failure, restore the backup and surface a clear operator message. Provide a CLI migration helper for controlled rollouts.

---

## 19. Design Decisions (FAQ)

1. **Position strategy**: Use integer positions (0, 1, 2...) with gap rebalancing, or fractional positions (1.0, 1.5, 2.0) for fewer updates?
   - **Decision**: Integer with rebalancing on conflict; simpler to reason about

2. **Archive vs delete**: Should archive be separate from soft delete?
   - **Decision**: Yes, separate:
     - `archived=1`: Hidden from default views, fully restorable indefinitely
     - `deleted=1`: Marked for cleanup, recoverable within retention period (default 30 days)
     - Hard delete: Permanent removal after retention expires

3. **Activity retention**: How long to keep activity logs?
   - **Decision**: 30 days default, user-configurable per board (7-365 days range)
   - Background job prunes expired activities

4. **Trello import compatibility**: How thorough should Trello JSON import be?
   - **Recommendation**: Support core entities (boards, lists, cards, checklists, labels); skip Trello-specific features (power-ups, Butler rules, stickers)

5. **Card description size limit**: Should we cap description length?
   - **Decision**: 64KB limit (generous for markdown); prevents abuse while allowing detailed cards

---

## 20. Acceptance Criteria

### Core CRUD
- [ ] User can create, view, update, and archive/restore boards
- [ ] User can create, reorder, and archive/restore lists within a board
- [ ] User can create, move, reorder, copy, and archive/restore cards
- [ ] Soft delete works correctly (archived items hidden by default, restorable)

### Card Features
- [ ] User can add/edit due dates and start dates on cards
- [ ] User can set card priority (low/medium/high/urgent)
- [ ] User can create and manage labels per board
- [ ] User can add checklists with checkable items to cards
- [ ] User can add and edit comments on cards
- [ ] Activity log captures all significant changes (board, list, card level)

### Bulk & Filter
- [ ] User can bulk move/archive/label multiple cards
- [ ] User can filter cards by label, priority, due date, checklist status
- [ ] User can copy cards (including checklists)

### Search & RAG
- [ ] Cards are searchable via FTS (respects soft delete)
- [ ] Cards are indexed in ChromaDB for vector search
- [ ] Search supports hybrid mode (FTS + vector)
- [ ] Kanban exposed as RAG source via existing endpoints

### Integration
- [ ] Cards can link to media items and notes
- [ ] Bidirectional lookup works (find cards from media/notes)
- [ ] Export board to JSON works
- [ ] Import from JSON (tldw format) works

### Quality
- [ ] All endpoints follow existing tldw_server patterns
- [ ] Optimistic locking (version field) prevents conflicts
- [ ] Rate limiting configured for all mutating endpoints
- [ ] Test coverage >= 80% (line + branch coverage via pytest-cov; enforced in CI)
- [ ] Position and FTS visibility invariants verified via property-based tests (Hypothesis; see Section 15)
- [ ] API documentation complete for frontend handoff
- [ ] API spec auto-generated via OpenAPI/Swagger; human-reviewed for clarity
- [ ] Deployment & migration tested (see Section 18): first-run init works; legacy path migration (if applicable) succeeds with no data loss

---

## 20. References

- Existing PRDs: Workflows_PRD.md, Content_Collections_PRD.md
- Database patterns: ChaChaNotes_DB.py, PromptStudioDatabase.py
- API patterns: notes.py, prompt_studio_projects.py endpoints
- Trello feature reference: boards, lists, cards, checklists, labels, activity
