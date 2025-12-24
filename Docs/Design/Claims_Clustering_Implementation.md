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

## Clustering Baseline
- Start with a conservative baseline:
  - If claim embeddings exist, assign by cosine similarity threshold.
  - Fallback to normalized exact-text clustering (hash key).
- Maintain a simple `cluster_version` counter incremented on membership changes.
- Recluster via background job triggered by claim insertion or rebuild events.

## API Surface
- `GET /api/v1/claims/clusters`
- `GET /api/v1/claims/clusters/{cluster_id}`
- `GET /api/v1/claims/clusters/{cluster_id}/members`
- `GET /api/v1/claims/clusters/{cluster_id}/timeline`
- `GET /api/v1/claims/clusters/{cluster_id}/evidence`
- `POST/DELETE /api/v1/watchlists/{watchlist_id}/clusters`

## Access Control
- `claims.reviewer` permission for cluster read APIs.
- `claims.admin` permission for cluster maintenance or manual adjustments.

## Testing
- Unit tests for membership insert/update.
- API tests for cluster list and member pagination.
