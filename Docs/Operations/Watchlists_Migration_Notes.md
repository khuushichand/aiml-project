# Watchlists Migration Notes

Status: Current guidance for moving legacy subscriptions-style workflows to Watchlists.

## Summary

- A dedicated migration CLI is not required.
- Use Watchlists source import/export and job filters for migration and reconciliation.
- Treat legacy "subscriptions" concepts as Watchlists sources and scheduled jobs.

## Recommended Migration Path

1. Export source lists from the legacy environment to OPML where possible.
2. Import sources with `POST /api/v1/watchlists/sources/import`.
3. Re-create inclusion/exclusion behavior with Watchlists job filters.
4. Validate results in Watchlists runs history and item views before cutover.

## Notes

- YouTube source URLs follow the Watchlists normalization and validation rules documented in the Watchlists product docs and API docs.
- For environments with no prior subscriptions data, start directly with Watchlists sources + filters.

## Related References

- `Docs/API-related/Watchlists_API.md`
- `Docs/Product/Watchlists/Watchlist_PRD.md`
- `Docs/Product/Watchlists/Watchlists_Subscriptions_Bridge_PRD.md`
- `Docs/Product/Watchlists/Watchlists_Outstanding_Work_Reconciled_2026-02-07.md`
