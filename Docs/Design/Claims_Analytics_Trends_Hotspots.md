# Claims Analytics Trends + Hotspots

## Overview
Extend the claims analytics dashboard payload with:
- Review status trend series (daily counts by `new_status` in `claims_review_log`).
- Cluster hotspots (clusters with flagged/rejected claims, sorted by issue volume).

This design is additive to existing analytics endpoints; no new tables are required.

## Data Sources
- `claims_review_log`: source of daily review status transitions.
- `Claims`: current review statuses and cluster assignments.
- `claim_clusters`: cluster metadata (canonical text, watchlist_count, timestamps).
- `claim_cluster_membership`: member counts per cluster.

## API Surface
- `GET /api/v1/claims/analytics/dashboard`
  - Adds:
    - `review_status_trends`
    - `clusters.hotspots`

### Query Parameters
- `window_days` (integer, optional, default: 7): number of days to include in trends analysis.

## Response Shape (Additions)
```json
{
  "review_status_trends": {
    "window_days": 7,
    "daily": [
      { "date": "2025-01-01", "total": 12, "status_counts": { "approved": 8, "flagged": 2, "rejected": 2 } }
    ]
  },
  "clusters": {
    "hotspots": [
      {
        "cluster_id": 42,
        "member_count": 10,
        "issue_count": 4,
        "issue_ratio": 0.4,
        "watchlist_count": 1,
        "canonical_claim_text": "Example claim",
        "updated_at": "2025-01-01T00:00:00Z"
      }
    ]
  }
}
```

### Hotspots Pagination / Overflow
- The hotspots list is fixed to the top 20 results; pagination is not supported.
- No `limit`, `offset`, or `page` parameters are accepted for hotspots.
- The response does not include `total_count`, `limit`, `offset`, or `has_more`.
- If more than 20 hotspots exist, results are truncated by the stated sort order.

Example request (default window):
- `GET /api/v1/claims/analytics/dashboard` (omits `window_days`, defaults to 7)

## Query Semantics
- Response behavior (empty/degenerate cases):
  - Always include `review_status_trends` and `clusters.hotspots` keys.
  - If no rows match, return empty arrays (`review_status_trends.daily = []`, `clusters.hotspots = []`) and keep `window_days` as requested/default.
  - Do not omit keys; prefer zero-safe values or placeholders over nulls.
- Review status trends:
  - Window: `window_days` from the request query parameter; if omitted, default to 7.
  - Source: `claims_review_log`.
  - Groups by `DATE(created_at)` and `new_status`.
  - Daily total = sum of status counts for that day.
- Cluster hotspots:
  - Cluster members from `claim_cluster_membership`.
  - Issue counts from `Claims` with `review_status IN ('flagged', 'rejected')`.
  - Filters out clusters with `issue_count = 0`.
  - issue_ratio: calculated as issue_count / member_count; when member_count is 0, issue_ratio is defined as 0 (clusters with zero members are retained but show a 0 ratio).
  - member_count: treat missing/null as 0.
  - canonical_claim_text: if missing/empty, surface a placeholder like "Unknown claim" (do not drop the cluster).
  - Sort: `issue_count DESC`, then `member_count DESC`.
  - Limit: 20 (fixed; no pagination or overflow metadata).

## Indexes and Performance
- Recommended indexes (SQLite/Postgres):
  - `claims_review_log(created_at, new_status)` to support windowed grouping; optional partial index on recent ranges if supported.
  - `claim_cluster_membership(cluster_id)` for member counts; optional UNIQUE on `(cluster_id, claim_id)` to prevent duplicate memberships.
  - `Claims(review_status, cluster_id)` for flagged/rejected filtering and aggregation; optional partial index where `review_status IN ('flagged', 'rejected')`.
- Migration/perf note:
  - Add these indexes when dashboard queries grow beyond acceptable latency or show full scans in query plans.
  - Expected plans: range scan on `claims_review_log` by `created_at`, index scan on `Claims` by `review_status` + `cluster_id`, index scan on `claim_cluster_membership` for group counts.
  - Keep the hotspot limit fixed (20); if pagination is added later, cap maximum limits and avoid large OFFSET scans (prefer keyset pagination or precomputed rollups).

## Notes
- No required schema migrations for functionality; optional indexes above are recommended for performance.
- Additive fields preserve backward compatibility for existing clients.
