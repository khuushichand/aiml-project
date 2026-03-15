# Admin Operations Runbook

Quick-reference guide for operating a tldw_server deployment.

---

## Daily Operations

### Health Checks

```bash
# API health
curl -sf http://localhost:8000/api/v1/health | jq .

# Prometheus metrics (if enabled)
curl -sf http://localhost:8000/metrics | head -20

# Check disk usage on database directory
du -sh Databases/
```

### Monitoring Review

If Grafana is deployed, review these dashboards daily:

- **tldw - Overview**: Check for elevated error rates or latency spikes
- **tldw - API Performance**: Identify slow endpoints
- **tldw - Resource Governor**: Watch for denial rate increases

Key alerts to watch:
- 5xx error rate > 1/s sustained for 5 minutes
- p95 latency > 5s
- Memory usage > 80% of available RAM
- Resource Governor denial rate climbing

---

## User Management

### Create a User (multi-user mode)

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "newuser", "email": "user@example.com", "password": "securepass"}'
```

### Reset a User Password

Use the admin API or direct database access:

```bash
# Via API (as admin)
curl -X POST http://localhost:8000/api/v1/auth/admin/reset-password \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 123, "new_password": "newSecurePass"}'
```

### Manage Roles

```bash
# Assign role
curl -X POST http://localhost:8000/api/v1/auth/admin/assign-role \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 123, "role": "editor"}'
```

### Disable a User

```bash
curl -X POST http://localhost:8000/api/v1/auth/admin/disable-user \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"user_id": 123}'
```

---

## Backup Operations

### Manual Backup

```bash
# Stop writes (optional but safest)
# SQLite databases support hot backup via .backup command

# Backup all databases
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Core databases
sqlite3 Databases/users.db ".backup '$BACKUP_DIR/users.db'"
sqlite3 Databases/evaluations.db ".backup '$BACKUP_DIR/evaluations.db'"

