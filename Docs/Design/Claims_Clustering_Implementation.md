# Claims Clustering Implementation Plan

## Goals
- Persist canonical clusters of similar claims.
- Provide cluster list, member, timeline, and evidence endpoints.
- Support watchlist subscriptions for clusters.

## Data Model
- `ClaimClusters`:
  - `id` (PK), `user_id`, `canonical_claim_text`, `representative_claim_id`,
    `summary`, `cluster_version`, `created_at`, `updated_at`, `watchlist_count`.
- `ClaimClusterMembership`:
  - `cluster_id`, `claim_id`, `similarity_score`, `cluster_joined_at`.
- `ClaimClusterLinks` (optional v1):
  - `parent_cluster_id`, `child_cluster_id`, `relation_type`, `created_at`.
- Claims table additions:
  - `claim_cluster_id` (INTEGER, nullable)
- `representative_claim_id` selection:
  - Default to the earliest `created_at` claim in the cluster; tie-break on lowest `claim_id`.
  - `claims.admin` may override via a manual update endpoint; override must reference a
    member claim in the same cluster and increments `cluster_version`.
  - Invariant: `representative_claim_id` always belongs to `ClaimClusterMembership`.
- `watchlist_count` maintenance:
  - Application-level transactional updates on watchlist add/remove for clusters.
  - On write failure, rollback the subscription change and leave `watchlist_count` unchanged.
  - Invariant: `watchlist_count >= 0` and equals the number of active subscriptions.
- `claim_cluster_id` backfill/migration:
  - Run a one-time batch clustering job that assigns `claim_cluster_id` for existing claims,
    recording progress (last processed claim ID + retry count) in job state.
  - Failures are retried with exponential backoff; skip hard failures after N retries and log
    for manual review.
  - New claims are assigned in real-time on ingestion; invariant: claims without a cluster
    are only allowed when clustering is disabled or a backfill failure is recorded.

## Clustering Baseline
- Start with a conservative baseline:
  - If claim embeddings exist, assign by cosine similarity threshold >= 0.85
    (configurable per deployment).
  - Fallback to normalized exact-text clustering (hash key).
- Maintain a simple `cluster_version` counter incremented on membership changes.
- On single claim insertion, perform lightweight assignment only (no full
  recluster). Increment `cluster_version` when membership changes.
- On rebuild/bulk import, enqueue a full recluster for the affected media/time
  range; full recluster runs nightly at 02:00 local time for drift detection.
- Manual/on-demand rebuilds run full reorganization and reset `cluster_version`
  as needed for rewritten clusters.
- Trade-offs: higher thresholds reduce false positives but may split related
  claims; lower thresholds increase recall but risk noisy clusters. Nightly
  reclusters improve global consistency at higher compute cost; incremental
  assignment minimizes latency. Schedules and thresholds are configurable per
  deployment.

## API Surface
- `GET /api/v1/claims/clusters`
  - Query: `page`, `per_page` (default 20), `sort_by` (`created_at|watchlist_count`),
    `order` (`asc|desc`), `query` (optional text search).
  - Response: `{ clusters: [...], total: int, page: int }`.
- `GET /api/v1/claims/clusters/{cluster_id}`
  - Response: `{ id, user_id, canonical_claim_text, representative_claim_id, summary,
    cluster_version, created_at, updated_at, member_count, watchlist_count }`.
- `GET /api/v1/claims/clusters/{cluster_id}/members`
  - Query: `page`, `per_page` (default 20).
  - Response: `{ members: [...], total: int }`.
- `GET /api/v1/claims/clusters/{cluster_id}/timeline`
  - Response: `{ events: [...], total: int }`.
- `GET /api/v1/claims/clusters/{cluster_id}/evidence`
  - Response: `{ sources: [...], verdicts: [...], flagged_claims: [...] }`.
- `POST /api/v1/watchlists/{watchlist_id}/clusters`
  - Body: `{ cluster_id }`.
  - Response: `{ success: bool, message: string }`.
- `DELETE /api/v1/watchlists/{watchlist_id}/clusters`
  - Query: `cluster_id`.
  - Response: `{ success: bool, message: string }`.

## Access Control
- `claims.reviewer` permission for cluster read APIs.
- `claims.admin` permission for cluster maintenance or manual adjustments.

## Testing
- Unit tests for membership insert/update.
- API tests for cluster list and member pagination.

## Database Indexes
- `ClaimClusterMembership(cluster_id, created_at)` for member pagination.
- `ClaimClusterMembership(claim_id)` for reverse lookup.
- `Claims(claim_cluster_id)` for bulk operations/stats.
- `ClaimClusters(user_id, created_at)` for user-scoped listings.

## Data Integrity & Cleanup
- **Claim deletion**: soft-delete claims (`deleted_at`) and mark membership as orphaned
  (retain rows for audit).
- **Cluster orphaning**: if all non-orphaned claims are deleted, soft-delete cluster
  (`deleted_at`) instead of hard-delete.
- **Foreign keys**: use `ON DELETE SET NULL` on `Claims.claim_cluster_id`; application
  code handles cascading soft-delete and watchlist_count adjustments.
