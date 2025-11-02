# Vector Stores API - Admin and Query Filters

This document describes vector store administration endpoints and advanced query filters.

## Endpoints

- GET `/api/v1/vector_stores/{store_id}/vectors`
  - List vectors with pagination and optional filtering/sorting.
  - Query params:
    - `limit` (int, default 50)
    - `offset` (int, default 0)
    - `filter` (JSON-encoded object; see Filter Grammar)
    - `order_by` (`id` or `metadata.<key>`)
    - `order_dir` (`asc` or `desc`)

- GET `/api/v1/vector_stores/{store_id}/admin/index_info`
  - Returns backend index info.
  - For PG: `{ index_type: 'hnsw'|'ivfflat'|'none', ops, dimension, metric, ef_search }`
  - For Chroma: `{ backend: 'chroma', index_type: 'managed', dimension, count }`

- POST `/api/v1/vector_stores/admin/hnsw_ef_search`
  - Body: `{ "ef_search": 128 }`
  - Sets session-level HNSW `ef_search` for PG. No-op for Chroma.

- POST `/api/v1/vector_stores/{store_id}/admin/rebuild_index`
  - Body: `{ "index_type": "hnsw"|"ivfflat"|"drop", "metric": "cosine"|"euclidean"|"ip", "m": 16, "ef_construction": 200, "lists": 100 }`
  - Drops existing embedding index and creates requested type (or drops only).

## Filter Grammar

Filters are JSON objects applied against metadata. The adapter supports a simple grammar:

- Logical operators:
  - `$and`: list of subclauses
  - `$or`: list of subclauses
- Field operators:
  - `$eq` (or plain value)
  - `$neq`
  - `$in` (array of values)
  - `$gt`, `$gte`, `$lt`, `$lte` (numeric comparisons)

Examples:

- Equality on a field
```json
{"genre": "sci-fi"}
```

- Numeric comparison
```json
{"score": {"$gte": 0.8}}
```

- IN list
```json
{"tag": {"$in": ["a", "b", "c"]}}
```

- AND
```json
{"$and": [ {"genre": "sci-fi"}, {"score": {"$gte": 0.8}} ]}
```

- OR
```json
{"$or": [ {"author": "alice"}, {"author": "bob"} ]}
```

Ordering:
- `order_by=id` sorts by vector id.
- `order_by=metadata.<key>` sorts lexicographically by the metadata field.
- `order_dir=asc|desc` controls direction.

Notes:
- PG backend compiles filters into SQL (`metadata @> ...` plus basic operators).
- Chroma backend forwards simple `where` filters where supported; advanced operators fall back to basic semantics or client-side processing.
