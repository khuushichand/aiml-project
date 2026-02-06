# RAG Multi-Tenant Isolation Design

## Purpose
Define tenant and user isolation boundaries for the unified RAG pipeline and
document the trust model for caches, persisted artifacts, and observability.

## Trust Assumptions
- Authentication and principal resolution are handled before RAG entry points.
- `user_id` and `index_namespace` values passed into RAG are trusted only after
  AuthNZ normalization/authorization.
- Operators should use opaque tenant identifiers for `index_namespace` and
  avoid human-readable PII in namespace values.

## Isolation Boundaries

### 1) Data stores and retrieval scope
- Retrieval uses request-scoped DB adapters/paths and optional
  `index_namespace`.
- Postgres deployments can enforce DB-side row isolation using
  `app.current_user_id` RLS policies.

### 2) Semantic and adaptive cache scope
- Shared cache instances are keyed by namespace in
  `get_shared_cache(...)` (`semantic_cache.py`).
- Cache persistence paths are sanitized and rooted under the configured cache
  base directory; out-of-base paths are rejected and replaced by safe defaults.
- Namespace-specific clearing is supported via `clear_shared_caches(namespace=...)`.

### 3) Rewrite cache scope
- Rewrite cache storage is per-user by default through
  `DatabasePaths.get_user_rewrite_cache_path(user_id)`.
- Rewrite lookup keys include corpus (`index_namespace`) and intent, preventing
  cross-corpus collisions for identical raw queries.

### 4) Payload exemplars scope and redaction
- Exemplar sink selection prefers `namespace`, then `user_id`, then global sink.
- Namespace/user segments are sanitized before directory selection.
- Exemplar payloads are redacted (`_redact`) before write and bounded in size.

## Multi-Tenant Safe Profile
- Use `get_multi_tenant_safe_kwargs(namespace, overrides=...)` for shared
  environments.
- This enforces `index_namespace=namespace`, keeps lightweight monitoring on,
  and disables OTEL-style detailed observability by default.
- To disable exemplar sampling in shared SaaS contexts, set
  `RAG_PAYLOAD_EXEMPLAR_SAMPLING=0`.

## Telemetry and Off-Box Export Guidance
- Prefer tenant-safe labels only (opaque namespace IDs, no raw query text).
- Keep high-cardinality and sensitive fields out of external sinks.
- When exporting traces/metrics off-box, treat exports as sensitive:
  - enforce TLS and restricted endpoints
  - apply retention limits
  - keep role-based access around observability backends
  - disable exemplar sampling unless incident debugging requires it

## Test Coverage Guards
- Semantic cache namespace behavior:
  - `tldw_Server_API/tests/RAG_NEW/unit/test_semantic_cache_tenant_scoping.py`
- Rewrite cache corpus/user scoping:
  - `tldw_Server_API/tests/RAG_NEW/unit/test_rewrite_cache.py`
- Exemplar metadata and redaction behavior:
  - `tldw_Server_API/tests/RAG_NEW/unit/test_payload_exemplars.py`

