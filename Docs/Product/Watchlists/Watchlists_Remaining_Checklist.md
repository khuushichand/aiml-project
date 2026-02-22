# Watchlists v1 - Remaining Checklist

Status: Reconciled (v1 wrap-up complete; optional roadmap items tracked in PRDs)

- [x] Add preview/dry-run endpoint: `POST /api/v1/watchlists/jobs/{job_id}/preview` (limit, per_source)
- [x] Extend OPML export tests (group OR + tag AND combos; multi-group; unknown group id)
- [x] Add admin org search edge-case tests (slug-only, numeric ID search)
- [x] Add pipeline e2e for include-only gating on site sources (RSS covered)
- [x] Migration tooling: CLI/import helper to map Subscriptions → Watchlists (jobs + filters) with dry-run (not required; superseded by OPML import + job filters)
- [x] Docs polish: migration playbook, OPML guidance (nested/duplicates), include-only semantics summary
- [x] Optional: Admin runs view polish (extra counters columns, richer CSV)
- [x] Optional: Rate-limit header deterministic tests under non-test mode

Notes
- YouTube policy: keep 400 for unsupported `@handle` and `/c/…` vanity forms; server normalizes channel/user/playlist and sets headers.
- Preview endpoint returns decision per item (ingest|filtered), matched action (include|exclude|flag|None), and filter key; no ingestion occurs.
- Migration note: Subscriptions never shipped to production; dedicated migration CLI is intentionally not required.
