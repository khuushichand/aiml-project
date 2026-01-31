# Deep Personalization: Per-User Profiles, Memories, and RAG Biasing

Status: Active (MVP scaffold implemented, Stage 2 enhancements in progress)

Owner: Core (RAG, LLM, AuthNZ)

Target Version: v0.2.x (Stage 1), v0.3.x (Stage 2-3), v0.4.x (Stage 4)

## Summary

Provide opt-in, explainable personalization that leverages a per-user topic profile, structured memories (with type taxonomy), conversation continuity, and proactive suggestions to improve retrieval, chat grounding, and UX. Personalization remains transparent, reversible (purge), and user-controlled.

## Current Status (v0.2.x dev)

- Feature flags: loaded from config; endpoints are gated when disabled.
  - Config: `[personalization] enabled=true` in `tldw_Server_API/Config_Files/config.txt`.
  - Exposed at runtime via `GET /api/v1/config/docs-info` under `capabilities.personalization`.
- Storage: per-user SQLite `Personalization.db` with `usage_events`, `topic_profiles`, `semantic_memories` (episodic stub present).
- Event logging: best-effort `UsageEventLogger` integrated into chat, TTS, audio transcription, media processing (videos, audios, ebooks, documents, pdfs), and web scraping endpoints.
- API endpoints (scaffolded and functional): opt-in, purge, profile, preferences, memories list/add/delete; explanations placeholder.
- Consolidation service: background loop + admin trigger; current implementation upserts topic scores from recent event tags. In-memory last-tick status is available.
- RAG integration: scorer/context builder stubs exist; current weights map to vector/personal/recency with BM25 as a base term.
- WebUI: Personalization tab (preview) for viewing profile/weights and adding/listing memories; tab visibility follows server capabilities.
- Tests: basic endpoint CRUD, feature flag presence, and usage-event logging across relevant media/audio/web endpoints.

## Changelog

- v0.2.x dev
  - Implemented feature flags and capability exposure via `/api/v1/config/docs-info`.
  - Added per-user SQLite Personalization DB; event logger integrated across chat/audio/media/web scraping.
  - Scaffolded personalization API (opt-in, purge, profile, preferences, memories CRUD; explanations placeholder).
  - Added consolidation service (tag-frequency topic upserts), admin trigger, and in-memory last-tick status with admin GET status endpoint.
  - WebUI tab wired behind capabilities; added unit tests for usage-event logging on ebooks/documents/pdfs.
- v0.1.0
  - Initial draft design with goals, architecture, data model, and milestones.

## Goals

- Capture user activity (ingestion, views, searches, chats, notes) as structured events.
- Consolidate events into: (1) topic affinities and (2) distilled semantic memories with type taxonomy.
- Bias RAG re-ranking and chat preambles with user-relevant context, with explanations.
- Track conversation sessions and enable continuity ("pick up where you left off").
- Provide proactive suggestions based on patterns, reminders, and content updates.
- Offer a Personalization Dashboard to inspect/edit memories, topics, sessions, and weights.
- Keep everything opt-in per user, with purge and export controls.

## Non-Goals (Initial)

- Cross-user modeling or global recommendations (future, opt-in only).
- On-device encryption/federated learning (future consideration).
- Intrusive UI nudges; personalization is subtle and explainable.
- Push notifications (proactive features are pull-based via API).

## User Stories

- As a user, I opt in and see my evolving topic interests and key preferences.
- As a user, I can pin, edit, or delete a memory and see where it applies.
- As a user, my searches and chat answers feel more relevant to my past work.
- As a user, I can correct the system's assumptions about me and see those corrections prioritized.
- As a user, I can continue conversations where I left off, with context preserved.
- As a user, I receive suggestions about content I saved but haven't revisited.
- As a user, I can purge all personalization data and return to the default behavior.

---

## Architecture Overview

### Core Components

- Event ingestion via API dependencies logs `UsageEvent`s for opted-in users.
- A background Consolidation Service periodically embeds events, clusters topics, and distills memories.
- The Personalization Scorer reranks RAG results using topic and memory overlap with the current query.
- Chat context builder injects a brief profile summary, top-k relevant memories, and session continuity context.
- Session Manager tracks conversation sessions and provides continuity prompts.
- Suggestion Detectors analyze patterns and generate proactive suggestions.

