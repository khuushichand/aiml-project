---
title: WebUI - Vector Backends
---

# WebUI - Vector Backends

The Vector Stores tab in the WebUI works with multiple backends:

- ChromaDB (default)
- pgvector (PostgreSQL extension)

This page shows how to identify which backend is active and where to change tuning options. It also provides quick visual cues to help operators verify configuration.

## Backend Badge (Index Info)

- In the Vector Stores panel, enter a store ID and click “Index Info”.
- The badge shows the index type and backend reported by the server. Examples:
  - index: hnsw • backend: pgvector (ops: vector_cosine_ops)
  - index: managed • backend: chroma

Screenshots

Note: Screenshot files are not bundled to keep the repo lean. See the "Capturing Screenshots" section below for filenames and add them under `Docs/Published/assets/` if you want images to render in your local build.

## ef_search (pgvector only)

- The Admin section exposes an ef_search control. This applies only to pgvector; on Chroma it’s accepted but effectively a no-op.
- To adjust ef_search:
  1) Enter a value (e.g., 128)
  2) Click “Set ef_search”
  3) Click “Index Info” again to confirm the session value (pgvector)

Screenshot

Note: The ef_search control screenshot is optional and not included by default. To add it locally, save the image under `Docs/Published/assets/vector_backends_ef_search.png` as described below.

Tips

- Higher ef_search generally improves recall at the cost of latency.
- For large collections, consider rebuilding the index via “Rebuild Index” and then running ANALYZE.

## Switching Backends

- The active backend is configured in `config.txt` under the `[RAG]` section:

```
[RAG]
vector_store_type = pgvector               # or chromadb
pgvector_host = localhost
pgvector_port = 5432
pgvector_database = tldw_content
pgvector_user = tldw_user
pgvector_password = <your_password>
pgvector_sslmode = prefer
pgvector_pool_min_size = 1
pgvector_pool_max_size = 5
pgvector_hnsw_ef_search = 64
```

Notes

- Server reads pgvector settings from `config.txt`. Environment variables don’t override these for normal operation. Tests/scripts may still use env DSNs.
- After changing backends, restart the server so the WebUI picks up the new configuration.

## Capturing Screenshots (Operators/Docs Maintainers)

This project ships without screenshots to keep the repo lean. Use the steps below to capture consistent images and save them under `Docs/Published/assets/` with the exact filenames referenced above.

Prerequisites

- API + WebUI running (e.g., `uvicorn ... --reload`)
- Admin privileges (single-user mode or admin token)
- Vector backends configured as needed in `config.txt`

1) Backend Badge - pgvector

- Ensure `[RAG] vector_store_type = pgvector` in `config.txt`; restart the server.
- In WebUI → Vector Stores → Create Vector Store, create a small store (e.g., 8 dimensions).
- Enter the new Store ID under Admin → Store ID, click “Index Info”.
- Crop the badge area that shows: `index: hnsw • backend: pgvector (ops: ...)`.
- Save as `Docs/Published/assets/vector_backends_badge_pgvector.png`.

2) Backend Badge - Chroma

- Set `vector_store_type = chromadb` in `config.txt`; restart.
- Create a store as above; click “Index Info”.
- Crop the badge showing: `index: managed • backend: chroma`.
- Save as `Docs/Published/assets/vector_backends_badge_chroma.png`.

3) ef_search Control - pgvector only

- With pgvector active, in Admin set `ef_search` (e.g., 128) and click “Set ef_search”.
- Click “Index Info” again to confirm the session value.
- Capture the ef_search input + the confirmation context (index info panel or badge).
- Save as `Docs/Published/assets/vector_backends_ef_search.png`.

Recommendations

- Redact or avoid sensitive values (DSNs, user IDs). Use demo store names/IDs.
- Use a consistent theme (light or dark) across screenshots for uniformity.
- Keep images narrow (≈ 800-1200px width) and crop tightly around the relevant UI.
- Rebuild docs locally with `mkdocs serve` to verify images render.
