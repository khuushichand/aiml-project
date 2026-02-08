# Persona Role-Play Stack (MVP) - PRD (Character/Chat Integrated)

## 1) Summary
Enable persona-consistent chat responses by curating character-scoped exemplars, labeling them (emotion, scenario, rhetorical function), retrieving a dynamic budget-aware subset per turn, and composing prompts with policy-first boundaries.

This PRD is intentionally integrated with the existing Character + Chat stack, not a parallel persona runtime.

Primary goals:
- Lift persona adherence for character chats with curated labeled exemplars and dynamic selection.
- Keep refusals in-character while honoring platform safety and capabilities.
- Add diagnostics (IOO/IOR/LCS) without incentivizing over-copying.

Out of scope (MVP):
- Fine-tuning/training.
- User-content harvesting beyond explicit curator actions.
- Replacing the existing `/api/v1/persona` scaffold agent loop.
- New standalone safety framework.


## 2) User Stories (MVP)
- As a user, I can choose a character and receive in-character responses that stay policy-compliant.
- As a curator, I can import, label, and search role-play exemplars for a character.
- As a developer, I can debug which demos were selected and why.
- As an operator, I can monitor demo utilization and safety adherence.


## 3) Architecture Overview
Components and repo paths:
- Content Store (extend existing DB layer):
  - `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
  - `tldw_Server_API/app/core/Character_Chat/modules/character_db.py` and migration helpers
- Retrieval & Packer (new module in Character/Chat domain):
  - `tldw_Server_API/app/core/Character_Chat/modules/persona_exemplar_selector.py` (new)
- Prompt Compiler integration:
  - `tldw_Server_API/app/core/Chat/chat_service.py`
  - `tldw_Server_API/app/core/Chat/chat_helpers.py`
- API Endpoints (extend character endpoints):
  - `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py`
- Schemas (extend existing schemas):
  - `tldw_Server_API/app/api/v1/schemas/character_schemas.py`
  - `tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py`
- Telemetry/Evals:
  - `tldw_Server_API/app/core/Chat/chat_metrics.py`
  - `tldw_Server_API/app/core/Evaluations/` (new persona-style eval helper, integrated into existing eval APIs)
- Embeddings: existing Chroma integration under `app/core/Embeddings/`

Flow per chat turn (integrated path):
1) `POST /api/v1/chat/completions` receives `character_id` and optional exemplar selection overrides.
2) Build standard character + conversation context through existing chat context assembly.
3) Classify user turn and retrieve character-scoped exemplar candidates (BM25 + embeddings), filtered by safety.
4) Score, diversify (MMR), and greedy-pack to demo token budget with rhetorical coverage.
5) Compose final prompt in existing chat pipeline: platform/system policy, character boundaries, demos, user/history.
6) Compute telemetry (IOO/IOR/LCS), attach to logs/metrics, and return optional debug metadata.


## 4) Data Model (Minimal)
Primary storage: existing per-user ChaChaNotes DB (`Databases/user_databases/<user_id>/ChaChaNotes.db`), via `CharactersRAGDB`.

Tables (add via migration):
- character_exemplars
  - id TEXT PRIMARY KEY (UUID)
  - character_id INTEGER NOT NULL REFERENCES character_cards(id)
  - text TEXT NOT NULL
  - source_type TEXT CHECK(source_type IN ('audio_transcript','video_transcript','article','other'))
  - source_url_or_id TEXT
  - source_date TEXT
  - novelty_hint TEXT CHECK(novelty_hint IN ('post_cutoff','unknown','pre_cutoff'))
  - emotion TEXT CHECK(emotion IN ('angry','neutral','happy','other'))
  - scenario TEXT CHECK(scenario IN ('press_challenge','fan_banter','debate','boardroom','small_talk','other'))
  - rhetorical JSON TEXT  -- JSON array: ["opener","emphasis","ender",...]
  - register TEXT
  - safety_allowed JSON TEXT
  - safety_blocked JSON TEXT
  - rights_public_figure INTEGER DEFAULT 1
  - rights_notes TEXT
  - length_tokens INTEGER NOT NULL
  - created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  - updated_at TIMESTAMP
  - is_deleted INTEGER DEFAULT 0

- character_exemplars_fts (FTS5 virtual)
  - text, character_id, emotion, scenario
  - external content = `character_exemplars`

Indexes:
- idx_character_exemplars_character (character_id)
- idx_character_exemplars_scenario_emotion (scenario, emotion)
- idx_character_exemplars_novelty (novelty_hint)

Embeddings:
- Chroma collection per user+character:
  - `character_exemplars:{user_id}:{character_id}`
  - doc_id = exemplar id
  - metadata: `{character_id, emotion, scenario, rhetorical, novelty_hint, length_tokens}`

JSON constraints are validated in API layer; DB stores as TEXT.

Future option (out of MVP): shared read-only global curated overlay with per-tenant merge rules.


## 5) API Surface (Minimal)
Primary base path: `/api/v1/characters/{character_id}`

Schemas (Pydantic) in `app/api/v1/schemas/character_schemas.py`:
- ExemplarIn: `{text, source: {type, url_or_id?, date?}, novelty_hint?, labels: {emotion, scenario, rhetorical[], register?}, safety: {allowed[], blocked[]}, rights: {public_figure?, notes?}}`
- Exemplar: `ExemplarIn + {id, character_id, length_tokens, created_at, updated_at}`
- SearchRequest: `{query?, filter: {emotion?, scenario?, rhetorical?[]}, limit?, offset?}`
- SearchResponse: `{items: [Exemplar], total}`
- SelectionConfig: `{budget_tokens (int, default 600), max_exemplar_tokens (int, default 120), mmr_lambda (float, default 0.7)}`
- SelectionDebug: `{selected: [Exemplar], budget_tokens, coverage: {openers, emphasis, enders, catchphrases_used}, scores: [{id, score}]}`
- Telemetry: `{ioo, ior, lcs, safety_flags: [str]}`

Endpoints in `app/api/v1/endpoints/characters_endpoint.py`:
- POST `/exemplars` → create one or many (list)
- GET `/exemplars/{id}` → fetch
- PUT `/exemplars/{id}` → update (text/labels/metadata)
- DELETE `/exemplars/{id}` → delete (soft delete)
- POST `/exemplars/search` → hybrid search; returns `SearchResponse`
- POST `/exemplars/select/debug` → returns `SelectionDebug` for `{user_turn, selection_config?}`

Chat Integration (extend existing Chat API):
- `POST /api/v1/chat/completions`
  - Existing field remains primary: `character_id`
  - New optional fields:
    - `persona_exemplar_budget_tokens?: int`
    - `persona_exemplar_strategy?: str`
    - `persona_debug?: bool`
  - Response (when debug enabled): `meta.persona.telemetry?: Telemetry` and `meta.persona.debug_id?`

Compatibility:
- `persona_id` (if sent by older clients) may be accepted as an alias only when it can be resolved deterministically to `character_id`.

AuthNZ & Rate Limits:
- Reuse existing character/chat dependencies in `API_Deps`.
- Exemplar write ops follow same permission model as character writes in multi-user mode.


## 6) Selection Algorithm (Default)
Inputs: `user_turn`, `character_id`, `SelectionConfig`.

Steps:
1) Classify `user_turn` to `{intent/topic, scenario heuristic, emotion heuristic}`.
2) Candidate set = top-N by hybrid retrieval (FTS5 + Chroma cosine) for the same `character_id`.
3) Apply safety gates:
   - Exclude exemplars with `safety_blocked` that conflict with detected request category.
4) Score each exemplar:
   - `score = 0.45*intent_sim + 0.25*scenario_match + 0.20*emotion_match + 0.10*novelty_weight`
   - `novelty_weight = 1.0 post_cutoff, 0.5 unknown, 0.0 pre_cutoff` (tunable per character)
5) Diversify with MMR (`λ ~= 0.7`).
6) Greedy-pack into `budget_tokens`, with soft coverage:
   - `<= max_exemplar_tokens` per exemplar (default 120)
   - Prefer many short snippets
   - Cap catchphrase frequency (`<=1-2` per 200 tokens)
   - Coverage target: 2-3 openers, 2-3 emphasis, 1-2 enders, 1-2 longer snippets
7) Sanity pass:
   - Dedupe near-duplicates
   - Strip non-persona lines
   - Finalize pack


## 7) Prompt Composition (Hardened)
- System: platform policies; refuse unsafe requests; do not reveal system/dev prompts; keep refusals in character.
- Character boundary layer: character card system prompt + explicit capability boundaries.
- Demos: character-only snippets grouped by rhetorical function; no interviewer text.
- User/history: current turn plus bounded conversation turns from existing chat history logic.

Refusal responses remain in character and offer safe alternatives.


## 8) Telemetry & Evaluation
- IOO (Input-Over-Output): overlap of output tokens with selected demos (stopword-reduced; approved catchphrases excluded). Flag if >30-40% for outputs >150 tokens.
- IOR (Input-Over-Retrieved): share of retrieved demo tokens used. Too low = retrieval miss; too high = over-copying risk.
- LCS: normalized longest common subsequence between output and demos.
- Safety: count violations/refusals using existing moderation/safety hooks.

Surfacing:
- Attach to logs (PII-safe) with `debug_id` correlation.
- Track aggregates through existing metrics/evals surfaces.
- Optional response field under `meta.persona.telemetry` when `persona_debug=true`.


## 9) Security, Safety, Legal
- No fabricated quotes attributed to real people.
- Keep policy boundaries in platform/system layers, not attributed to persona.
- Enforce `safety_blocked` during exemplar selection.
- Rights metadata is required for curated public-figure content (`rights_public_figure`, `rights_notes`).


## 10) Rollout Plan (4 Sprints)
- Sprint 1: Data + CRUD on character stack
  - Add exemplar tables/migrations to ChaChaNotes DB.
  - Add exemplar CRUD/search endpoints under `characters`.
  - Unit tests for DB + endpoints.

- Sprint 2: Retrieval + Packer
  - Hybrid search, MMR, budget packer, heuristic classifier.
  - Integration tests with mock data and embeddings.

- Sprint 3: Chat Integration
  - Integrate selector/packer into chat context assembly for `character_id` path.
  - Add request flags (`persona_exemplar_*`) and debug response metadata.
  - E2E tests with mock LLM provider.

- Sprint 4: Telemetry + Evals
  - IOO/IOR/LCS metrics and alerting hooks.
  - Red-team prompt tests for over-copying and injection pressure.


## 11) Acceptance Criteria (MVP)
Functional:
- CRUD: create/update/delete/search exemplars for a character via API.
- Selection: given `character_id` and `user_turn`, return packed demos within `<=800` tokens, covering opener/emphasis/ender, with `<=120` tokens per exemplar.
- Chat: `POST /api/v1/chat/completions` with `character_id` yields in-character outputs and policy-compliant refusals with exemplar augmentation enabled.
- Telemetry: IOO/IOR/LCS computed and logged per response, optional debug field when requested.

Quality / Metrics:
- Persona adherence (heuristic): >=80% sampled responses judged in-character; no fabricated quotes.
- Safety: no increase in violation rate vs baseline; refusals stay in-character.
- IOO: <=30% for outputs >150 tokens (excluding approved catchphrases), with sustained exceedance alerting.
- IOR: typical 10-60%, monitored for misses/over-copying.

Operational:
- Works in single-user and multi-user AuthNZ modes.
- Exemplar write endpoints follow existing character write permission model.
- Performance target: selector + prompt assembly adds <=120ms p95 for local character with <=10k exemplars.


## 12) Open Questions
- Do we need a shared global curated overlay in v0, or is per-user/per-character storage sufficient?
- Should `persona_id` alias support be temporary with deprecation messaging, or immediate strict `character_id` only?
- What IOO alert policy should auto-adjust demo budget versus log-only?


## 13) Implementation Notes
- Follow `CharactersRAGDB` + migration patterns in `app/core/DB_Management/ChaChaNotes_DB.py`.
- Keep DB access in the Character/Chat abstractions; no raw SQL in endpoints.
- Use Chroma batching for embedding upserts keyed by exemplar id.
- Keep default demo budget 600 tokens, configurable in server config.
- Testing should mirror existing suites under:
  - `tldw_Server_API/tests/Character_Chat_NEW/`
  - `tldw_Server_API/tests/Chat_NEW/`
  - `tldw_Server_API/tests/Persona/` (only for scaffold compatibility, not primary role-play serving path)