### System Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           USER INTERACTION LAYER                           │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │   Search    │  │    Chat     │  │   Ingest    │  │  Dashboard  │       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
│         │                │                │                │               │
└─────────┼────────────────┼────────────────┼────────────────┼───────────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         PERSONALIZATION LAYER                              │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐   │
│  │   Event Collector  │  │  Session Manager   │  │ Context Builder    │   │
│  │                    │  │                    │  │                    │   │
│  │  - Log activities  │  │  - Track sessions  │  │  - Memory retrieval│   │
│  │  - Tag extraction  │  │  - Continuity      │  │  - Profile inject  │   │
│  │  - Metadata        │  │  - Summarization   │  │  - Why signals     │   │
│  └─────────┬──────────┘  └─────────┬──────────┘  └─────────┬──────────┘   │
│            │                       │                       │               │
│            ▼                       ▼                       ▼               │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │                    PERSONALIZATION SCORER                          │   │
│  │                                                                    │   │
│  │  score = bm25 + α×vector + β×personal_similarity + γ×recency      │   │
│  │                                                                    │   │
│  │  Memory Priority: correction > constraint > preference > others   │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         BACKGROUND SERVICES                                │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐   │
│  │   Consolidation    │  │ Suggestion Detectors│  │  Session Cleanup   │   │
│  │                    │  │                    │  │                    │   │
│  │  - Topic clusters  │  │  - Pattern detect  │  │  - Summarize old   │   │
│  │  - Memory distill  │  │  - Reminder gen    │  │  - Expire working  │   │
│  │  - Decay scores    │  │  - Content updates │  │  - Archive history │   │
│  └────────────────────┘  └────────────────────┘  └────────────────────┘   │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                           STORAGE LAYER                                    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐ │
│  │         SQLite (per-user)       │  │      ChromaDB (per-user)        │ │
│  │                                 │  │                                 │ │
│  │  - profiles                     │  │  - personal_topics_<user_id>    │ │
│  │  - usage_events                 │  │  - personal_memories_<user_id>  │ │
│  │  - memories (6 types)           │  │  - session_embeddings_<user_id> │ │
│  │  - conversation_sessions        │  │                                 │ │
│  │  - conversation_messages        │  │                                 │ │
│  │  - suggestions                  │  │                                 │ │
│  │  - topic_profiles               │  │                                 │ │
│  └─────────────────────────────────┘  └─────────────────────────────────┘ │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Model (SQLite + Chroma)

SQLite (per-user DB): `<USER_DB_BASE_DIR>/<user_id>/Personalization.db`
`USER_DB_BASE_DIR` is defined in `tldw_Server_API.app.core.config` (defaults to `Databases/user_databases/` under the project root). Override via environment variable or `Config_Files/config.txt` as needed.

### Core Tables

#### profiles

```sql
CREATE TABLE IF NOT EXISTS profiles (
  user_id TEXT PRIMARY KEY,
  enabled INTEGER NOT NULL DEFAULT 0,
  alpha REAL NOT NULL DEFAULT 0.2,
  beta REAL NOT NULL DEFAULT 0.6,
  gamma REAL NOT NULL DEFAULT 0.2,
  recency_half_life_days INTEGER NOT NULL DEFAULT 14,

  -- Proactive features preferences
  proactive_enabled INTEGER NOT NULL DEFAULT 1,
  proactive_frequency TEXT DEFAULT 'normal',  -- off, low, normal, high
  proactive_types TEXT,  -- JSON array of enabled types
  quiet_hours_start TEXT,  -- HH:MM format
  quiet_hours_end TEXT,

  -- Style preferences
  response_style TEXT DEFAULT 'balanced',  -- concise, balanced, detailed
  preferred_format TEXT DEFAULT 'auto',  -- prose, bullets, code, auto

  purged_at TEXT,  -- ISO timestamp; prevents re-creation after purge
  updated_at TEXT NOT NULL
);
```

#### usage_events

```sql
CREATE TABLE IF NOT EXISTS usage_events (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  type TEXT NOT NULL,  -- ingest|view|search|chat|note|tts|transcribe|web_scrape|media_process|feedback
  resource_id TEXT,
  tags TEXT,  -- JSON array
  metadata TEXT,  -- JSON object (redacted; no secrets)

  FOREIGN KEY (user_id) REFERENCES profiles(user_id)
);
CREATE INDEX IF NOT EXISTS idx_usage_user_ts ON usage_events(user_id, timestamp DESC);
```

### Memory Type Taxonomy

