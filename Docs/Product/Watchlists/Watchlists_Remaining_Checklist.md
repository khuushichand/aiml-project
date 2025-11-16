# Watchlists v1 - Remaining Checklist

Status: Tracking final items for Bridge PRD wrap-up

- [x] Add preview/dry-run endpoint: `POST /api/v1/watchlists/jobs/{job_id}/preview` (limit, per_source)
- [ ] Extend OPML export tests (group OR + tag AND combos; multi-group; unknown group id)
- [ ] Add admin org search edge-case tests (slug-only, numeric ID search)
- [ ] Add pipeline e2e for include-only gating on site sources (RSS covered)
- [ ] Migration tooling: CLI/import helper to map Subscriptions → Watchlists (jobs + filters) with dry-run
- [ ] Docs polish: migration playbook, OPML guidance (nested/duplicates), include-only semantics summary
- [ ] Optional: Admin runs view polish (extra counters columns, richer CSV)
- [ ] Optional: Rate-limit header deterministic tests under non-test mode

Notes
- YouTube policy: keep 400 for unsupported `@handle` and `/c/…` vanity forms; server normalizes channel/user/playlist and sets headers.
- Preview endpoint returns decision per item (ingest|filtered), matched action (include|exclude|flag|None), and filter key; no ingestion occurs.
