# Llama.cpp Thinking Budget And Grammar Library Design

Date: 2026-03-10
Status: Approved
Scope: `POST /api/v1/chat/completions`, shared chat/playground UI state, sidepanel/workspace session persistence, user-scoped grammar library

## 1. Summary

Add first-class llama.cpp advanced controls for:

- constrained generation via reusable custom GBNF grammars
- thinking-budget control when the deployment can map an app-level budget field to a verified llama.cpp request parameter

The design keeps these controls llama.cpp-specific, reuses the existing chat model settings state pipeline, stores reusable grammars as a user-owned resource, and translates app-level fields into llama.cpp request payload extensions at send time.

## 2. User-Approved Decisions

1. Ship a full-stack feature, not API-only.
2. Scope the feature to `llama.cpp` only.
3. Support both per-request use and persistence in saved chat/session state.
4. Use a user-scoped reusable grammar library.
5. Support selecting a saved grammar with an optional per-request inline override.
6. Prefer first-class UI controls over a raw `extra_body`-only UX.
7. Keep raw transport details behind a backend translation layer.

## 3. Review-Driven Revisions

This design was revised after a design review to address these issues:

1. Do not assume a stable upstream per-request thinking-budget request key for llama.cpp.
2. Reuse the existing `ChatModelSettings` store and session snapshot pipeline instead of inventing a new preset backend.
3. Treat advanced llama.cpp controls as unavailable when `strict_openai_compat` disables non-standard request keys.
4. Make `chat/completions` the only v1 request surface. `/api/v1/messages` support is a follow-on task.
5. Define conflict rules between first-class controls and raw `extra_body`.

## 4. Current State

### 4.1 Existing Capabilities

- Chat/playground UI already persists model settings such as `apiProvider`, `numPredict`, `reasoningEffort`, and raw `extraBody` in `apps/packages/ui/src/store/model.tsx`.
- Sidepanel chat already snapshots `modelSettings` into per-tab session state, and workspace/playground paths already reuse the same store family.
- The backend already forwards provider-specific payload extensions through `extra_body`.
- llama.cpp already advertises `grammar` as a known extra-body compatibility key in `tldw_Server_API/app/core/LLM_Calls/extra_body_compat_catalog.py`.
- `GET /api/v1/llm/providers` already exposes capability metadata and extra-body compatibility hints that UIs can consume.

### 4.2 Gaps

- There is no first-class grammar library resource.
- The UI exposes raw `extraBody` JSON but no guided grammar workflow.
- There is no stable app-level contract for a llama.cpp thinking budget.
- `strict_openai_compat` can drop non-standard payload keys, which would silently break naive advanced-control implementations.
- `/api/v1/messages` also supports llama.cpp, but there is no aligned advanced-control story there yet.

## 5. Goals And Non-Goals

### 5.1 Goals

- Add first-class llama.cpp grammar selection and editing in the chat/playground UI.
- Persist grammar/thinking selections in existing chat/session state and snapshots.
- Introduce a user-scoped grammar library with CRUD operations.
- Keep the request contract safe when llama.cpp deployment/runtime settings disable non-standard keys.
- Centralize translation from app-level fields to llama.cpp request payload extensions.

### 5.2 Non-Goals

- No generic advanced-controls framework for other providers in this phase.
- No new reusable server-side chat preset backend in this phase.
- No `/api/v1/messages` llama.cpp advanced-control support in v1.
- No promise that the server can validate every GBNF grammar offline without a llama.cpp-compatible validator/runtime.

## 6. Proposed Architecture

### 6.1 Canonical UI State Path

Extend the existing shared chat settings store instead of creating a parallel state model.

Add llama.cpp-specific state keys to `ChatModelSettings`:

- `llamaThinkingBudgetTokens?: number`
- `llamaGrammarMode?: "none" | "library" | "inline"`
- `llamaGrammarId?: string`
- `llamaGrammarInline?: string`
- `llamaGrammarOverride?: string`

These values become part of the same snapshot flow already used by sidepanel/workspace chat state.

This means “saved chat/session presets” in v1 are implemented by:

- existing session/tab snapshots
- existing persisted model settings consumers

This phase does not add a separate reusable preset resource.

### 6.2 Backend Translation Layer

Add a dedicated llama.cpp request-extension resolver, for example:

`tldw_Server_API/app/core/LLM_Calls/llamacpp_request_extensions.py`

Responsibilities:

1. Accept app-level request fields from `ChatCompletionRequest`.
2. Enforce provider guard: only valid when `api_provider == "llama.cpp"`.
3. Resolve grammar selection into final GBNF text.
4. Merge first-class llama.cpp controls into `extra_body` with deterministic precedence.
5. Refuse advanced llama.cpp controls when runtime strict compatibility disables non-standard fields.
6. Map `thinking_budget_tokens` into the deployment’s configured/verified upstream request key.

### 6.3 Capability-Gated Thinking Budget

Grammar support is always first-class for llama.cpp because the current compatibility catalog already knows about `grammar`.

Thinking-budget support must be capability-gated.

The server should not hard-code a guessed upstream request-body field. Instead:

1. Expose a dedicated capability such as `llama_cpp_controls.thinking_budget`.
2. Mark it `supported=true` only when the deployment can map the app-level field to a verified upstream request key.
3. Return `supported=false` with an `effective_reason` when the deployment cannot safely support it.

This allows the grammar workflow to ship even if a given llama.cpp deployment cannot yet expose a safe per-request thinking budget.

## 7. API And Data Model

### 7.1 Chat Request Extensions

Extend `ChatCompletionRequest` with llama.cpp-only top-level extension fields:

- `thinking_budget_tokens: int | null`
- `grammar_mode: "none" | "library" | "inline" | null`
- `grammar_id: str | null`
- `grammar_inline: str | null`
- `grammar_override: str | null`

Server behavior:

1. Reject these fields with `400` when `api_provider != "llama.cpp"`.
2. Reject these fields with `400` when llama.cpp strict compatibility disables advanced controls.
3. Reject invalid combinations:
   - `grammar_mode == "library"` without `grammar_id`
   - `grammar_mode == "inline"` without `grammar_inline`
4. Translate accepted values into llama.cpp `extra_body`.

### 7.2 Grammar Library Resource

Add a user-scoped grammar library API under the chat domain:

- `GET /api/v1/chat/grammars`
- `POST /api/v1/chat/grammars`
- `GET /api/v1/chat/grammars/{grammar_id}`
- `PATCH /api/v1/chat/grammars/{grammar_id}`
- `DELETE /api/v1/chat/grammars/{grammar_id}`

Grammar record shape:

- `id`
- `name`
- `description`
- `grammar_text`
- `validation_status: "unchecked" | "valid" | "invalid"`
- `validation_error: str | null`
- `last_validated_at`
- `created_at`
- `updated_at`
- `is_archived`

Storage should follow the same user-scoped pattern as existing chat-owned resources such as chat dictionaries, using the per-user ChaChaNotes database layer rather than a new global database.

### 7.3 Provider Metadata Additions

Extend provider capability metadata returned from `GET /api/v1/llm/providers` with a stable app-level capability block for llama.cpp controls:

```json
{
  "llama_cpp_controls": {
    "grammar": {
      "supported": true,
      "source": "first_class+extra_body",
      "effective_reason": "supported in current deployment"
    },
    "thinking_budget": {
      "supported": false,
      "effective_reason": "no verified request mapping configured for this deployment"
    }
  }
}
```

This metadata is separate from existing `extra_body_compat`. `extra_body_compat` remains a low-level passthrough hint; `llama_cpp_controls` becomes the first-class UI contract.

## 8. Persistence Model

### 8.1 Session And Snapshot Persistence

Persist the new llama.cpp settings in the same client-side/session snapshot structures that already store `modelSettings`.

This covers:

- sidepanel tab snapshots
- workspace/playground session persistence
- any existing restore flows that already round-trip `ChatModelSettings`

### 8.2 Reusable Grammar Persistence

Reusable grammars live in the new user-scoped grammar library resource, not inside session snapshots.

Snapshots store:

- grammar mode
- grammar id
- inline grammar text
- inline override text
- thinking budget value

Library records store:

- reusable named grammar text and metadata

## 9. UX Flow

### 9.1 Surface

Show a llama.cpp-only advanced section when the selected provider is `llama.cpp`.

Controls:

- `Thinking budget` numeric input
- `Grammar source` segmented control: `None`, `Saved grammar`, `Inline`
- saved grammar picker when `Saved grammar` is selected
- inline grammar editor when `Inline` is selected
- optional override editor when `Saved grammar` is selected
- `Manage grammars` entry point into the grammar library CRUD UI