The enhanced memory model distinguishes six types of memories, each with different confidence levels, decay rates, and injection priorities:

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY TYPES                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  IDENTITY MEMORIES (rarely change, high confidence)          │
│  ├── Facts: "Works at Acme Corp as ML Engineer"             │
│  ├── Background: "PhD in Computer Science from MIT"          │
│  └── Demographics: "Based in San Francisco, PST timezone"    │
│                                                              │
│  PREFERENCE MEMORIES (change over time, medium confidence)   │
│  ├── Style: "Prefers concise bullet points over prose"       │
│  ├── Technical: "Favors Python, dislikes verbose Java"       │
│  └── Domain: "Focus on ML/NLP, less interest in frontend"    │
│                                                              │
│  RELATIONAL MEMORIES (context-dependent)                     │
│  ├── People: "Collaborates with Alice on Project X"          │
│  ├── Projects: "Currently researching RAG optimization"      │
│  └── Organizations: "Company uses GCP, not AWS"              │
│                                                              │
│  CORRECTION MEMORIES (highest priority, prevents mistakes)   │
│  ├── Explicit: "Told me ChromaDB is preferred over Pinecone" │
│  ├── Implicit: "Dismissed result about React, likely irrelevant"│
│  └── Feedback: "Marked response about X as unhelpful"        │
│                                                              │
│  CONSTRAINT MEMORIES (scheduling/availability)               │
│  ├── Time: "Usually works 9-5 PST, slow responses weekends" │
│  ├── Resources: "Limited GPU access, prefer CPU solutions"   │
│  └── Preferences: "Don't surface work content after 6pm"     │
│                                                              │
│  WORKING MEMORIES (session-scoped, high recency)            │
│  ├── Current context: "Currently debugging auth issue"       │
│  ├── Recent queries: "Last 5 searches were about OAuth"      │
│  └── Conversation state: "Discussing implementation details" │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### memories (unified table with type taxonomy)

```sql
CREATE TABLE IF NOT EXISTS memories (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,

  -- Type classification
  memory_type TEXT NOT NULL,  -- identity, preference, relational, correction, constraint, working
  subtype TEXT,               -- e.g., 'style', 'technical', 'people', 'explicit'

  -- Content
  content TEXT NOT NULL,      -- Human-readable statement
  structured_data TEXT,       -- JSON: Optional structured representation

  -- Confidence and sourcing
  confidence REAL DEFAULT 0.5,  -- 0.0-1.0, affects injection priority
  source TEXT,                  -- 'explicit' (user said), 'inferred', 'corrected'
  source_event_ids TEXT,        -- JSON: Links to usage_events

  -- Lifecycle
  created_at TEXT NOT NULL,
  last_accessed TEXT,           -- For recency decay
  last_validated TEXT,          -- When user confirmed still accurate
  expires_at TEXT,              -- For working memories (nullable for permanent)

  -- User control
  pinned INTEGER DEFAULT 0,
  hidden INTEGER DEFAULT 0,     -- User can hide without deleting

  -- Embeddings (optional cache; Chroma is canonical)
  embedding BLOB,

  FOREIGN KEY (user_id) REFERENCES profiles(user_id)
);

CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(user_id, memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_confidence ON memories(user_id, confidence DESC);
CREATE INDEX IF NOT EXISTS idx_memories_recency ON memories(user_id, last_accessed DESC);
CREATE INDEX IF NOT EXISTS idx_memories_expires ON memories(expires_at) WHERE expires_at IS NOT NULL;
```

#### Legacy Tables (backwards compatibility)

The following tables are retained for backwards compatibility during migration:

```sql
-- Legacy: semantic_memories (migrate to memories with type='preference' or 'identity')
CREATE TABLE IF NOT EXISTS semantic_memories (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  content TEXT NOT NULL,
  tags TEXT,
  pinned INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

-- Legacy: episodic_memories (migrate to memories with type='working')
CREATE TABLE IF NOT EXISTS episodic_memories (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  summary TEXT NOT NULL,
  event_id TEXT,
  timestamp TEXT NOT NULL
);
```

#### topic_profiles

```sql
CREATE TABLE IF NOT EXISTS topic_profiles (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  label TEXT NOT NULL,
  centroid_embedding BLOB,  -- Optional cache; Chroma is canonical
  score REAL NOT NULL DEFAULT 0,  -- Decayed affinity 0.0-1.0
  last_seen TEXT NOT NULL,

  FOREIGN KEY (user_id) REFERENCES profiles(user_id)
);
CREATE INDEX IF NOT EXISTS idx_topics_user ON topic_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_topics_score ON topic_profiles(user_id, score DESC);
```

### Conversation Continuity Tables

#### conversation_sessions

```sql
CREATE TABLE IF NOT EXISTS conversation_sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,

  -- Session metadata
  title TEXT,                     -- Auto-generated or user-provided
  started_at TEXT NOT NULL,
  ended_at TEXT,                  -- NULL if ongoing
  last_activity_at TEXT,

  -- Content summary (LLM-generated after session ends or pauses)
  summary TEXT,
  key_topics TEXT,                -- JSON: ["oauth", "python", "authentication"]
  key_decisions TEXT,             -- JSON: ["use JWT over sessions", "implement refresh tokens"]
  action_items TEXT,              -- JSON: ["implement token endpoint", "add tests"]

  -- Status
  status TEXT DEFAULT 'active',   -- active, paused, completed, abandoned
  completion_reason TEXT,         -- 'resolved', 'user_ended', 'timeout', etc.

  -- Embeddings for retrieval (optional cache)
  summary_embedding BLOB,

  -- Linking
  parent_session_id TEXT,         -- If this continues another session
  related_session_ids TEXT,       -- JSON: Similar/related conversations

  FOREIGN KEY (user_id) REFERENCES profiles(user_id),
  FOREIGN KEY (parent_session_id) REFERENCES conversation_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_sessions_recent ON conversation_sessions(user_id, last_activity_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON conversation_sessions(user_id, status);
```

