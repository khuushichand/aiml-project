# Workflows PRD Gap Checklist

Source of truth: `Docs/Product/Workflows_PRD.md` (legacy UI excluded).

- [x] LLM step type separate from prompt (adapter + registry + validation); Owner: Backend/LLM; Tests: unit adapter + integration sync/async
- [x] Enforce assigned reviewer for approvals (admin override allowed); Owner: AuthNZ/API; Tests: integration approve/reject (assigned ok, owner deny, admin ok)
- [x] MCP tool allowlist/scopes per workflow; Owner: Security/MCP; Tests: unit allow/deny + integration blocked vs allowed
- [x] Orphan requeue for stale leases (with subprocess cleanup); Owner: Workflows engine; Tests: unit stale lease requeue + integration resume
- [x] Webhook step controls (per-step allow/deny, redirects, max bytes, signing); Owner: Backend/Security; Tests: unit policy enforcement + integration signature/redirect/size
- [x] Idempotency TTL 24h; Owner: Backend/DB; Tests: unit TTL reuse vs new run
- [x] Tokens/cost aggregation across steps; Owner: Backend/Metrics; Tests: unit aggregate + integration multi-step
- [ ] Map sub-step support expansion or explicit hard-fail with docs; Owner: Workflows; Tests: unit unsupported type error + integration supported
