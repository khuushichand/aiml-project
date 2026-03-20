# Resource Requirements

Hardware and storage guidelines for deploying tldw_server at various scales.

## Compute Tiers

### Minimum (API + SQLite, no transcription)

| Resource | Requirement |
|----------|------------|
| CPU      | 2 cores    |
| RAM      | 4 GB       |
| Disk     | 10 GB      |
| GPU      | None       |

Suitable for single-user deployments with cloud LLM providers and pre-transcribed content.

### Recommended (Multi-user, moderate load)

| Resource | Requirement |
|----------|------------|
| CPU      | 4 cores    |
| RAM      | 8 GB       |
| Disk     | 50 GB      |
| GPU      | None       |

Handles several concurrent users, background ingestion, and ChromaDB vector search with small-to-medium collections.

### With Local Transcription

| Resource | Requirement             |
|----------|------------------------|
| CPU      | 4+ cores               |
| RAM      | 16 GB                  |
| Disk     | 50 GB                  |
| GPU      | Recommended (CUDA)     |

faster-whisper and NeMo (Parakeet/Canary) benefit significantly from GPU acceleration. Without a GPU, transcription will work but may be 5-10x slower.

- **GPU VRAM**: 4 GB minimum (small model), 8 GB recommended (medium/large model).
- Models are downloaded on first use and cached under `~/.cache/huggingface/` or the configured model directory.

### With Vector Search at Scale

| Resource | Requirement |
|----------|------------|
| CPU      | 4+ cores   |
| RAM      | 8-16 GB    |
| Disk     | 100 GB+    |

ChromaDB keeps embeddings in memory-mapped files. RAM usage grows roughly linearly with collection size:

| Documents    | Approximate RAM |
|-------------|----------------|
| 10,000      | ~500 MB        |
| 100,000     | ~2 GB          |
| 1,000,000   | ~8 GB          |

## Storage Estimates

### Per-User Storage

| Data Type               | Estimate per 1,000 items |
|------------------------|-------------------------|
| Media metadata (SQLite) | ~5 MB                   |
| Full-text content       | ~50 MB                  |
| Chat history            | ~10 MB                  |
| Notes                   | ~5 MB                   |
| Vector embeddings       | ~100 MB                 |

### System-Wide Storage

| Component              | Estimate        |
|-----------------------|-----------------|
| AuthNZ database       | < 10 MB         |
| Evaluations database  | 10-100 MB       |
| Log files (7-day)     | 100 MB - 1 GB   |
| Transcription models  | 1-6 GB per model |
| Embedding models      | 100 MB - 1 GB   |

## Scaling Guidelines

### Vertical Scaling

The simplest approach. Increase CPU and RAM on a single server:

- **More concurrent users**: Add RAM (each active request uses ~50-200 MB depending on operation).
- **Faster transcription**: Add GPU or upgrade to a faster GPU.
- **Larger collections**: Add RAM for ChromaDB.

### Horizontal Scaling

For deployments beyond a single server:

1. **Database**: Migrate AuthNZ to PostgreSQL (`DATABASE_URL` env var). Media and Notes DBs remain per-user SQLite files on shared storage (NFS/EFS).
2. **Stateless API**: Run multiple FastAPI instances behind a load balancer. Ensure shared access to the database and media file directories.
3. **ChromaDB**: Run as a separate service (`chroma run --host 0.0.0.0`) and point all API instances to it.
4. **Background Workers**: Use the sidecar worker pattern (see `Docs/Deployment/Sidecar_Workers.md`) for transcription and ingestion tasks.

### Docker Resource Limits

Set container resource limits to prevent runaway processes:

```yaml
# docker-compose.yml
services:
  tldw-api:
    deploy:
      resources:
        limits:
          cpus: "4.0"
          memory: 8G
        reservations:
          cpus: "1.0"
          memory: 2G
```

## Monitoring Resource Usage

Use the pool metrics endpoint and system health checks to monitor:

- Database connection pool saturation
- Memory usage trends
- Disk space remaining
- GPU utilisation (if applicable, via `nvidia-smi`)

See `Docs/Deployment/Monitoring/` for alerting configuration.
