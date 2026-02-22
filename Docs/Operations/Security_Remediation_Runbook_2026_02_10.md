# Security Remediation Runbook (2026-02-10)

This runbook documents security hardening changes shipped for review findings remediation.

## Scope

- API key exposure hardening in config/docs endpoints and startup logs.
- Scheduler external payload deserialization hardening.
- Web scraping dedupe persistence hardening.
- Loguru placeholder formatting normalization.
- Placeholder service runtime isolation.

## Secure Defaults Introduced

1. `GET /api/v1/config/docs-info` no longer returns real API key values.
2. Startup API key logging is masked by default unless `SHOW_API_KEY_ON_STARTUP=true`.
3. Scheduler external payload files now use JSON by default.
4. Scheduler payload reference validation now rejects malformed/non-conforming refs.
5. Scheduler legacy pickle payload load/store is disabled by default.
6. Web scraper dedupe hashes now persist to JSON (`content_hashes.json`) by default.
7. Web scraper legacy pickle dedupe loading is disabled by default.
8. Placeholder processing services are blocked in production-like environments even when enabled.

## Compatibility Flags

### Scheduler legacy payload compatibility

- Flag: `SCHEDULER_ALLOW_LEGACY_PICKLE_PAYLOADS`
- Default: `false`
- Purpose: Temporarily allow loading legacy externally stored pickle payload artifacts.

### Web scraper dedupe legacy compatibility

- Flag: `WEBSCRAPER_ALLOW_LEGACY_PICKLE_HASHES`
- Default: `false`
- Purpose: One-time migration of legacy `content_hashes.pkl` data into JSON storage.

### Placeholder service toggle

- Flag: `PLACEHOLDER_SERVICES_ENABLED`
- Default: `false`
- Guardrail: placeholder services remain blocked when environment is production-like (`APP_ENV=production`, `ENVIRONMENT=production`, etc.).

## Upgrade/Migration Steps

1. Deploy with all compatibility flags unset.
2. If scheduler payload load failures reference legacy pickle format:
   - set `SCHEDULER_ALLOW_LEGACY_PICKLE_PAYLOADS=true` temporarily,
   - drain/consume old payloads,
   - unset the flag.
3. If web dedupe state exists only as `content_hashes.pkl`:
   - set `WEBSCRAPER_ALLOW_LEGACY_PICKLE_HASHES=true` temporarily,
   - start service once to migrate to JSON,
   - unset the flag.
4. Keep `PLACEHOLDER_SERVICES_ENABLED` unset/false in all production deployments.

## Validation Checklist

1. Confirm `/api/v1/config/docs-info` reports placeholder key only.
2. Confirm startup logs do not print full API keys.
3. Confirm no Loguru `%`-placeholder usage remains in `tldw_Server_API/app`.
4. Confirm placeholder services are not bound to active API routes.
5. Confirm scheduler/web-scraper regression tests pass.