#### conversation_messages

```sql
CREATE TABLE IF NOT EXISTS conversation_messages (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,

  role TEXT NOT NULL,             -- user, assistant, system
  content TEXT NOT NULL,
  timestamp TEXT NOT NULL,

  -- Metadata
  tokens_used INTEGER,
  model_used TEXT,

  -- Important markers
  is_key_moment INTEGER DEFAULT 0,  -- User marked as important
  extracted_facts TEXT,             -- JSON: Facts extracted for memory

  FOREIGN KEY (session_id) REFERENCES conversation_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON conversation_messages(session_id, timestamp);
```

### Proactive Suggestions Tables

#### suggestions

```sql
CREATE TABLE IF NOT EXISTS suggestions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,

  -- Classification
  suggestion_type TEXT NOT NULL,  -- pattern, reminder, update, goal, continuation, serendipity
  trigger_reason TEXT,            -- Why this was generated

  -- Content
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  action_url TEXT,                -- Deep link to relevant content
  related_resource_ids TEXT,      -- JSON: Links to media/chats/etc

  -- Lifecycle
  created_at TEXT NOT NULL,
  expires_at TEXT,                -- When suggestion becomes stale

  -- Delivery status
  status TEXT DEFAULT 'pending',  -- pending, delivered, dismissed, acted_on
  delivered_at TEXT,
  user_response TEXT,             -- 'clicked', 'dismissed', 'snoozed'
  user_response_at TEXT,

  -- Scoring
  relevance_score REAL,           -- Computed relevance
  priority INTEGER DEFAULT 0,     -- Higher = more urgent

  FOREIGN KEY (user_id) REFERENCES profiles(user_id)
);

CREATE INDEX IF NOT EXISTS idx_suggestions_pending ON suggestions(user_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_suggestions_expires ON suggestions(expires_at) WHERE expires_at IS NOT NULL;
```

### Chroma Collections (per-user)

- `personal_topics_<user_id>` (TopicProfile embeddings)
- `personal_memories_<user_id>` (Memory embeddings across all types)
- `session_embeddings_<user_id>` (Session summary embeddings for continuity retrieval)

Embedding storage note:
- Chroma collections are the canonical source for embeddings; SQLite stores optional cached vectors only for export/inspection and may be empty.

---

## Memory Priority Algorithm

When selecting memories to inject into context:

```python
def score_memory(memory: Memory, query_embedding: list[float]) -> float:
    """
    Score a memory for relevance to current query.
    Higher score = more likely to inject.
    """
    # Base: semantic similarity to query
    similarity = cosine_similarity(memory.embedding, query_embedding)

    # Type multipliers (corrections are critical)
    type_weights = {
        'correction': 2.0,   # Always surface corrections
        'constraint': 1.5,   # Important for appropriate responses
        'preference': 1.2,   # Moderately important
        'relational': 1.1,   # Context-dependent
        'identity': 1.0,     # Stable background
        'working': 0.8,      # Only if very recent
    }
    type_mult = type_weights.get(memory.memory_type, 1.0)

    # Confidence factor
    conf_mult = 0.5 + (memory.confidence * 0.5)  # Range: 0.5-1.0

    # Recency decay (exponential, half-life varies by type)
    half_lives = {
        'working': 1,        # 1 day
        'correction': 30,    # 1 month
        'preference': 14,    # 2 weeks
        'relational': 7,     # 1 week
        'identity': 90,      # 3 months
        'constraint': 7,     # 1 week
    }
    days_old = (now() - memory.last_accessed).days
    half_life = half_lives.get(memory.memory_type, 14)
    recency_mult = 0.5 ** (days_old / half_life)

    # Pinned memories get boost
    pin_mult = 1.5 if memory.pinned else 1.0

    return similarity * type_mult * conf_mult * recency_mult * pin_mult
```

---

## Services & Integration

### Event Collector (API deps)
- Location: `tldw_Server_API/app/api/v1/API_Deps/`
- Behavior: For authenticated requests, if user has `enabled=True`, log `UsageEvent`.
- Privacy: Never store raw secrets; hash/strip sensitive fields.

