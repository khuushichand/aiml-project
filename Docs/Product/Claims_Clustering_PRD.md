# Claims Clustering & Deduplication PRD

## 1. Background
- The claims pipeline produces statement-level records tied to individual media chunks. Analysts often encounter duplicated or near-identical claims across different sources.
- Current search and UI flows display each claim independently, leading to:
  - Redundant review effort.
  - Difficulty seeing consensus or conflicting evidence across sources.
  - Limited ability to monitor recurring narratives over time.
- Clustering similar claims enables canonical references, streamlined reviews, and richer analytics (e.g., watchlists, alerting).

## 2. Problem Statement
Without claim clustering and deduplication:
- Analysts must manually compare claims across media to determine overlap.
- Watchlists cannot alert on recurring themes effectively.
- Evidence is fragmented, obscuring consensus or divergence.
- Historical tracking of claim evolution is cumbersome.

## 3. Goals & Success Criteria
1. Generate canonical claim clusters representing semantically similar statements.
2. Track cluster evolution over time to understand narrative shifts.
3. Integrate clusters with watchlists and notifications.
4. Aggregate supporting/refuting evidence per cluster for quick analysis.

**Success Metrics**
- ≥80% of new claims auto-assigned to an existing cluster (recall).
- Cluster precision validated via reviewer sampling (≤10% mis-clustered rate).
- Watchlist alerts generated for key topics with <5 min latency post-ingestion.
- Evidence aggregation reduces analyst comparison time by ≥30%.

## 4. Out of Scope (v1)
- Cross-language clustering (focus on English).
- Automatic fact-checking or truth scoring.
- Source credibility scoring beyond existing metadata.
- UI redesign beyond necessary components for clusters/watchlists.

## 5. Personas & Use Cases
- **Research Analyst**: Needs to view canonical claims with aggregated evidence, track narrative evolution.
- **Claims Reviewer**: Validates representative claim once instead of duplicates, sees cluster impact.
- **Watchlist Owner / Subject Matter Expert**: Subscribes to narratives (e.g., “vaccine efficacy”) for alerts.
- **Product Engineer**: Integrates cluster data into UI/search/export.
- **ML Engineer**: Maintains embedding models and clustering accuracy metrics.

## 6. Functional Requirements

### 6.1 Canonical Claim Graph
- Embedding-based clustering:
  - Use vector representations (existing embeddings or dedicated model) to cluster claims via incremental algorithm (e.g., hierarchical clustering with thresholds, approximate nearest neighbors).
  - Maintain cluster ID for each claim (`claim_cluster_id`).
  - Store cluster metadata (canonical text, representative claim, summary, size).
- Graph structure:
  - Build relationships between clusters and sources (media IDs, providers, extraction modes).
  - Support linking clusters that are related but not identical (parent-child relationships).
- Deduplication in UI/search:
  - Provide API flag to return canonical clusters with member claims collapsed.
  - List top representative claim per cluster alongside aggregated counts.
- Storage:
  - New tables: `ClaimClusters`, `ClaimClusterMembership`.
  - Support incremental updates as new claims arrive (online clustering).

### 6.2 Temporal Tracking & Versioning
- Track cluster timelines:
  - Record time series of claim additions/removals per cluster.
  - Maintain `cluster_version` when canonical text or membership threshold changes.
- Visualizations:
  - Provide timeline view showing claim volume per cluster over time.
  - Highlight spikes or narrative shifts (e.g., new evidence, change in sentiment).
- Integration with rebuild/refresh cycles to recalculate clusters periodically or on-demand.
- API endpoints:
  - `GET /api/v1/claims/clusters/{cluster_id}/timeline`.
  - `GET /api/v1/claims/clusters?since=<timestamp>` for delta updates.

### 6.3 Watchlist Integration
- Allow users to subscribe to clusters:
  - `POST /api/v1/watchlists/{watchlist_id}/clusters` to add cluster.
  - Option to auto-create watchlist from search query/cluster selection.
- Notifications:
  - Trigger when new claims join a subscribed cluster, or when external verification status changes (supported/refuted).
  - Provide summary payload with new sources, evidence counts.
- UI:
  - Watchlist page listing clusters, freshness indicators, quick link to evidence view.
- Manage thresholds:
  - Admin configurable min cluster size or significance before alerting.

### 6.4 Evidence Aggregation
- For each cluster, aggregate:
  - Supporting claims (aligned evidence).
  - Refuting claims (contradictory evidence).
  - NEI/unknown claims.
- Provide consensus metrics:
  - Support vs. refute ratios.
  - Confidence scores (avg, distribution).
  - Top sources contributing to each side.
- Surface aggregated evidence in API (`GET /api/v1/claims/clusters/{cluster_id}/evidence`) and UI:
  - Summaries, representative quotes, link to media.
  - Indicate reviewer status and notes per member claim.
- Consider integration with reviewer workflow (cluster-level approvals or flags).

