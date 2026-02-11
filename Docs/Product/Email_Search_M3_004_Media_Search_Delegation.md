# Email Search M3-004 `/media/search` Delegation Strategy

Last Updated: 2026-02-10  
Owner: Backend and Search Team  
Related PRD: `Docs/Product/Email_Ingestion_Search_PRD.md`

## Scope

Finalize the compatibility behavior for `POST /api/v1/media/search` when email-native operator search is available.

Goals:

1. Preserve legacy behavior by default.
2. Provide an explicit cutover switch for email-only search traffic.
3. Keep unchanged response shape and avoid client-breaking behavior.

## Delegation Inputs

Delegation decision uses:

1. Request parameter `email_query_mode` (`operators`, `legacy`, or omitted).
2. Request `media_types` scope.
3. Feature flags:
   - `EMAIL_OPERATOR_SEARCH_ENABLED`
   - `EMAIL_MEDIA_SEARCH_DELEGATION_MODE` (`opt_in` or `auto_email`)

## Final Behavior Contract

Precedence order:

1. `email_query_mode=operators`
   - Requires `media_types=['email']`.
   - Returns 422 if `EMAIL_OPERATOR_SEARCH_ENABLED=false`.
   - Delegates to normalized email planner.
2. `email_query_mode=legacy`
   - Always uses legacy media search path.
3. `email_query_mode` omitted
   - `EMAIL_MEDIA_SEARCH_DELEGATION_MODE=opt_in` (default): legacy path.
   - `EMAIL_MEDIA_SEARCH_DELEGATION_MODE=auto_email`: auto-delegate when `media_types=['email']` and `EMAIL_OPERATOR_SEARCH_ENABLED=true`.
   - If auto mode is enabled but operator search is disabled, fallback remains legacy (no breaking error for implicit mode).

## Compatibility Notes

1. Response envelope from `/api/v1/media/search` is unchanged.
2. Existing clients that do not set `email_query_mode` continue to work with default `opt_in`.
3. Operators can cut over email-only traffic by setting `EMAIL_MEDIA_SEARCH_DELEGATION_MODE=auto_email` without requiring client changes.
4. Clients can still force old behavior with `email_query_mode=legacy` during or after cutover.

## Validation Coverage

Integration tests:

1. `tldw_Server_API/tests/MediaIngestion_NEW/integration/test_media_search_request_model.py::test_media_search_email_scope_defaults_to_legacy_planner`
2. `tldw_Server_API/tests/MediaIngestion_NEW/integration/test_media_search_request_model.py::test_media_search_auto_email_delegation_uses_email_planner`
3. `tldw_Server_API/tests/MediaIngestion_NEW/integration/test_media_search_request_model.py::test_media_search_auto_email_delegation_honors_explicit_legacy_mode`
4. `tldw_Server_API/tests/MediaIngestion_NEW/integration/test_media_search_request_model.py::test_media_search_auto_email_delegation_falls_back_when_operator_disabled`

