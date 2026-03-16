# Model Router Auto Selection Design

**Date:** 2026-03-16

**Status:** Approved for planning

**Goal:** Add first-class model router support so requests using `model="auto"` are resolved to a concrete provider/model pair server-side, with provider-constrained routing by default, optional cross-provider routing, LLM-based routing as the default strategy, deterministic fallback, and reuse across chat-adjacent LLM surfaces.

## Problem

The current stack already normalizes provider/model selections and infers providers from model IDs, but it does not perform semantic routing. The frontend persists a concrete `selectedModel`, the shared UI client resolves an explicit `api_provider`, and the backend normalizes/validates provider-model pairs before execution. That is sufficient for explicit model selection, but it does not support "choose the best model for this request" behavior.

Treating `auto` as a missing model is not viable because several current surfaces assume a concrete model ID must exist before submission. Routing therefore needs to become a first-class cross-stack mode with a clear sentinel and a dedicated backend decision step that runs before existing provider/model normalization for execution.

## Approved Product Decisions

- `auto` is a first-class model sentinel in the UI and API.
- Provider-constrained routing is the primary default.
- Cross-provider routing is optional, not the default.
- LLM-based routing is the default strategy.
- Deterministic rules routing is the default fallback.
- Requests may optionally fail instead of falling back after router failure.
- Re-evaluate every turn by default.
- Sticky routing is optional and supported only where a stable scope key exists.
- The default routing objective is `highest_quality`.
- The router should be reusable across chat, character chat, writing playground, RAG answer generation, media analysis, and other LLM surfaces over time.

## Routing Contract

### `auto` Is Explicit

`auto` is a real selectable model value across the stack. It is not equivalent to "no model selected". The frontend must preserve it, allow it through validation, and send it to the server intentionally. The backend must recognize it before normal provider/model normalization and availability checks.

### Routing Boundary Modes

Routing boundary is explicit and has three modes:

1. `server_default_provider`
   The user did not pin a provider. Keep routing inside the server default provider unless cross-provider routing is enabled.

2. `pinned_provider`
   The user or caller pinned a provider explicitly. Keep routing inside that provider unless cross-provider routing is enabled.

3. `cross_provider`
   The router is allowed to choose across all eligible providers.

### Canonical Router Output

The router returns an internal `RoutingDecision` with concrete `provider`, `model`, and `canonical=true`.

Once a canonical routing decision exists:

- downstream code must not run additional provider inference on it
- downstream code must not strip or reinterpret namespaced model IDs
- availability checks operate on the canonical provider/model pair as-is

This prevents misrouting namespaced models like OpenRouter catalog IDs after the router has already made a valid decision.

### Sticky Routing Scope

Sticky routing is supported only when the caller provides a stable scope key, such as a conversation ID, chat session ID, or writing session ID. If a stable key does not exist, sticky mode degrades to per-turn routing.

Sticky decisions are bypassed automatically when a later request introduces a hard capability mismatch, including:

- tools become required
- vision/image input appears
- JSON mode becomes required
- context requirements increase beyond the previously selected model

## Routing Pipeline

The routing pipeline is:

`candidate prefilter -> sticky reuse check -> llm router -> rules fallback -> canonical decision -> existing execution path`

### 1. Candidate Prefilter

Build the candidate set from configured and enabled chat-capable models, then filter by:

- routing boundary mode
- enabled/configured provider inventory
- admin provider overrides and allowed-model constraints
- BYOK/provider credential availability
- provider health and circuit state
- hard capability requirements
- any per-surface allowlists or exclusions

If only one eligible candidate remains and `skip_when_single_candidate` is enabled, routing short-circuits and returns that model directly.

### 2. Sticky Reuse Check

Sticky reuse in v1 is deterministic, not semantic. Reuse is allowed only when this fingerprint matches:

`surface + objective + boundary_mode + pinned_provider + hard_capabilities + modality_flags + sticky_scope`

This avoids ambiguous "task class" heuristics in the first implementation.

