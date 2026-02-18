# Characters Query Performance Monitoring Checklist (Stage 4)

## Purpose

Operational checklist for validating `/api/v1/characters/query` scalability rollout and ensuring fallback readiness.

## Rollout Guardrails

- `ff_characters_server_query=true` (default): use server-driven query endpoint in Characters Manager.
- `ff_characters_server_query=false`: fallback to legacy client-side list/filter/sort path.
- Keep rollback path documented in release notes before enabling for broad users.

## API Response Size Checks

1. Capture representative query payload sizes (small, medium, large workspaces):
   - `GET /api/v1/characters/query?page=1&page_size=25&include_image_base64=false`
   - `GET /api/v1/characters/query?page=1&page_size=100&sort_by=updated_at&sort_order=desc&include_image_base64=false`
2. Verify response body size targets:
   - P95 for `page_size=25`: <= `250 KB`
   - P95 for `page_size=100`: <= `600 KB`
3. Confirm `image_base64` is absent in list payloads unless explicitly requested.

## Query Latency Checks

1. Measure p95 latency by route and major filter combinations:
   - default list (no query/filter)
   - search query (`query=<term>`)
   - tags filter (`tags=a&tags=b`)
   - creator filter + date/sort combinations
2. Target budgets:
   - p95 query latency <= `250 ms` for `page_size=25`
   - p95 query latency <= `400 ms` for `page_size=100`
3. Validate no sustained regressions after deploy (30-minute rolling windows).

## Frontend Interaction Checks

1. Confirm first-page render remains responsive for 200+ total characters.
2. Confirm pagination, sort, and search all trigger `/api/v1/characters/query` requests.
3. Confirm search debounce behavior sends updated query parameters without duplicate request bursts.
4. Confirm avatar images are lazy-loaded (`loading="lazy"`) in table/gallery.

## Alerting Recommendations

- Add warning alert when p95 `/api/v1/characters/query` latency exceeds budget for 15m.
- Add warning alert when response size exceeds `600 KB` p95 for 15m.
- Add error alert when 5xx rate for `/api/v1/characters/query` exceeds 1% for 10m.

## Rollback Procedure

1. Set `ff_characters_server_query=false` for affected clients.
2. Verify Characters page still lists/searches/sorts/paginates using legacy path.
3. Keep monitoring enabled and capture incident diagnostics before re-enabling.