### 9.2 Runtime Behavior

1. When provider changes away from `llama.cpp`, keep the values in local state but disable the controls.
2. Exclude llama.cpp extension fields from outgoing non-llama.cpp requests.
3. When a saved grammar reference is missing or archived, surface a degraded-state warning and require reselection or inline replacement before send.
4. When capability metadata says `thinking_budget.supported == false`, disable the numeric input and show the provider-reported reason.

## 10. Conflict And Precedence Rules

This phase must define deterministic merge behavior between first-class controls and raw `extraBody`.

Rule set:

1. First-class llama.cpp controls win over conflicting raw `extraBody` keys.
2. If raw `extraBody` contains reserved keys such as `grammar` or the deployment’s configured thinking-budget key, the UI should warn and the backend should overwrite them with first-class values.
3. Raw `extraBody` remains available for other advanced llama.cpp keys.

Reserved keys:

- `grammar`
- configured thinking-budget request key for this deployment

## 11. Validation And Error Handling

### 11.1 Client-Side

- grammar mode combination checks
- empty grammar text checks
- grammar size bounds
- missing grammar reference handling
- JSON validity for raw `extraBody`

### 11.2 Server-Side

- provider guard
- strict-compat guard
- grammar lookup authorization
- missing/archived grammar rejection
- request combination validation
- bounded length checks on grammar text and override fields
- upstream llama.cpp rejection translated into grammar/thinking-specific errors

### 11.3 Grammar Validation Semantics

`validation_status` must mean:

- `unchecked`: stored but not validated against a compatible validator/runtime
- `valid`: validated successfully by the server/runtime
- `invalid`: validation failed; `validation_error` contains the last known reason

Do not label a grammar as `valid` unless the server has actually performed validation.

## 12. Scope Boundary For `/messages`

`/api/v1/messages` already treats `llama.cpp` as a native provider, but this design intentionally does not include that surface in v1.

v1 contract:

- supported: `POST /api/v1/chat/completions`
- follow-on: `/api/v1/messages` parity

This must be explicit in docs and tests to avoid mismatched user expectations.

## 13. Testing Strategy

### 13.1 Backend Unit

- chat schema validation for new llama.cpp extension fields
- llama.cpp provider guard
- strict-compat rejection path
- grammar resolution precedence over raw `extra_body`
- capability derivation for grammar and thinking-budget support

### 13.2 Backend Integration

- grammar library CRUD
- per-user isolation for grammar records
- successful chat request translation with saved grammar
- successful chat request translation with inline grammar
- degraded/missing grammar reference handling
- thinking-budget translation only when supported

### 13.3 Frontend

- `ChatModelSettings` store round-trip of new fields
- sidepanel/workspace snapshot persistence
- provider-gated rendering for llama.cpp controls
- disabled thinking-budget UI when provider metadata says unsupported
- warning state when raw `extraBody` conflicts with first-class controls

### 13.4 Regression

- existing raw `extraBody` workflows remain functional
- non-llama.cpp chat flows remain unchanged
- existing session snapshot restore behavior remains unchanged

## 14. Rollout

1. Add backend capability metadata and grammar library resource.
2. Add request translation and provider/strict guards.
3. Extend shared chat settings state and persistence.
4. Add llama.cpp advanced UI controls.
5. Add conflict warnings around raw `extraBody`.
6. Document the v1 boundary: `chat/completions` only.

## 15. Acceptance Criteria

1. Users can create, edit, archive, list, and delete reusable GBNF grammars in a user-scoped library.
2. Users can choose `None`, `Saved grammar`, or `Inline` grammar in the llama.cpp chat UI.
3. Existing chat/session persistence restores grammar and thinking-budget selections.
4. Grammar selections are translated into llama.cpp request payloads without requiring users to hand-edit `extra_body`.
5. If strict OpenAI compatibility disables advanced llama.cpp fields, the UI reflects that and the backend rejects unsupported requests clearly.
6. Thinking budget is only exposed when the deployment can safely map it to a verified llama.cpp request parameter.
7. Raw `extraBody` conflicts are handled deterministically and documented.
8. `/api/v1/messages` is explicitly documented as out of scope for this phase.