### 3. LLM Router Strategy

The default router strategy uses a small dedicated concrete router model.

Input is minimized:

- latest user turn or a short surface-specific summary
- compact task features only
- no full history by default
- no raw tool schemas
- no file contents
- no image bytes

The router is only allowed to choose from the candidate set passed to it. Its structured output must be validated against the candidate pool before use.

The router model must:

- always be configured as a concrete provider/model pair
- never be `auto`
- be excluded from the routed candidate pool

This prevents recursive routing.

### 4. Rules Fallback Strategy

Rules fallback is deterministic and boring by design.

Order:

1. hard capability filtering
2. objective-based ranking using routing metadata
3. provider/surface preferred-model tie-breaking
4. admin-curated per-provider ordered fallback list when metadata is incomplete

If no candidate survives and failure mode is configured to error, the request returns a clear structured error to the caller.

### 5. Existing Execution Path

After routing, the existing provider execution path remains responsible for:

- actual provider invocation
- any execution-time provider fallback behavior
- normal response construction

Execution fallback and routing fallback are separate concerns and must remain separate in code and logs.

## Components

Create a shared server-side routing module under a path like:

`tldw_Server_API/app/core/LLM_Calls/routing/`

### `ModelRouterService`

Single public entry point. Accepts a routing request, returns a canonical `RoutingDecision`, and encapsulates the entire routing pipeline.

### `RoutingPolicyResolver`

Merges:

- global defaults
- per-surface defaults
- per-request overrides

Request overrides should live under one server extension object:

```json
{
  "routing": {
    "strategy": "llm_router",
    "objective": "highest_quality",
    "mode": "per_turn",
    "cross_provider": false,
    "failure_mode": "fallback_then_error"
  }
}
```

This keeps server extensions grouped instead of scattering many new top-level OpenAI-like fields.

### `CandidatePoolBuilder`

Builds and filters the candidate set using inventory, policy, auth/credentials, health, capabilities, and overrides.

### `LLMRouterStrategy`

Invokes the dedicated router model with minimal structured context and validates that the selected provider/model exists in the provided candidate set.

### `RulesRouterStrategy`

Deterministic fallback. Requires ranking metadata where available and admin-curated fallback ordering where metadata is incomplete.

### `RoutingDecisionStore`

Stores sticky decisions with:

- scope key
- objective
- provider boundary mode
- selected provider/model
- routing fingerprint
- policy/config fingerprint
- last updated timestamp

This allows invalidation when policy or inventory changes.

### `RoutingTelemetry`

Emits structured routing data for logs and diagnostics, including:

- `decision_source`
- `fallback_used`
- `routing_scope`
- `router_selected_provider`
- `router_selected_model`
- `execution_provider`
- `execution_model`

## Candidate Metadata And Ranking

Rules fallback and policy shortcuts need metadata beyond the current basic catalog:

- `context_window`
- `tool_support`
- `vision_support`
- `reasoning_support`
- `json_mode_support`
- `quality_rank`
- `latency_rank`
- `cost_rank`
- optional `preferred_for_surfaces`

If ranking metadata is partial or missing, the router falls back to admin-curated ordered model lists per provider rather than inventing cross-model quality judgments dynamically.

## Frontend Behavior

### Selection UX

The UI should allow `selectedModel = "auto"` explicitly instead of treating it as "no model". Provider selection remains separate. If provider selection is also `auto`, the backend interprets that as `server_default_provider` boundary mode unless cross-provider routing is enabled.

### Validation

Any validation logic that currently assumes a concrete model ID must bypass or special-case `auto`. In particular:

- chat composer validation
- playground validation
- any availability checks that compare the selected model directly to server catalog IDs

### Client Request Shape

Shared client request types should add an optional `routing` object rather than proliferating additional top-level request fields.

### Debugging

Routing debug output should be opt-in, via a server extension flag or debug header. OpenAI-compatible default responses should remain unchanged unless debug mode is requested.