# Per-user databases
for db in Databases/user_databases/*/; do
  user_id=$(basename "$db")
  mkdir -p "$BACKUP_DIR/user_databases/$user_id"
  for f in "$db"*.db; do
    [ -f "$f" ] && sqlite3 "$f" ".backup '$BACKUP_DIR/user_databases/$user_id/$(basename $f)'"
  done
done

# ChromaDB (file-based)
cp -r Databases/chromadb "$BACKUP_DIR/chromadb" 2>/dev/null || true

echo "Backup complete: $BACKUP_DIR"
```

### Scheduled Backups

Add to crontab:
```bash
# Daily at 2 AM
0 2 * * * /path/to/tldw_server2/Helper_Scripts/backup.sh >> /var/log/tldw-backup.log 2>&1
```

### Restore from Backup

```bash
# Stop the server first
# Replace databases with backup copies
cp backups/20260314_020000/users.db Databases/users.db
# Repeat for each database file
# Restart the server
```

---

## Troubleshooting

### Database Locked

**Symptoms:** HTTP 500 errors, "database is locked" in logs.

**Fix:**
1. Check for long-running queries: `sqlite3 Databases/users.db ".timeout 5000"`
2. Ensure WAL mode is enabled: `sqlite3 Databases/users.db "PRAGMA journal_mode;"`
   - Should return `wal`. If not: `sqlite3 Databases/users.db "PRAGMA journal_mode=WAL;"`
3. Check for zombie processes holding locks: `fuser Databases/*.db`
4. As last resort, restart the server

### Transcription Failures

**Symptoms:** Audio/video processing returns errors.

**Fix:**
1. Verify ffmpeg: `ffmpeg -version`
2. Check available disk space (transcription uses temp files)
3. For CUDA errors: verify GPU drivers and CUDA toolkit
4. Check model files exist (faster_whisper models download on first use)
5. Test with a small file: `curl -X POST .../api/v1/audio/transcriptions -F file=@test.wav`

### API Key / Auth Errors

**Symptoms:** 401 or 403 responses.

**Fix:**
1. Confirm `AUTH_MODE` in `.env` matches your usage
2. Single-user: check `SINGLE_USER_API_KEY` matches the header value
3. Multi-user: verify JWT token is not expired; re-authenticate
4. Check logs for specific auth error messages

### Memory Issues

**Symptoms:** OOM kills, increasing memory usage, slow responses.

**Fix:**
1. Check process memory: `ps aux | grep uvicorn`
2. Reduce worker count in uvicorn: `--workers 1`
3. For embedding operations, reduce batch size in config
4. If using local STT models, consider offloading to a separate worker
5. Monitor with: `watch -n5 'ps -o rss,vsz,comm -p $(pgrep -f uvicorn)'`

### ChromaDB Issues

**Symptoms:** Embedding search returns empty or errors.

**Fix:**
1. Check ChromaDB directory permissions
2. Verify embedding model is available
3. Rebuild index if corrupted: delete and re-embed (see RAG docs)

---

## Emergency Procedures

### Service Restart

```bash
# Graceful restart (Docker)
docker compose restart tldw-api

# Graceful restart (systemd)
sudo systemctl restart tldw-api

# Graceful restart (manual)
kill -TERM $(pgrep -f "uvicorn.*tldw")
sleep 2
python -m uvicorn tldw_Server_API.app.main:app --host 0.0.0.0 --port 8000 &
```

### Database Corruption Recovery

1. **Stop the server immediately**
2. **Check integrity:**
   ```bash
   sqlite3 Databases/users.db "PRAGMA integrity_check;"
   ```
3. **If corrupt, restore from backup:**
   ```bash
   cp backups/latest/users.db Databases/users.db
   ```
4. **If no backup, attempt recovery:**
   ```bash
   sqlite3 Databases/users.db ".dump" | sqlite3 Databases/users_recovered.db
   mv Databases/users_recovered.db Databases/users.db
   ```
5. **Restart and verify**

### Emergency Maintenance Mode

To stop accepting new requests while finishing in-flight work:

```bash
# Docker: scale to 0, let load balancer drain
docker compose scale tldw-api=0

# Direct: send SIGTERM and wait for graceful shutdown
kill -TERM $(pgrep -f "uvicorn.*tldw")
# uvicorn will finish active requests before exiting (default 30s timeout)
```

For immediate shutdown (data loss risk for in-flight requests):
```bash
kill -9 $(pgrep -f "uvicorn.*tldw")
```

---

## Scaling

### When to Scale

- Sustained CPU > 80% across workers
- p95 latency > 2s for simple endpoints
- Resource Governor denial rate increasing
- Queue depth (if applicable) growing over time

### Single Instance Scaling

1. **Add workers:** `uvicorn ... --workers 4` (CPU-count guideline)
2. **Increase memory:** Embedding and STT models benefit from more RAM
3. **Move to PostgreSQL** for AuthNZ under concurrent load
4. **Separate ChromaDB** to its own host if vector search is bottleneck

### Multi-Instance Scaling

1. Deploy behind a load balancer (nginx, Caddy, or cloud LB)
2. Switch AuthNZ to PostgreSQL (shared across instances)
3. Use shared storage or object store for user databases
4. Configure session affinity if using WebSocket features
5. See `Docs/Deployment/horizontal-scaling.md` for full details

---

## Upgrades

### Standard Upgrade Process

```bash
# 1. Backup first
./Helper_Scripts/backup.sh

# 2. Pull latest code
git pull origin main

# 3. Update dependencies
pip install -e .

# 4. Run migrations (if any)
# Check RELEASE_NOTES.md for migration steps

# 5. Restart
sudo systemctl restart tldw-api
# or: docker compose up -d --build
```

### Rollback

```bash
# Revert to previous version
git checkout <previous-tag-or-commit>
pip install -e .

# Restore databases if schema changed
cp backups/pre-upgrade/users.db Databases/users.db

# Restart
sudo systemctl restart tldw-api
```

See `Helper_Scripts/` for any available upgrade automation scripts.
