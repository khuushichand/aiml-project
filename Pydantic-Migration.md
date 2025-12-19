# Pydantic Request Model Migration

Goal: Replace dict-based request bodies with explicit Pydantic models to gain validation, clear OpenAPI, and consistent error semantics (prefer 422 Unprocessable Entity for invalid payloads). Keep extra='forbid' unless compatibility requires permissive extras.

## Status Summary

- Phase 1 — Completed
  - Admin cleanup settings: strict model + bounds
    - tldw_Server_API/app/api/v1/schemas/admin_schemas.py
    - tldw_Server_API/app/api/v1/endpoints/admin.py
  - Notes export request model
    - tldw_Server_API/app/api/v1/schemas/notes_schemas.py
    - tldw_Server_API/app/api/v1/endpoints/notes.py
  - Connectors sources add/patch
    - tldw_Server_API/app/api/v1/schemas/connectors.py
    - tldw_Server_API/app/api/v1/endpoints/connectors.py
  - Prompts legacy/compat + collections
    - tldw_Server_API/app/api/v1/schemas/prompt_schemas.py
    - tldw_Server_API/app/api/v1/endpoints/prompts.py
  - Prompt Studio simple endpoints (run/execute/optimization)
    - tldw_Server_API/app/api/v1/schemas/prompt_studio_*.py
    - tldw_Server_API/app/api/v1/endpoints/prompt_studio_*.py

- Phase 2 — Completed
  - Embeddings A/B test run request
    - Added EmbeddingsABTestRunRequest (extra='forbid')
      - tldw_Server_API/app/api/v1/schemas/embeddings_abtest_schemas.py
    - Updated run endpoint to accept typed model
      - tldw_Server_API/app/api/v1/endpoints/evaluations_embeddings_abtest.py
    - Tests: tldw_Server_API/tests/Evaluations/test_embeddings_abtest_run_api.py
  - Llama.cpp inference request
    - Added LlamaCppInferenceRequest (extra='allow' to preserve llama-specific fields)
      - tldw_Server_API/app/api/v1/schemas/llamacpp_schemas.py
    - Updated inference endpoint to use typed model
      - tldw_Server_API/app/api/v1/endpoints/llamacpp.py
    - Tests: tldw_Server_API/tests/LLM_Local/test_llamacpp_inference_api.py

## Phase 3 — In Progress

Public endpoints still using untyped dict bodies. Current implementation status and acceptance criteria below.

1) Character chat sessions — legacy completion
   - Endpoint: tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py:368
   - Current: payload: Dict[str, Any] = None (unused)
   - Plan:
     - Keep accepting an optional dict payload for now to preserve existing tests that post bodies to this endpoint. The payload is ignored. Revisit later if we deprecate the endpoint entirely.
   - Tests: existing rate-limit tests cover behavior.

2) Evaluations CRUD — create run (Completed)
   - Endpoint: tldw_Server_API/app/api/v1/endpoints/evaluations_crud.py:203
   - Current: request: Dict[str, Any]
   - Implemented schema: CreateRunSimpleRequest(BaseModel, extra='forbid')
     - target_model: Optional[str]
     - config: Dict[str, Any] = {}
     - webhook_url: Optional[str]
   - Update endpoint to use typed model and pass through fields (config is free-form dict). Returns 422 on extra keys. Preserves optional target_model.
   - Tests added: positive (valid payload), negative (extra key 422).

3) Chunking Templates — validate (Completed)
   - Endpoint: tldw_Server_API/app/api/v1/endpoints/chunking_templates.py:770
   - Current: template_config: Dict[str, Any] = Body(...)
   - Implemented: keep request body as Dict to preserve 200 return semantics for invalid payloads, but parse using TemplateConfig inside the handler and convert Pydantic ValidationError(s) into a TemplateValidationResponse (status 200). This avoids FastAPI 422 while enforcing schema checks.
     - tldw_Server_API/app/api/v1/schemas/chunking_templates_schemas.py:24 (TemplateConfig)
   - Tests: valid config remains 200; missing required keys remains 200 with errors; added test to ensure classifier schema errors surface as 200 with errors, not 422.

4) Triage — chat.py helper uses Dict internally (not a public request body)
   - tldw_Server_API/app/api/v1/endpoints/chat.py:569 (internal helper param)
   - No change required; not exposed as a request body.

## Error Semantics

- Default: rely on Pydantic for validation → FastAPI 422 errors for invalid payloads or extra keys when extra='forbid'.
- If an endpoint historically returned 400 for certain invalid values, either:
  - Update tests to expect 422, or
  - Wrap validation to translate Pydantic errors to a 400 while preserving detail. Prefer 422 for new endpoints.

## Test Plan (additions per endpoint)

- Positive: minimal valid payload returns expected 2xx and response shape.
- Negative: unknown/extra keys → 422.
- Boundary: numeric/ge bounds where applicable.
- Compatibility: if replacing an unused payload param, assert status and output remain unchanged.

## Checklist per migration

- Define request model in appropriate schemas module (extra='forbid' unless needs pass-through).
- Replace Dict[str, Any] request arg with the typed model.
- Update OpenAPI description/response_model if needed.
- Add targeted tests (unit/integration) for success and failure cases.
- Run pytest targeted markers and ensure no route gating affects tests.

## Notes

- Connectors, Prompts, Prompt Studio, Admin cleanup, Notes export migrations are done and tested.
- Embeddings A/B run and Llama.cpp inference are complete with tests.
- If any endpoints are behind route gating (e.g., connectors, llamacpp, evaluations), tests should either enable via ROUTES_ENABLE or mount routers into a minimal FastAPI app to avoid gating.
