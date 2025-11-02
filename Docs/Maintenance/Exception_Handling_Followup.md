Exception Handling Follow-Up (BLE001)

Goal
- Improve observability and safety for broad exception handlers that are intentionally tolerated today (marked with `# noqa: BLE001`).
- Where feasible, narrow exception scopes or add structured context to logs without changing behavior.

Scope Candidates (non-exhaustive)
- tldw_Server_API/app/main.py
  - Import gating for optional routers (audio, tools, workflows, evals, sandbox)
  - Route gating for metrics
  - Action: keep broad catch, ensure warning logs include module name and error message (already done), consider adding a hint for enabling the route via settings.

- tldw_Server_API/app/api/v1/API_Deps/setup_deps.py
  - Proxy / loopback heuristics and header parsing
  - Action: keep defensive catches; add debug log with the offending header value when parsing fails.

- tldw_Server_API/app/core/Setup/install_manager.py
  - Install plan validation and per-engine installers (STT/TTS/Embeddings)
  - Action: maintain DownloadBlockedError flow; add structured fields (engine, variant/model, repo) in error logs.

- tldw_Server_API/app/core/Prompt_Management/prompt_studio/*
  - test_case_manager.py, job_processor.py
  - Action: ensure exceptions include job/test identifiers and state transitions in logs; consider a retry budget for transient exceptions.

- tldw_Server_API/app/core/DB_Management/*
  - PromptStudioDatabase.py, ChaChaNotes_DB.py, UserDatabase_v2.py, DB_Backups.py
  - Action: handlers already log with exc_info; add entity identifiers (media_id, version_number, user_id) consistently across paths and unify error messages.

- tldw_Server_API/app/core/DB_Management/backends/postgresql_backend.py
  - Transaction rollback fallbacks
  - Action: keep catch around rollback; include connection dsn/label and operation in error log.

Proposed Changes (incremental)
1) Replace silent `except: pass` with low-level debug/warn (DONE where present under app/ and endpoints/).
2) For BLE001 blocks, add contextual fields to logger calls:
   - keys: `module`, `operation`, `entity_id`, `user_id`, `request_id`, `db_path`/`dsn`, `engine`, `variant`, `repo`.
3) Where a broad catch protects optional features, include a short "enablement hint" in logs (e.g., required env or extras).
4) Avoid behavior changes - keep existing return values and status codes.

Validation Plan
- Focused pytest runs for changed modules:
  - Chat_NEW integration suite for `main.py` middleware/routers import.
  - Embeddings unit suite for endpoints and background workers.
  - RAG health integration for endpoint availability.
- Verify no additional warnings are promoted to errors; logs visible at DEBUG/INFO.

Tracking
- Open a small PR per sub-area to keep diffs reviewable.
- Link PRs to this doc; check off modules as completed.

Status
- Silent `except …: pass` removed or converted to logs in:
  - endpoints/chat.py (usage log)
  - endpoints/media.py (failed/empty upload cleanup)
  - main.py (trace headers middleware; embeddings dimension check; logging wrapper)
- Smoketests green: Chat_NEW, Embeddings v5 unit, RAG health.