### 6.5 Deduplication & Search Enhancements
- Extend `/api/v1/claims/search` with `group_by_cluster=true` option.
- Provide cluster facets (size, trending, watchlisted).
- Allow navigation to member claims when deeper inspection required.

### 6.6 Analytics & Reporting
- Metrics:
  - Number of clusters, average cluster size, orphan claims (not clustered).
  - Cluster formation rate, merge/split counts.
  - Watchlist alert rate per cluster category.
- Dashboards: overlay with provider, language, extraction mode; show top trending clusters.

## 7. Non-Functional Requirements
- **Performance**: Clustering should process new claims near real time (<1 minute) for actionable alerts.
- **Scalability**: Support tens of thousands of clusters, millions of claims.
- **Accuracy**: Provide manual override/resolution for mis-clustered claims.
- **Security**: Respect tenant boundaries; cluster IDs namespaced per workspace.
- **Maintainability**: Modular clustering service with configuration for thresholds, model selection.

## 8. Data Model Changes
- `ClaimClusters` table: `id`, `workspace_id`, `canonical_claim_text`, `representative_claim_id`, `created_at`, `updated_at`, `cluster_version`, `summary`, `watchlist_count`.
- `ClaimClusterMembership`: `cluster_id`, `claim_id`, `similarity_score`, `cluster_joined_at`.
- Optional `ClaimClusterLinks` for parent/child relationships.
- Update `Claims` table with `claim_cluster_id` (nullable).
- Watchlist extension: link `watchlist_id` with `cluster_id`.

## 9. Services & Components
- **Clustering Service**:
  - Ingests claim embeddings, performs clustering, updates membership.
  - Handles incremental updates and periodic rebalancing.
- **Cluster API**: Manage queries, membership lookup, timeline data.
- **Notification Service**: Integrate with watchlists for cluster alerts.
- **UI Extensions**: Search, watchlists, evidence views, timeline visualizations.

## 10. APIs (Draft)
| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/api/v1/claims/clusters` | GET | List clusters (filters: watchlisted, size, updated_since, keyword) | reviewer/analyst |
| `/api/v1/claims/clusters/{cluster_id}` | GET | Cluster details, canonical text, latest stats | reviewer/analyst |
| `/api/v1/claims/clusters/{cluster_id}/members` | GET | Paginated member claims | reviewer/analyst |
| `/api/v1/claims/clusters/{cluster_id}/timeline` | GET | Time series for cluster growth/changes | reviewer/analyst |
| `/api/v1/claims/clusters/{cluster_id}/evidence` | GET | Aggregated supporting/refuting evidence | reviewer/analyst |
| `/api/v1/watchlists/{watchlist_id}/clusters` | POST/DELETE | Subscribe/unsubscribe cluster | analyst/admin |

## 11. Algorithms & Thresholds
- Initial approach:
  - Use cosine similarity on normalized embeddings; threshold configurable (e.g., >0.85).
  - For large volumes, leverage approximate nearest neighbor index (e.g., FAISS, Annoy).
  - Merge small clusters into larger ones if average similarity within threshold.
  - Periodic reclustering to prevent drift.
- Provide manual override APIs to merge/split clusters if necessary.

## 12. Integrations & Dependencies
- Relies on existing embeddings pipeline; may require dedicated embedding model tuned for claim similarity.
- Interfaces with reviewer workflow for status aggregation.
- Hooks into monitoring/alerting for cluster-level metrics.
- Watchlist service must support cluster membership.

## 13. Risks & Mitigations
- **Mis-clustering**: Provide reviewer overrides, cluster audit, manual merge/split tools.
- **Performance**: Use incremental clustering with batching; monitor latency.
- **Storage growth**: Manage cluster history retention; consider summarizing older data.
- **Alert noise**: Provide thresholds, user-configurable watchlist sensitivity.

## 14. Implementation Roadmap
1. **Phase 1**: Baseline clustering engine, cluster storage, API to fetch clusters/members.
2. **Phase 2**: Temporal tracking, timeline endpoints, merge/split tools.
3. **Phase 3**: Watchlist integration, notifications, UI overlays.
4. **Phase 4**: Evidence aggregation dashboards, consensus metrics, advanced analytics.

## 15. Open Questions
- What is acceptable cluster size vs. granularity? Need user study.
- Should clusters be global or per workspace? Default per workspace.
- How to handle claims that span multiple languages or multiple tenant contexts?
- Should canonical claim text be auto-generated (e.g., summarization) or selected from member claims?
- How to manage cluster lifecycle (archival, deletion)?

## 16. References
- Claims Module PRD (`Docs/Product/Claims_Module_PRD.md`).
- Reviewer Workflow PRD (`Docs/Product/Claims_Reviewer_Workflow_PRD.md`).
- Monitoring PRD (`Docs/Product/Claims_Monitoring_PRD.md`).
- Embeddings infrastructure (`tldw_Server_API/app/core/Embeddings`).
