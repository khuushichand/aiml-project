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

## Query Semantics
- Review status trends:
  - Window: `window_days` (same window as review throughput).
  - Source: `claims_review_log`.
  - Groups by `DATE(created_at)` and `new_status`.
  - Daily total = sum of status counts for that day.
- Cluster hotspots:
  - Cluster members from `claim_cluster_membership`.
  - Issue counts from `Claims` with `review_status IN ('flagged', 'rejected')`.
  - Filters out clusters with `issue_count = 0`.
  - Sort: `issue_count DESC`, then `member_count DESC`.
  - Limit: 20.

## Notes
- No schema migrations required.
- Additive fields preserve backward compatibility for existing clients.
