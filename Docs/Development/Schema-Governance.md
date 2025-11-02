Schema Governance - Embeddings Pipeline

Overview
- The embeddings pipeline uses versioned message envelopes carried across Redis Streams.
- Goals: safe evolution, forward/backward compatibility, and clear migration notes.

Artifacts
- Registry bundle (JSON): Docs/Development/schema/embeddings_registry.json
  - Contains logical schemas, versions, required fields, and upgrade notes.
- Current envelope schema: tldw.embeddings.v1
  - Fields: msg_version, msg_schema, schema_url, idempotency_key, dedupe_key, operation_id, job_id, user_id, media_id,
    priority, user_tier, created_at, updated_at, retry_count, max_retries, trace_id.

Compatibility Policy
- Minor additions: additive optional fields are allowed at any time; older workers must ignore unknown fields.
- Removals: only after a two-release deprecation window and when schema_version increments (v2).
- Breaking changes: require a new `msg_schema` value (e.g., tldw.embeddings.v2) and migration notes.

Validation
- Best-effort validation at ingress with a bundled JSON Schema.
- Workers normalize messages via `normalize_message(stage, data)` and validate core envelope.

Upgrade Rules
- v1 → v1.x: add optional metadata keys or stage-specific fields.
- v1 → v2: change field semantics or required sets; use dual-publish or shims until all consumers are updated.

Migration Notes
- If upgrading to v2, plan a rolling deploy in this order:
  1) Release workers that accept v1 and v2 (dual-read).
  2) Update producers to emit v2 (dual-write v1+v2 during bake-in if needed).
  3) Remove v1 publish once queues drain; keep v1 read for one full release cycle.

Schema URLs
- Each schema may point to a canonical URL (private or repo path). Bundle keeps an internal copy for offline validation.

Registry Maintenance
- Update `embeddings_registry.json` on every schema change.
- Keep `migration_notes` precise (what changed, why, rollout plan).