### Consolidation Service
- Location: `tldw_Server_API/app/services/personalization_consolidation.py`
- Schedule: Periodic (e.g., every 30-60 min) and on-demand API trigger.
- Steps:
  - Embed recent events (title, tags, brief content fingerprint).
  - Incremental clustering → update `TopicProfile` + Chroma centroid.
  - Summarize frequent patterns into typed memories (LLM-assisted, rate limited).
  - If LLM summarization is disabled or no provider is configured, skip memory synthesis.
  - Clean up expired working memories.
  - Enforce retention windows; ignore events older than configured limits and any events before `purged_at`.
- MVP behavior (implemented): compute tag-frequency topic scores from recent events; upsert into `topic_profiles`.
- Ops: maintains in-memory `last_ticks` per user for status; graceful start/stop with app lifecycle.

### Session Manager
- Location: `tldw_Server_API/app/core/Personalization/session_manager.py`
- Responsibilities:
  - Create/retrieve sessions for chat interactions
  - Detect session boundaries (new topic vs continuation)
  - Summarize completed sessions (LLM-assisted)
  - Provide continuity context for resumed sessions

### Suggestion Detectors
- Location: `tldw_Server_API/app/services/suggestion_detectors/`
- Types:
  - `PatternDetector`: Detect concentrated activity on a topic
  - `ReminderDetector`: Surface saved but unvisited content
  - `ContinuationDetector`: Offer to resume unfinished conversations
  - `SerendipityDetector`: Surface interesting content outside usual topics

### Personalization Scorer (RAG)
- Location: `tldw_Server_API/app/core/RAG/personalization_scorer.py`
- Score: `score = bm25 + alpha*vector + beta*personal_similarity + gamma*recency`
- Inputs are normalized to `[0,1]` before blending (per-query min/max or z-score → sigmoid).
- Weights are clamped to `>= 0`; if `alpha+beta+gamma > 1`, normalize to sum to 1.
- Recency is computed as `0.5^(age_days / recency_half_life_days)` with a floor at 0.
- Memory type weights are applied per the priority algorithm above.
- Explanations: Attach `why` signals (topic overlap, memory match, recency boost, memory type).

### Chat Context Builder (LLM)
- Location: `tldw_Server_API/app/core/LLM_Calls/context_builders/personal_context.py`
- Behavior: Given a chat input, embed intent; fetch top-k memories (prioritized by type and relevance); add concise profile summary (<300 chars), selected memories (<3-5), and session continuity context to the system preamble.
- Safety: Inject as a non-instructional "User Context" block; strip imperative phrasing; do not allow memories to override system instructions.

---

## API Design

Base path: `/api/v1/personalization`

### Profile & Preferences

```yaml
POST /opt-in:
  description: Enable/disable personalization for the user (idempotent)
  request:
    enabled: bool
  response:
    enabled: bool
    user_id: string
    updated_at: datetime

POST /purge:
  description: Delete all personalization data for user
  response:
    status: "ok"
    deleted_counts: { memories: int, events: int, sessions: int, suggestions: int }
    enabled: false
    purged_at: datetime

GET /profile:
  description: Get current personalization profile
  response:
    enabled: bool
    alpha: float
    beta: float
    gamma: float
    recency_half_life_days: int
    topic_count: int
    memory_count: int
    session_count: int
    proactive_enabled: bool
    proactive_frequency: string
    response_style: string
    updated_at: datetime

POST /preferences:
  description: Update weights and preferences
  request:
    alpha?: float
    beta?: float
    gamma?: float
    recency_half_life_days?: int
    proactive_enabled?: bool
    proactive_frequency?: string  # off, low, normal, high
    proactive_types?: string[]    # pattern, reminder, update, goal, continuation, serendipity
    quiet_hours?: { start: string, end: string }
    response_style?: string       # concise, balanced, detailed
    preferred_format?: string     # prose, bullets, code, auto
  response: PersonalizationProfile
```

### Memories API

```yaml
GET /memories:
  description: List memories (with type taxonomy filtering)
  query_params:
    type?: string[]      # Filter by memory_type(s)
    subtype?: string     # Filter by subtype
    source?: string      # 'explicit', 'inferred', 'corrected'
    include_expired?: bool
    include_hidden?: bool
    format?: 'json' | 'markdown'
    q?: string           # Search content
    page?: int
    size?: int
  response:
    items: Memory[]
    total: int
    page: int
    size: int

POST /memories:
  description: Add a new memory
  request:
    content: string
    memory_type: string  # identity, preference, relational, correction, constraint, working
    subtype?: string
    confidence?: float
    tags?: string[]
    pinned?: bool
    expires_in_days?: int  # For working memories
  response: Memory

GET /memories/{id}:
  description: Get a specific memory
  response: Memory

PATCH /memories/{id}:
  description: Update a memory
  request:
    content?: string
    confidence?: float
    pinned?: bool
    hidden?: bool
    tags?: string[]
  response: Memory

DELETE /memories/{id}:
  description: Delete a memory
  response:
    detail: string

POST /memories/validate:
  description: Batch confirm memories are still accurate (updates last_validated)
  request:
    memory_ids: string[]
  response:
    validated_count: int
    updated_at: datetime

POST /memories/import:
  description: Import memories from JSON or Markdown
  request:
    format: 'json' | 'markdown'
    content: string
  response:
    imported_count: int
    errors: string[]

GET /memories/export:
  description: Export all memories
  query_params:
    format: 'json' | 'markdown'
  response:
    content: string  # Formatted export
```

