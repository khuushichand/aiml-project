# Privilege Maps Mock API Responses

The following fixtures mirror the contracts defined in the Privilege Maps PRD and can be used by the WebUI team to prototype dashboard components and pagination behaviour.

## Organization Summary (grouped by role)

```json
{
  "catalog_version": "1.0.0",
  "generated_at": "2025-01-15T10:12:03Z",
  "group_by": "role",
  "buckets": [
    {"key": "admin", "users": 12, "endpoints": 145, "scopes": 83},
    {"key": "analyst", "users": 48, "endpoints": 97, "scopes": 52},
    {"key": "viewer", "users": 160, "endpoints": 45, "scopes": 28}
  ],
  "metadata": {
    "org_id": "acme",
    "filters": {"include_trends": false, "since": null}
  }
}
```

## Organization Summary (grouped by resource category with trends)

```json
{
  "catalog_version": "1.0.0",
  "generated_at": "2025-01-15T10:12:03Z",
  "group_by": "resource",
  "buckets": [
    {
      "key": "media",
      "users": 188,
      "endpoints": 112,
      "scopes": 64,
      "trend": {"delta": 5, "direction": "up"}
    },
    {
      "key": "chat",
      "users": 205,
      "endpoints": 76,
      "scopes": 41,
      "trend": {"delta": -2, "direction": "down"}
    },
    {
      "key": "rag",
      "users": 97,
      "endpoints": 58,
      "scopes": 34,
      "trend": {"delta": 0, "direction": "flat"}
    }
  ],
  "metadata": {
    "org_id": "acme",
    "filters": {"include_trends": true, "since": "2025-01-01T00:00:00Z"}
  }
}
```

## Drill-Down Detail (page 1)

```json
{
  "catalog_version": "1.0.0",
  "generated_at": "2025-01-15T10:12:03Z",
  "page": 1,
  "page_size": 100,
  "total_items": 2350,
  "items": [
    {
      "user_id": "user-123",
      "user_name": "Alex Rivera",
      "role": "admin",
      "endpoint": "/api/v1/media/process",
      "method": "POST",
      "privilege_scope_id": "media.ingest",
      "feature_flag_id": "media_ingest_beta",
      "sensitivity_tier": "high",
      "ownership_predicates": ["same_org"],
      "status": "allowed"
    },
    {
      "user_id": "user-123",
      "user_name": "Alex Rivera",
      "role": "admin",
      "endpoint": "/api/v1/chat/completions",
      "method": "POST",
      "privilege_scope_id": "chat.admin",
      "feature_flag_id": null,
      "sensitivity_tier": "restricted",
      "ownership_predicates": ["same_org"],
      "status": "allowed"
    },
    {
      "user_id": "user-456",
      "user_name": "Priya Patel",
      "role": "analyst",
      "endpoint": "/api/v1/rag/search",
      "method": "POST",
      "privilege_scope_id": "rag.search",
      "feature_flag_id": null,
      "sensitivity_tier": "moderate",
      "ownership_predicates": ["same_team"],
      "status": "allowed"
    }
  ],
  "filters": {
    "resource": null,
    "role": null
  }
}
```

## Drill-Down Detail (page 2 with filters)

```json
{
  "catalog_version": "1.0.0",
  "generated_at": "2025-01-15T10:12:03Z",
  "page": 2,
  "page_size": 100,
  "total_items": 310,
  "items": [
    {
      "user_id": "user-789",
      "user_name": "Morgan Lee",
      "role": "viewer",
      "endpoint": "/api/v1/media/catalog",
      "method": "GET",
      "privilege_scope_id": "media.catalog.view",
      "feature_flag_id": null,
      "sensitivity_tier": "low",
      "ownership_predicates": ["same_org"],
      "status": "allowed"
    },
    {
      "user_id": "user-789",
      "user_name": "Morgan Lee",
      "role": "viewer",
      "endpoint": "/api/v1/media/process",
      "method": "POST",
      "privilege_scope_id": "media.ingest",
      "feature_flag_id": "media_ingest_beta",
      "sensitivity_tier": "high",
      "ownership_predicates": ["same_org"],
      "status": "blocked",
      "blocked_reason": "missing_scope"
    }
  ],
  "filters": {
    "resource": "media",
    "role": "viewer"
  }
}
```

## Usage Notes

- `total_items` represents the total rows that match the current filters to guide pagination controls.
- Detail responses include blocked entries to surface actionable gaps (e.g., missing scopes, disabled feature flags).
- `blocked_reason` values should map to UI messaging (e.g., `missing_scope`, `feature_flag_disabled`, `ownership_violation`).
