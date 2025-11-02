# Chatbook Features API Documentation

## Overview
This document describes the current, implemented API surface for Chatbook-adjacent features in the multi-user API: Chat Dictionaries, World Books (lorebooks), Document Generator, and Chatbooks (import/export). It reflects the code as of v0.1.0 in `tldw_Server_API` and corrects any previously published mismatches.

## Auth + Rate Limits
- Single-user: `X-API-KEY: <key>`
- Multi-user: `Authorization: Bearer <JWT>`
- Standard limits apply; background jobs (export/import, document generator) may have additional concurrency limits.

Notes on conventions used here:
- Base API prefix is `/api/v1`.
- Authentication uses either `X-API-KEY` (single-user) or `Authorization: Bearer <JWT>` (multi-user).
- Pagination uses `limit` and `offset` where applicable and responses include a `total` field in the body (no page/per_page headers).
- Rate limits are applied per-endpoint via SlowAPI decorators and may differ by route.

## Table of Contents
1. [Chat Dictionary API](#chat-dictionary-api)
2. [World Book Manager API](#world-book-manager-api)
3. [Document Generator API](#document-generator-api)
4. [Chatbooks Import/Export API](#chatbooks-importexport-api)

---

## Chat Dictionary API

Pattern-based text replacement for conversations. Supports literal and regex patterns with probability and optional grouping.

### Base URL
`/api/v1/chat/dictionaries`

### Endpoints

#### 1. Create Dictionary
POST `/api/v1/chat/dictionaries`

Creates a new chat dictionary for the authenticated user.

Request body:
```json
{
  "name": "Fantasy Terms",
  "description": "Convert modern terms to fantasy equivalents"
}
```

Response body (ChatDictionaryResponse):
```json
{
  "id": 1,
  "name": "Fantasy Terms",
  "description": "Convert modern terms to fantasy equivalents",
  "is_active": true,
  "version": 1,
  "entry_count": 0,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

#### 2. List Dictionaries
GET `/api/v1/chat/dictionaries`

Lists all dictionaries for the authenticated user.

Query parameters:
- `include_inactive` (boolean): Include inactive dictionaries (default: false)

Response body:
```json
{
  "dictionaries": [
    {
      "id": 1,
      "name": "Fantasy Terms",
      "description": "Convert modern terms to fantasy equivalents",
      "is_active": true,
      "version": 1,
      "entry_count": 25,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 1,
  "active_count": 1,
  "inactive_count": 0
}
```

#### 3. Get Dictionary (with entries)
GET `/api/v1/chat/dictionaries/{dictionary_id}`

Response body:
```json
{
  "id": 1,
  "name": "Fantasy Terms",
  "description": "Convert modern terms to fantasy equivalents",
  "is_active": true,
  "entries": [
    {
      "id": 1,
      "pattern": "car",
      "replacement": "carriage",
      "type": "literal",
      "probability": 1.0,
      "max_replacements": 0,
      "enabled": true,
      "case_sensitive": true,
      "group": null,
      "timed_effects": null
    }
  ],
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### 4. Add Entry
POST `/api/v1/chat/dictionaries/{dictionary_id}/entries`

Notes:
- `type` must be `literal` or `regex`.
- `probability` is a float in [0.0, 1.0].
- `case_sensitive` applies to literal matching.
- `max_replacements` of 0 means “unlimited”.
- `timed_effects` supports `{ sticky, cooldown, delay }` in seconds (optional).

Request body:
```json
{
  "pattern": "phone",
  "replacement": "sending stone",
  "type": "literal",
  "probability": 1.0,
  "max_replacements": 0,
  "enabled": true,
  "case_sensitive": true
}
```

Response body:
```json
{
  "id": 2,
  "dictionary_id": 1,
  "pattern": "phone",
  "replacement": "sending stone",
  "probability": 1.0,
  "group": null,
  "timed_effects": null,
  "max_replacements": 0,
  "type": "literal",
  "enabled": true,
  "case_sensitive": true,
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T00:00:00Z"
}
```

#### 5. Update Entry
PUT `/api/v1/chat/dictionaries/entries/{entry_id}`

Request body (all fields optional):
```json
{
  "pattern": "telephone",
  "replacement": "communication crystal",
  "probability": 0.9,
  "type": "literal",
  "enabled": true,
  "case_sensitive": true,
  "group": "tech",
  "max_replacements": 0
}
```

#### 6. Delete Entry
DELETE `/api/v1/chat/dictionaries/entries/{entry_id}`

#### 7. Process Text
POST `/api/v1/chat/dictionaries/process`

Request body:
```json
{
  "text": "I'll call you on my phone from the car",
  "token_budget": 1000,
  "dictionary_id": 1,
  "max_iterations": 5
}
```

Response body:
```json
{
  "original_text": "I'll call you on my phone from the car",
  "processed_text": "I'll call you on my sending stone from the carriage",
  "replacements": 2,
  "iterations": 1,
  "entries_used": [3, 5],
  "token_budget_exceeded": false,
  "processing_time_ms": 2.4
}
```

#### 8. List Entries
GET `/api/v1/chat/dictionaries/{dictionary_id}/entries`

Query parameters:
- `group` (string, optional)

Response body:
```json
{
  "entries": [
    {
      "id": 1,
      "dictionary_id": 1,
      "pattern": "car",
      "replacement": "carriage",
      "probability": 1.0,
      "group": null,
      "timed_effects": null,
      "max_replacements": 0,
      "type": "literal",
      "enabled": true,
      "case_sensitive": true,
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  ],
  "total": 1,
  "dictionary_id": 1,
  "group": null
}
```

#### 9. Import Dictionary (Markdown)
POST `/api/v1/chat/dictionaries/import`

Request body:
```json
{
  "name": "Fantasy Terms",
  "content": "# Fantasy Terms\n\n## Entry: AI\n- **Type**: literal\n- **Replacement**: Artificial Intelligence\n- **Enabled**: true\n",
  "activate": true
}
```

#### 10. Import Dictionary (JSON)
POST `/api/v1/chat/dictionaries/import/json`

Request body:
```json
{
  "data": {
    "name": "Fantasy Terms",
    "entries": [
      {"pattern": "car", "replacement": "carriage", "type": "literal"}
    ]
  },
  "activate": true
}
```

#### 11. Export Dictionary (Markdown)
GET `/api/v1/chat/dictionaries/{dictionary_id}/export`

Response body:
```json
{
  "name": "Fantasy Terms",
  "content": "# Fantasy Terms\n\ncar: carriage\nphone: sending stone\n",
  "entry_count": 25,
  "group_count": 3
}
```

#### 12. Export Dictionary (JSON)
GET `/api/v1/chat/dictionaries/{dictionary_id}/export/json`

Response body:
```json
{
  "name": "Fantasy Terms",
  "description": "Convert modern terms to fantasy equivalents",
  "entries": [
    {"pattern": "car", "replacement": "carriage", "type": "literal", "probability": 1.0}
  ]
}
```

#### 13. Update Dictionary
PUT `/api/v1/chat/dictionaries/{dictionary_id}`

Update dictionary metadata (`name`, `description`, `is_active`).

#### 14. Delete Dictionary
DELETE `/api/v1/chat/dictionaries/{dictionary_id}`

#### 15. Dictionary Statistics
GET `/api/v1/chat/dictionaries/{dictionary_id}/statistics`

Aggregate statistics for a dictionary (counts by type, groups, average probability, usage if available).

---

Planned additions (not yet implemented): Clone dictionary, toggle active status, bulk add/update entries, search entries across dictionaries.

---

## World Book Manager API

Contextual lore injection for character conversations. Supports keyword-based entry matching and character-specific attachments.

### Base URL
`/api/v1/characters/world-books`

### Endpoints

#### 1. Create World Book
POST `/api/v1/characters/world-books`

Request body:
```json
{
  "name": "Fantasy Campaign",
  "description": "D&D campaign setting",
  "scan_depth": 3,
  "token_budget": 1000,
  "recursive_scanning": true,
  "enabled": true
}
```

Response body:
```json
{
  "id": 1,
  "name": "Fantasy Campaign",
  "description": "D&D campaign setting",
  "scan_depth": 3,
  "token_budget": 1000,
  "recursive_scanning": true,
  "enabled": true,
  "version": 1,
  "entry_count": 0,
  "created_at": "2024-01-01T00:00:00Z",
  "last_modified": "2024-01-01T00:00:00Z"
}
```

#### 2. List World Books
GET `/api/v1/characters/world-books`

Query parameters:
- `include_disabled` (boolean): Include disabled world books

Response body:
```json
{
  "world_books": [
    {
      "id": 1,
      "name": "Fantasy Campaign",
      "description": "D&D campaign setting",
      "entry_count": 50,
      "enabled": true,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 1,
  "enabled_count": 1,
  "disabled_count": 0
}
```

#### 3. Get World Book
GET `/api/v1/characters/world-books/{world_book_id}`

Response body:
```json
{
  "id": 1,
  "name": "Fantasy Campaign",
  "entries": [
    {
      "id": 1,
      "keywords": ["dragon", "wyrm"],
      "content": "Dragons are ancient magical beings",
      "priority": 100,
      "enabled": true
    }
  ]
}
```

#### 4. Add Entry
POST `/api/v1/characters/world-books/{world_book_id}/entries`

Request body:
```json
{
  "keywords": ["magic", "wizard", "spell"],
  "content": "Magic in this world comes from ley lines",
  "priority": 90,
  "enabled": true
}
```

#### 5. Update Entry
PUT `/api/v1/characters/world-books/entries/{entry_id}`

#### 6. Delete Entry
DELETE `/api/v1/characters/world-books/entries/{entry_id}`

#### 7. Attach to Character
POST `/api/v1/characters/{character_id}/world-books`

Request body:
```json
{
  "world_book_id": 1,
  "enabled": true,
  "priority": 0
}
```

#### 8. Detach from Character
DELETE `/api/v1/characters/{character_id}/world-books/{world_book_id}`

#### 9. Get Character World Books
GET `/api/v1/characters/{character_id}/world-books`

#### 10. Process Context
POST `/api/v1/characters/world-books/process`

Request body:
```json
{
  "text": "Tell me about dragons and magic",
  "character_id": 1,
  "max_tokens": 1000
}
```

Response body:
```json
{
  "injected_content": "[World Info: Dragons are ancient magical beings...]\n[World Info: Magic in this world comes from ley lines...]",
  "entries_matched": 2,
  "tokens_used": 200,
  "books_used": 1,
  "entry_ids": [1, 2]
}
```

#### 2. Attach World Book to Character
POST `/api/v1/characters/{character_id}/world-books`

Body:
```json
{ "world_book_id": 10, "enabled": true, "priority": 100 }
```

#### 3. Detach World Book from Character
DELETE `/api/v1/characters/{character_id}/world-books/{world_book_id}`

#### 11. Search Entries
Not implemented. (Planned)

#### 12. Import World Book
POST `/api/v1/characters/world-books/import`

Request body:
```json
{
  "world_book": {"name": "Imported World", "description": "Imported lore"},
  "entries": [
    {"keywords": ["test"], "content": "Test content", "priority": 100}
  ],
  "merge_on_conflict": false
}
```

#### 13. Export World Book
GET `/api/v1/characters/world-books/{world_book_id}/export`

#### 14. Clone World Book
Not implemented. (Planned)

#### 15. Delete World Book
DELETE `/api/v1/characters/world-books/{world_book_id}`

#### 16. Bulk Update Entries
POST `/api/v1/characters/world-books/entries/bulk`

Request body:
```json
{
  "entry_ids": [1, 2, 3],
  "operation": "disable"
}
```

#### 17. Get Statistics
GET `/api/v1/characters/world-books/{world_book_id}/statistics`

---

## Document Generator API

Creates structured documents from conversations. Supports multiple document types and async job management.

### Base URL
`/api/v1/chat/documents`

### Document Types
- `timeline`
- `study_guide`
- `briefing`
- `summary`
- `q_and_a`
- `meeting_notes`

### Endpoints

#### 1. Generate Document
POST `/api/v1/chat/documents/generate`

Request body (GenerateDocumentRequest):
```json
{
  "conversation_id": 123,
  "document_type": "timeline",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "api_key": "...",
  "specific_message": null,
  "custom_prompt": "Focus on technical decisions",
  "stream": false,
  "async_generation": false
}
```

Response (synchronous):
```json
{
  "document_id": 42,
  "conversation_id": 123,
  "document_type": "timeline",
  "title": "Conversation Timeline",
  "content": "Timeline...",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "generation_time_ms": 2500,
  "created_at": "2024-01-01T00:00:00Z"
}
```

Response (asynchronous):
```json
{
  "job_id": "job_456",
  "status": "pending",
  "conversation_id": 123,
  "document_type": "timeline",
  "message": "Document generation job created",
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### 2. Get Document
GET `/api/v1/chat/documents/{document_id}`

#### 3. List Documents
GET `/api/v1/chat/documents`

#### 4. Delete Document
DELETE `/api/v1/chat/documents/{document_id}`

#### 5. Get Generation Job Status
GET `/api/v1/chat/documents/jobs/{job_id}`

#### 6. Cancel Generation Job
DELETE `/api/v1/chat/documents/jobs/{job_id}`

#### 7. Save Prompt Configuration
POST `/api/v1/chat/documents/prompts`

#### 8. Get Prompt Configuration
GET `/api/v1/chat/documents/prompts/{document_type}`

Query parameters:
- `conversation_id` (integer, optional)
- `document_type` (enum, optional)
- `limit` (integer, default 50)

#### 4. Delete Document
DELETE `/api/v1/chat/documents/{document_id}`

#### 5. Bulk Generate
POST `/api/v1/chat/documents/bulk`

Request body (BulkGenerateRequest):
```json
{
  "conversation_ids": [123, 456],
  "document_types": ["timeline", "summary", "q_and_a"],
  "provider": "openai",
  "model": "gpt-4o-mini",
  "api_key": "...",
  "async_generation": true
}
```

#### 6. Get Job Status
GET `/api/v1/chat/documents/jobs/{job_id}`

Response body (JobStatusResponse):
```json
{
  "job_id": "job_456",
  "status": "completed",
  "conversation_id": 123,
  "document_type": "timeline",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "result_content": "...",
  "created_at": "2024-01-01T00:00:00Z",
  "started_at": "2024-01-01T00:00:01Z",
  "completed_at": "2024-01-01T00:00:05Z",
  "progress_percentage": 100
}
```

#### 7. Cancel Job
DELETE `/api/v1/chat/documents/jobs/{job_id}`

#### 8. Save Prompt Config
POST `/api/v1/chat/documents/prompts`

Request body:
```json
{
  "document_type": "timeline",
  "system_prompt": "You are a helpful document generator...",
  "user_prompt": "Write a timeline...",
  "temperature": 0.7,
  "max_tokens": 2000
}
```

#### 9. Get Prompt Config
GET `/api/v1/chat/documents/prompts/{document_type}`

#### 10. Get Statistics
GET `/api/v1/chat/documents/statistics`

---

## Chatbooks Import/Export API

Export/import collections of chat-related content with job management and secure downloads.

### Base URL
`/api/v1/chatbooks`

### Endpoints

#### 1. Export Chatbook
POST `/api/v1/chatbooks/export`

Request body (CreateChatbookRequest):
```json
{
  "name": "My Chatbook Export",
  "description": "Backup of my conversations",
  "content_selections": {
    "conversation": ["conv123", "conv456"],
    "note": ["note789"],
    "character": ["char001"],
    "world_book": [1],
    "dictionary": [2],
    "generated_document": [42]
  },
  "author": "Jane Doe",
  "include_media": false,
  "media_quality": "compressed",
  "include_embeddings": false,
  "include_generated_content": true,
  "tags": ["backup"],
  "categories": ["personal"],
  "async_mode": true
}
```

Response body (async mode):
```json
{
  "success": true,
  "job_id": "0c9d9a3a-6d1c-4c8f-9c84-9a0c2c2d8f77",
  "status": "pending",
  "message": "Export job created successfully"
}
```

#### 2. Preview Chatbook (Upload)
POST `/api/v1/chatbooks/preview`

Preview an uploaded chatbook file (no import).

Request (multipart/form-data):
- `file`: ZIP archive

Response body (manifest summary):
```json
{
  "manifest": {
    "version": "1.0",
    "name": "My Chatbook Export",
    "total_conversations": 10,
    "total_notes": 5,
    "total_world_books": 2,
    "total_dictionaries": 1,
    "total_documents": 3,
    "include_media": false
  }
}
```

#### 3. Get Export Job Status
GET `/api/v1/chatbooks/export/jobs/{job_id}`

Response body (ExportJobResponse):
```json
{
  "job_id": "0c9d9a3a-6d1c-4c8f-9c84-9a0c2c2d8f77",
  "status": "completed",
  "chatbook_name": "My Chatbook Export",
  "download_url": "/api/v1/chatbooks/download/0c9d9a3a-6d1c-4c8f-9c84-9a0c2c2d8f77",
  "file_size_bytes": 15900000,
  "created_at": "2024-01-01T00:00:00Z",
  "completed_at": "2024-01-01T00:00:30Z"
}
```

#### 4. Download Export
GET `/api/v1/chatbooks/download/{job_id}`

Returns a ZIP file with secure headers.

#### 5. Import Chatbook
POST `/api/v1/chatbooks/import`

Request (multipart/form-data):
- `file`: The chatbook archive file (ZIP)
- Additional fields (ImportChatbookRequest via form fields):
  - `conflict_resolution`: one of `skip`, `overwrite`, `rename`, `merge`
  - `prefix_imported`: boolean
  - `import_media`: boolean
  - `import_embeddings`: boolean
  - `async_mode`: boolean

Response body (async mode):
```json
{
  "success": true,
  "job_id": "import_job_456",
  "status": "pending",
  "message": "Import job created successfully"
}
```

#### 6. Get Import Job Status
GET `/api/v1/chatbooks/import/jobs/{job_id}`

Response body (ImportJobResponse):
```json
{
  "job_id": "import_job_456",
  "status": "completed",
  "items_imported": 55,
  "conflicts_found": 5,
  "successful_items": 50,
  "failed_items": 3,
  "skipped_items": 2,
  "conflicts": [],
  "created_at": "2024-01-01T00:00:00Z",
  "completed_at": "2024-01-01T00:01:00Z"
}
```

#### 7. Validate Chatbook
No dedicated `/validate` endpoint. Use `/chatbooks/preview` (upload) to inspect a manifest without importing.

#### 8. List Export Jobs
GET `/api/v1/chatbooks/export/jobs`

Query parameters:
- `limit` (integer, default 100)
- `offset` (integer, default 0)

#### 9. List Import Jobs
GET `/api/v1/chatbooks/import/jobs`

#### 10. Cancel Export Job
DELETE `/api/v1/chatbooks/export/jobs/{job_id}`

#### 11. Cancel Import Job
DELETE `/api/v1/chatbooks/import/jobs/{job_id}`

#### 12. Clean Old Exports
POST `/api/v1/chatbooks/cleanup`

#### 13. Service Health
GET `/api/v1/chatbooks/health`

Lightweight health indicator for the Chatbooks subsystem.

---

## Error Responses

Endpoints return standard FastAPI error responses with meaningful HTTP status codes and a `detail` message. Some success responses include a `success` boolean for convenience (e.g., Chatbooks export/import). Domain-specific errors may include additional fields (see response schemas).

## Rate Limiting

Endpoint-specific limits are enforced with SlowAPI where applied:
- Chatbooks `POST /export`: 5/minute
- Chatbooks `POST /import`: 5/minute
- Chatbooks `POST /preview`: 10/minute
- Chatbooks `GET /download/{job_id}`: 20/minute

A global limiter may also be active depending on environment. When rate limits are hit, a 429 is returned.

## Pagination

List endpoints use `limit` and `offset` query parameters and include a `total` count in the response body.

## Webhooks

Webhook notifications for Chatbooks are planned but not yet implemented. See the Chatbook Developer Guide for design notes.

## SDK Examples

### Python
```python
import requests

class ChatbookAPI:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {token}"}

    def create_dictionary(self, name, description):
        response = requests.post(
            f"{self.base_url}/api/v1/chat/dictionaries",
            json={"name": name, "description": description},
            headers=self.headers
        )
        return response.json()

    def process_text(self, text, token_budget=1000, dictionary_id=None):
        response = requests.post(
            f"{self.base_url}/api/v1/chat/dictionaries/process",
            json={"text": text, "token_budget": token_budget, "dictionary_id": dictionary_id},
            headers=self.headers
        )
        return response.json()
```

### JavaScript
```javascript
class ChatbookAPI {
  constructor(baseUrl, token) {
    this.baseUrl = baseUrl;
    this.headers = {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    };
  }

  async exportChatbook(req) {
    const response = await fetch(`${this.baseUrl}/api/v1/chatbooks/export`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify(req)
    });
    return response.json();
  }

  async getExportStatus(jobId) {
    const response = await fetch(
      `${this.baseUrl}/api/v1/chatbooks/export/jobs/${jobId}`,
      { headers: this.headers }
    );
    return response.json();
  }
}
```

## Migration Guide

For users migrating from the TUI application:

1. Authentication is required for all API calls.
2. User content is isolated per-user (per-user DBs, per-user export/import paths).
3. Large operations support async jobs with status polling and secure download URLs.
4. Import conflict resolution supports `skip`, `overwrite`, `rename`, and `merge`.
5. Endpoint-level rate limiting is enforced; plan for 429 handling.