### Conversation Sessions API

```yaml
GET /sessions:
  description: List conversation sessions
  query_params:
    status?: string[]   # active, paused, completed, abandoned
    days?: int          # Limit to last N days
    limit?: int
  response:
    sessions: Session[]

GET /sessions/{id}:
  description: Get session details with messages
  query_params:
    include_messages?: bool
  response:
    session: Session
    messages?: Message[]
    related_sessions?: Session[]

POST /sessions/{id}/continue:
  description: Mark intent to continue a session
  response:
    session: Session
    context_summary: string  # Brief recap to inject

POST /sessions/{id}/end:
  description: Explicitly end a session
  request:
    completion_reason?: string
  response:
    session: Session

PATCH /sessions/{id}:
  description: Update session metadata
  request:
    title?: string
    status?: string
  response: Session
```

### Suggestions API

```yaml
GET /suggestions:
  description: Get pending suggestions for user
  query_params:
    status?: string     # pending, all
    type?: string[]     # Filter by suggestion_type
    limit?: int
  response:
    suggestions: Suggestion[]

POST /suggestions/{id}/respond:
  description: Record user response to suggestion
  request:
    response: 'clicked' | 'dismissed' | 'snoozed'
    snooze_until?: datetime
  response:
    suggestion: Suggestion
```

### Explanations API

```yaml
GET /explanations:
  description: Get recent personalization signals used in RAG/chat
  query_params:
    limit?: int
    context?: 'rag' | 'chat'
  response:
    items: ExplanationEntry[]
    total: int
```

### Admin Endpoints

```yaml
POST /admin/personalization/consolidate:
  description: Trigger one-off consolidation (admin only)
  request:
    user_id?: string
  response:
    status: string
    user_id: string

GET /admin/personalization/status:
  description: Get background service state (admin only)
  response:
    running: bool
    last_ticks: { user_id: datetime }
```

Schemas live under: `tldw_Server_API/app/api/v1/schemas/personalization.py`

Implementation notes:
- All endpoints are feature-gated; return 404 when personalization is disabled.
- Explanations endpoint returns from a per-user ring buffer (default N=100, TTL 7 days) and are not persisted in MVP.
- Purge sets `enabled=false` and `purged_at=now`; opt-in clears `purged_at`.
- Preferences updates validate/clamp weights to `[0,1]` and ensure non-negative values.

---

## Proactive Features Architecture

### Feature Categories

```
┌─────────────────────────────────────────────────────────────┐
│                 PROACTIVE FEATURE TYPES                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. PATTERN-BASED SUGGESTIONS                                │
│     Detect: User ingests 5 papers on "transformer attention" │
│     Action: "I notice you're researching attention mechanisms.│
│              Here are 3 highly-cited papers you haven't seen."│
│                                                              │
│  2. TIME-BASED REMINDERS                                     │
│     Detect: User saved content 7 days ago, hasn't revisited  │
│     Action: "You saved 'RAG Best Practices' last week.        │
│              Would you like to continue reading?"             │
│                                                              │
│  3. CONTENT UPDATES                                          │
│     Detect: New content matches user's topic profile          │
│     Action: "New paper on your topic 'vector databases'       │
│              was published yesterday."                        │
│                                                              │
│  4. GOAL PROGRESS                                            │
│     Detect: User has active research goal                     │
│     Action: "Your 'ML Security' research is 60% complete.     │
│              3 subtopics remain unexplored."                  │
│                                                              │
│  5. CONVERSATION CONTINUATION                                │
│     Detect: Unfinished conversation thread                    │
│     Action: "We were discussing OAuth implementation.         │
│              Would you like to continue?"                     │
│                                                              │
│  6. SERENDIPITY                                              │
│     Detect: Interesting content outside usual topics          │
│     Action: "This might interest you: related to your work    │
│              but from a different angle."                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Detection Pipeline

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Events     │────▶│  Detectors   │────▶│ Suggestions  │
│   Stream     │     │  (Rules +    │     │    Queue     │
│              │     │   ML-based)  │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
                                                 │
                                                 ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Delivery   │◀────│  Filtering   │◀────│   Ranking    │
│  (API/Pull)  │     │  (Rate limit │     │  (Relevance  │
│              │     │   + prefs)   │     │   + timing)  │
└──────────────┘     └──────────────┘     └──────────────┘
```

### User Preferences for Proactive Features

