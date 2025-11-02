# Persona Role-Play Stack (MVP) - PRD

## 1) Summary
Enable persona-consistent chat responses by curating persona-only exemplars, labeling them (emotion, scenario, rhetorical function), retrieving a dynamic, budget-aware subset per turn, and composing prompts with policy-first boundaries. Ship light telemetry (IOO/IOR) to measure demo utilization and detect retrieval drift or prompt injection.

Primary goals:
- Lift persona adherence with curated, labeled exemplars and dynamic selection.
- Keep refusals in-character while honoring platform safety and capabilities.
- Add diagnostics (IOO/IOR/LCS) without incentivizing over-copying.

Out of scope (MVP): fine-tuning/training; user-content harvesting; new safety frameworks.


## 2) User Stories (MVP)
- As a user, I can choose a persona and receive in-character responses that stay policy-compliant.
- As a curator, I can import, label, and search persona exemplars.
- As a developer, I can debug which demos were selected and why.
- As an operator, I can monitor demo utilization and safety adherence.


## 3) Architecture Overview
Components and repo paths:
- Content Store: `tldw_Server_API/app/core/DB_Management/Persona_DB.py` (new)
- Retrieval & Packer: `tldw_Server_API/app/core/RAG/persona_selector.py` (new)
- Prompt Compiler: `tldw_Server_API/app/core/LLM_Calls/prompt_compiler.py` (extend or add)
- API Endpoints: `tldw_Server_API/app/api/v1/endpoints/persona.py` (new)
- Schemas: `tldw_Server_API/app/api/v1/schemas/persona.py` (new)
- Telemetry/Evals: `tldw_Server_API/app/core/Evaluations/persona_eval.py` (new)
- Embeddings: use existing Chroma integration under `app/core/Embeddings/`

Flow per chat turn (persona path):
1) Classify user turn (intent/topic, scenario, emotion heuristic).
2) Hybrid retrieve candidates (BM25 + embeddings), filter by persona and safety.
3) Score, diversify (MMR), greedy-pack to demo token budget with rhetorical coverage.
4) Compile prompt: System (policy), Developer (persona + boundaries), Demos, User K turns.
5) Compute telemetry (IOO/IOR/LCS), attach to logs/metrics and optional debug response field.


## 4) Data Model (Minimal)
SQLite DB: `Databases/persona_exemplars.db` (global, read-only at inference; CRUD via API).

Tables:
- personas
  - id TEXT PRIMARY KEY (slug)
  - display_name TEXT NOT NULL
  - description TEXT
  - created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

- persona_exemplars (row store)
  - id TEXT PRIMARY KEY (UUID)
  - persona_id TEXT NOT NULL REFERENCES personas(id)
  - text TEXT NOT NULL
  - source_type TEXT CHECK(source_type IN ('audio_transcript','video_transcript','article','other'))
  - source_url_or_id TEXT
  - source_date TEXT
  - novelty_hint TEXT CHECK(novelty_hint IN ('post_cutoff','unknown','pre_cutoff'))
  - emotion TEXT CHECK(emotion IN ('angry','neutral','happy','other'))
  - scenario TEXT CHECK(scenario IN ('press_challenge','fan_banter','debate','boardroom','small_talk','other'))
  - rhetorical JSON TEXT  -- JSON array: ["opener","emphasis","ender",...]
  - register TEXT  -- optional (formal, informal)
  - safety_allowed JSON TEXT  -- JSON array of allowed categories
  - safety_blocked JSON TEXT  -- JSON array of blocked categories
  - rights_public_figure INTEGER DEFAULT 1  -- 0/1
  - rights_notes TEXT
  - length_tokens INTEGER NOT NULL
  - created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

- persona_exemplars_fts (FTS5 virtual)
  - text, persona_id, emotion, scenario
  - contentless FTS5 with external content = persona_exemplars

Indexes:
- idx_exemplars_persona (persona_id)
- idx_exemplars_scenario_emotion (scenario, emotion)
- idx_exemplars_novelty (novelty_hint)

Embeddings:
- Chroma collection per persona: `persona_exemplars:{persona_id}`
  - doc_id = exemplar id
  - metadata: {persona_id, emotion, scenario, rhetorical, novelty_hint, length_tokens}

JSON constraints are validated in API layer; DB stores as TEXT.


## 5) API Surface (Minimal)
Base path: `/api/v1/persona`

Schemas (Pydantic) in `app/api/v1/schemas/persona.py`:
- Persona: {id, display_name, description}
- ExemplarIn: {persona_id, text, source: {type, url_or_id?, date?}, novelty_hint?, labels: {emotion, scenario, rhetorical[], register?}, safety: {allowed[], blocked[]}, rights: {public_figure?, notes?}}
- Exemplar: ExemplarIn + {id, length_tokens, created_at}
- SearchRequest: {persona_id, query?, filter: {emotion?, scenario?, rhetorical?[]}, limit?, offset?}
- SearchResponse: {items: [Exemplar], total}
- SelectionConfig: {budget_tokens (int, default 600), max_exemplar_tokens (int, default 120), mmr_lambda (float, default 0.7)}
- SelectionDebug: {selected: [Exemplar], budget_tokens, coverage: {openers, emphasis, enders, catchphrases_used}, scores: [{id, score}]}
- Telemetry: {ioo, ior, lcs, safety_flags: [str]}

Endpoints in `app/api/v1/endpoints/persona.py`:
- POST `/exemplars` → create one or many (ndjson or list)
- GET `/exemplars/{id}` → fetch
- PUT `/exemplars/{id}` → update (text/labels/metadata)
- DELETE `/exemplars/{id}` → delete (soft delete optional later)
- POST `/exemplars/search` → hybrid search; returns SearchResponse
- POST `/select/debug` → returns SelectionDebug for given `{persona_id, user_turn, selection_config?}`