## Backend Integration Rules

### Early Interception

Routing must run before existing chat provider/model normalization and explicit availability checks. This is necessary because those code paths assume the request already references a concrete provider/model pair.

### Do Not Renormalize Routed Decisions

Once a canonical `RoutingDecision` has been produced, downstream execution logic must use that decision directly and skip additional provider/model normalization.

### Surface Rollout

The first integration target is `/api/v1/chat/completions`. After that:

1. character chat completion endpoint
2. writing playground generation flows
3. RAG answer generation and media analysis

The routing module itself should be surface-agnostic even if initial rollout is incremental.

## Accounting, Budgets, And Logging

Router invocations are real LLM calls and must be budgeted and logged separately from execution calls.

Requirements:

- separate budget accounting for router calls
- separate usage rows for router vs. execution calls
- separate operation names in usage tracking
- clear correlation between a routed request and the router call that selected it

Use the existing `llm_usage_log` path instead of inventing a parallel telemetry store. Extend it only if necessary. The existing migration groundwork for router analytics columns is the preferred base.

## Failure Handling

### Default Failure Behavior

- LLM router timeout or invalid output -> run rules fallback
- rules fallback produces valid candidate -> continue
- rules fallback produces no valid candidate -> clear structured error if failure mode demands it

### Sticky Invalidations

Sticky decisions are invalidated when:

- selected model is no longer in the candidate set
- provider health/policy removes eligibility
- sticky fingerprint no longer matches
- capability requirements increase beyond the prior model

### User-Facing Errors

Failure responses should explain why no eligible candidate exists, not just that routing failed. For example:

- provider boundary too restrictive
- no models with required tool support
- no vision-capable models enabled
- no provider credentials available

## Configuration Shape

Conceptual configuration:

```text
model_routing.enabled = true
model_routing.router_model.provider = "openai"
model_routing.router_model.model = "gpt-4.1-mini"
model_routing.router_model.exclude_from_candidates = true
model_routing.default_strategy = "llm_router"
model_routing.default_fallback_strategy = "rules_router"
model_routing.default_objective = "highest_quality"
model_routing.default_mode = "per_turn"
model_routing.default_cross_provider = false
model_routing.default_failure_mode = "fallback_then_error"
model_routing.skip_when_single_candidate = true
model_routing.surfaces.chat.enabled = true
model_routing.surfaces.character_chat.enabled = true
model_routing.surfaces.writing.enabled = true
model_routing.surfaces.rag.enabled = true
```

The exact persistence mechanism can be implemented via existing config parsing and env overrides rather than introducing a new bespoke configuration system.

## Testing Strategy

### Unit Tests

- policy resolution
- candidate filtering
- deterministic reuse fingerprint matching
- rules fallback ranking and fallback ordering
- router output validation
- recursion prevention for router model configuration

### Integration Tests

- `/api/v1/chat/completions` resolves `model="auto"` to a concrete canonical provider/model
- invalid router output falls back to rules routing
- failure mode `error` surfaces a clear structured error
- character chat and writing flows accept `auto` without frontend/client breakage

### UI Tests

- `auto` is allowed in selection and validation
- shared request typing includes nested `routing`
- client requests preserve `model="auto"` and routing overrides

## Rollout Plan

1. Shared routing module and config/policy support
2. Candidate metadata and deterministic fallback
3. Router usage accounting and telemetry
4. `/api/v1/chat/completions` integration
5. Frontend `auto` sentinel support
6. character chat and writing playground integration
7. later adoption by RAG answer generation and media analysis

## Risks To Watch

- accidental recursion if router model is not excluded
- double normalization of namespaced model IDs
- budget/accounting drift if router calls are not logged separately
- UI validation silently rejecting `auto`
- metadata gaps causing deterministic fallback to behave unpredictably

## Out Of Scope For V1

- semantic task-class reuse heuristics
- full-history router prompting
- cross-provider routing as the default behavior
- broad response-shape changes to default OpenAI-compatible payloads