Users control proactive features via the profile:
- `proactive_enabled`: Master toggle
- `proactive_frequency`: off, low (max 1/day), normal (max 3/day), high (unlimited)
- `proactive_types`: Array of enabled suggestion types
- `quiet_hours_start/end`: Time range when suggestions should not be surfaced

---

## Conversation Continuity Design

### Conversation Layers

```
┌─────────────────────────────────────────────────────────────┐
│                 CONVERSATION LAYERS                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Layer 1: CURRENT SESSION                                    │
│  - Full conversation history in context window               │
│  - Real-time working memory updates                          │
│  - Immediate context (no summarization needed)               │
│                                                              │
│  Layer 2: RECENT SESSIONS (last 7 days)                      │
│  - Compressed summaries of each session                      │
│  - Key topics, decisions, and action items                   │
│  - Available for "continue from..." prompts                  │
│                                                              │
│  Layer 3: HISTORICAL SESSIONS (older)                        │
│  - Highly compressed (topic + 1-2 sentence summary)          │
│  - Used for long-term pattern detection                      │
│  - Retrieved only when semantically relevant                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Session Lifecycle

1. **Session Creation**: New session created when:
   - User starts a conversation after >30 min inactivity
   - Query is semantically dissimilar to recent session (similarity < 0.8)
   - User explicitly starts a new session

2. **Session Continuation**: Same session continues when:
   - Activity within 30 min window
   - Query is semantically similar to current session
   - User explicitly continues a session

3. **Session End Detection**: Session marked as complete when:
   - User sends closing signals ("thanks", "that's all", "got it")
   - No activity for 2+ hours
   - User explicitly ends session

4. **Session Summarization**: When session ends:
   - LLM generates summary, key topics, decisions, action items
   - Summary is embedded for future retrieval
   - Working memories from session are migrated or expired

### Context Injection for Continuity

When building chat context:
1. Current session messages (full context)
2. Recent session summaries (last 7 days, top 5)
3. Semantically relevant historical sessions (top 3)
4. Unfinished sessions with action items

---

## Human-Readable Memory Format

Users can view and edit memories as Markdown:

```markdown
# My Memories

## Identity
- I work at Acme Corp as a Machine Learning Engineer (high confidence)
- I have a PhD in Computer Science from MIT (medium confidence)

## Preferences
- I prefer concise, bullet-point responses (high confidence)
- I favor Python over other languages (medium confidence)
- I dislike verbose explanations (inferred from feedback)

## Corrections ⚠️
- ChromaDB is my preferred vector store, not Pinecone [corrected 2024-01-15]
- My project deadline is March, not April [corrected 2024-01-20]

## Relational
- Collaborating with Alice on Project X
- Company uses GCP, not AWS

## Constraints
- Usually available 9-5 PST
- Limited GPU access, prefer CPU solutions

## Current Context (Working)
- Currently debugging OAuth2 implementation (expires: end of session)
- Researching RAG optimization techniques (expires: 7 days)
```

---

## WebUI Additions

### Personalization Dashboard (Next.js WebUI)

- **Profile Tab**
  - Opt-in toggle, sliders for `alpha/beta/gamma`, half-life selector
  - Response style and format preferences
  - Proactive feature toggles and quiet hours

- **Topics Tab**
  - Topic list with affinity bars
  - Ability to dismiss/boost topics

- **Memories Tab**
  - Memory list grouped by type with search
  - Edit, pin, hide, delete actions
  - Import/export buttons
  - Validation button for stale memories

- **Sessions Tab**
  - Recent session list with status indicators
  - Session detail view with messages
  - Continue/end session actions

- **Suggestions Tab**
  - Pending suggestions list
  - Dismiss/snooze/act actions
  - Suggestion type filters

- **Explanations Tab**
  - "Why" popovers on search/chat results
  - Recent explanation log

Visibility controlled by capability map from `GET /api/v1/config/docs-info` (`capabilities.personalization`).

---

## Configuration

`tldw_Server_API/Config_Files/config.txt`

Weights: `alpha=vector`, `beta=personal_similarity`, `gamma=recency` (BM25 is a base term with weight 1.0 in MVP).

```ini
[personalization]
enabled = true
alpha = 0.2
beta = 0.6
gamma = 0.2
recency_half_life_days = 14

# Retention
usage_event_retention_days = 90
episodic_memory_retention_days = 30
semantic_memory_retention_days = 180
working_memory_default_ttl_days = 7

# LLM for summarization
personalization_llm_provider = "local_only"  # or provider name

# Proactive features
proactive_enabled = true
proactive_check_interval_minutes = 60
suggestion_max_per_day = 5