Chat Integration (extend existing Chat API):
- `POST /api/v1/chat/completions`
  - New optional fields in request: `{persona_id?: str, demo_budget_tokens?: int, demo_strategy?: str}`
  - Response: include `meta.persona.telemetry?: Telemetry` and `meta.persona.debug_id?` (for server logs correlation)

AuthNZ & Rate Limits: reuse existing dependencies in `API_Deps`; scope write ops to admin roles when multi-user.


## 6) Selection Algorithm (Default)
Inputs: user_turn, persona_id, SelectionConfig.

Steps:
1) Classify user_turn → {intent/topic, scenario heuristic, emotion heuristic}. Heuristic classifier first (embedding neighbors + regex for tone); ML classifier optional later.
2) Candidate set → top-N by hybrid retrieval (BM25 via FTS5 + Chroma cosine). Filters: persona_id match; exclude exemplars with safety_blocked that conflict with detected request category.
3) Score each exemplar:
   - score = 0.45*intent_sim + 0.25*scenario_match + 0.20*emotion_match + 0.10*novelty_weight
   - novelty_weight = 1.0 for `post_cutoff`, 0.5 unknown, 0.0 pre_cutoff (tunable per persona)
4) Diversify with MMR (λ ≈ 0.7).
5) Greedy pack into budget_tokens, enforcing soft coverage targets:
   - ≤ max_exemplar_tokens per exemplar (default 120)
   - Prefer many short snippets; cap catchphrase frequency (≤1-2 per 200 tokens)
   - Coverage: try for 2-3 openers, 2-3 emphasis, 1-2 enders, plus 1-2 longer snippets
6) Sanity pass: dedupe near-duplicates; strip non-persona lines if any; finalize pack.


## 7) Prompt Composition (Hardened)
- System: platform policies; refuse unsafe requests; do not reveal system/dev prompts; stay in character while refusing.
- Developer: persona description + capability boundaries (e.g., “as {CHAR}, I comment on code, I don’t write it”). No “restrictions lifted”.
- Demos: persona-only snippets grouped by rhetorical function; no interviewer text.
- User: current turn (+ last K turns as needed).

Refusal responses remain in character; offer alternative help paths.


## 8) Telemetry & Evaluation
- IOO (Input-Over-Output): share of output tokens overlapping demos (stopword-reduced; exclude approved catchphrase lexicon). Flag if >30-40% on outputs >150 tokens.
- IOR (Input-Over-Retrieved): share of retrieved demo tokens actually used. Too low → retrieval miss; too high → potential over-copying.
- LCS: longest common subsequence vs demos (normalized).
- Safety: count violations/refusals using existing safety hooks; log per request.

Surfacing:
- Attach to logs (PII-safe); expose aggregates via `app/core/Evaluations/persona_eval.py` and existing evaluations endpoints.
- Optional: include telemetry snippet in chat response `meta.persona.telemetry` when `debug=true`.


## 9) Security, Safety, Legal
- No fabricated quotes attributed to real people.
- Keep boundaries in system/dev prompts; never attribute policy to persona.
- Respect `safety_blocked` categories during selection.
- Rights: default to `public_figure: true` for public events; store notes; expand workflow later.


## 10) Rollout Plan (4 Sprints)
- Sprint 1: Data + CRUD
  - Persona DB + FTS5 schema; exemplar import; endpoints + schemas; unit tests.
- Sprint 2: Retrieval + Packer
  - Hybrid search, MMR, budget packer; heuristic classifier; integration tests with mock data.
- Sprint 3: Prompt Compiler + Chat Integration
  - Compiler assembly; chat request params; refusal templates; E2E tests with mock LLM provider.
- Sprint 4: Telemetry + Evals
  - IOO/IOR/LCS; metrics surfacing; red-team prompts; alerts when IOO collapses under hostile prompts.


## 11) Acceptance Criteria (MVP)
Functional
- CRUD: Can create, update, delete, and search exemplars for a persona via API.
- Selection: Given `persona_id` and `user_turn`, system returns a packed demo set within `≤800` tokens that includes coverage across opener/emphasis/ender and caps per-exemplar length at `≤120` tokens.
- Chat: `POST /api/v1/chat/completions` with `persona_id` yields in-character outputs and policy-compliant refusals.
- Telemetry: IOO/IOR/LCS computed and logged per response; optional debug field in response when requested.

Quality / Metrics
- Persona adherence (heuristic): ≥80% of sampled responses judged in-character by internal rubric; no fabricated quotes.
- Safety: No increase in violation rate vs baseline; refusals sound in-character.
- IOO: ≤30% for outputs >150 tokens (excluding approved catchphrases); alert on sustained exceedance.
- IOR: 10-60% typical range, monitored to detect retrieval miss (too low) or over-copying (too high).

Operational
- Works in both AuthNZ modes; write endpoints gated to admin in multi-user.
- Performance: Selection+compile adds ≤120ms p95 on local persona with ≤10k exemplars; scales with indexing.


## 12) Open Questions
- Do we need per-tenant persona overlays, or is a shared global store sufficient in v0?
- Should we expose persona boundary presets via API, or keep inline in developer prompt for now?
- What threshold and actions for IOO alerts (log only vs. degrade demo budget dynamically)?


## 13) Implementation Notes
- Follow `MediaDatabase` patterns in `app/core/DB_Management/` (context managers, migrations, FTS5 sync).
- Use Chroma batching for embedding upserts; key by exemplar id.
- Config: default demo budget 600 tokens; configurable per persona via server config.
- Testing: mirror patterns in `tldw_Server_API/tests/`; mock LLM provider and Chroma; include adversarial prompt set.