# Session continuity
session_inactivity_timeout_minutes = 30
session_auto_summarize = true
max_recent_sessions_in_context = 5
```

Environment overrides supported via existing config loader.

Runtime capability surface:
- `GET /api/v1/config/docs-info` → includes `capabilities` and `supported_features` maps (for backward compatibility).

---

## Privacy & Security

- Default off per user; explicit opt-in.
- Purge endpoint removes SQLite rows and Chroma collections.
- If LLM summarization is enabled, it must use the configured provider; users can opt out of LLM summarization while keeping personalization on.
- Rate limits on consolidation; never log secret values.
- Access control via existing AuthNZ user scopes.
- Working memories auto-expire; no permanent storage of session-scoped data without explicit promotion.
- Hidden memories are excluded from context injection but retained for user access.

---

## Testing Strategy

### Unit Tests
- Topic clustering stability and centroid updates.
- Personalization scoring blends and `why` signal emission.
- Consolidation idempotence over overlapping event windows.
- Memory injection safety: non-instructional block and stripped imperatives.
- Memory type priority scoring accuracy.
- Session boundary detection logic.
- Suggestion detector rules.

### Integration Tests
- RAG search with/without personalization; uplift in MRR@k.
- Chat injection remains within token budget and improves judged relevance.
- Opt-in/out and purge flows, including Chroma cleanup.
- Usage-event logging smoke tests for TTS, web scraping, ebooks/documents/pdfs process endpoints.
- Session creation/continuation/summarization flow.
- Memory import/export round-trip.
- Suggestion lifecycle (create → deliver → respond).

### Fixtures/Mocks
- Mock embeddings and LLM summarization for deterministic tests.
- Use temporary per-test user DBs under `<USER_DB_BASE_DIR>/<test_user>`.

---

## Metrics & Evaluation

- **Retrieval**: MRR@k, NDCG@k with and without personalization.
- **Engagement**: Click-through/top-3, dwell time, "usefulness" thumbs-up rate.
- **Safety**: Purge correctness and latency, token overhead in chat.
- **Continuity**: Session continuation rate, time-to-resume.
- **Proactive**: Suggestion acceptance rate, dismissal rate by type.

---

## Milestones

### Stage 1 (MVP) - Foundation ✓
- Event logging ✓
- Basic profile with opt-in/purge ✓
- Simple topic affinity from tags ✓
- Basic memory CRUD (single type) ✓
- Dashboard read-only view ✓

### Stage 2 - Core Personalization (Current)
- RAG re-ranking integration
- Chat context injection
- Consolidation with embeddings
- **Memory type taxonomy** (6 types)
- **Feedback mechanism** (corrections)
- Style preferences (tone, verbosity)
- Memory import/export

### Stage 3 - Intelligence
- **Conversation sessions and summaries**
- **Session continuity** ("continue where you left off")
- **Pattern detection** for suggestions
- Goal/project inference
- Auto-tuning of weights

### Stage 4 - Proactive & Delight
- **Proactive suggestions endpoint**
- **Reminder system**
- **Content update notifications**
- Serendipity mode
- Cross-session insights
- Full export (including sessions)

---

## Implementation Priorities

| Priority | Feature | Impact | Effort | Stage |
|----------|---------|--------|--------|-------|
| 1 | Memory type taxonomy | High | Medium | 2 |
| 2 | Correction memories | High | Low | 2 |
| 3 | Session tracking | High | Medium | 3 |
| 4 | Continuation prompts | High | Low | 3 |
| 5 | Pattern-based suggestions | Medium | Medium | 4 |
| 6 | Reminder system | Medium | Low | 4 |

---

## Open Questions

- Default top-k memories to inject for chat without bloat? (Proposed: 5 max, prioritized by type)
- Per-project overrides in addition to global user profile?
- How to surface "why" without cluttering the UI? (Proposed: expandable popovers)
- Should we add a "Persona Action Log" that records actions taken and rationale?
- How to handle conflicting memories (e.g., correction contradicts preference)?
- Should session summaries be editable by the user?

---

## Risks & Mitigations

- **Token bloat in chat** → enforce strict memory caps and concise summaries; prioritize by type.
- **Privacy concerns** → opt-in, purge, and clear data visibility/editing; working memories auto-expire.
- **Overfitting to recent interests** → recency half-life configurable and visible; type-specific decay rates.
- **Dual personalization paths** → ensure only one boost path is active per request.
- **Stale memories** → validation endpoint; confidence decay over time; "last validated" tracking.
- **Suggestion fatigue** → frequency caps; dismissal learning; quiet hours.

---

## References

- [OpenClaw Official Site](https://openclaw.ai/)
- [What is OpenClaw - DigitalOcean](https://www.digitalocean.com/resources/articles/what-is-openclaw)
- [OpenClaw GitHub](https://github.com/clawdbot/clawdbot)
- [OpenClaw: The AI Assistant That Actually Does Things - Turing College](https://www.turingcollege.com/blog/openclaw)
