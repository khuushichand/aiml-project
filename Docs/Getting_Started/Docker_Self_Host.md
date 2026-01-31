# Docker Self-Hosting Guide

This guide covers running tldw_server on your home server or VPS using Docker Compose.

**Time to complete:** 15-20 minutes (single-user) | 30-45 minutes (multi-user with HTTPS)

**Prerequisite:** Docker and Docker Compose installed ([Get Docker](https://docs.docker.com/get-docker/))

## What You'll Have at the End

- tldw_server running persistently on your server
- Data stored in Docker volumes (survives restarts)
- Optional: HTTPS with automatic certificate renewal

---

## Quick Start (Single-User)

The fastest way to get a persistent tldw_server running:

```bash
# Clone the repository
git clone https://github.com/rmusser01/tldw_server.git
cd tldw_server

# Create .env with your API key
cat > .env << 'EOF'
AUTH_MODE=single_user
SINGLE_USER_API_KEY=your-secure-api-key-at-least-16-chars
DATABASE_URL=sqlite:///./Databases/users.db
EOF

# Start the stack
docker compose -f Dockerfiles/docker-compose.yml up -d --build

# Initialize authentication
docker compose -f Dockerfiles/docker-compose.yml exec app \
  python -m tldw_Server_API.app.core.AuthNZ.initialize --non-interactive

# Verify
curl http://localhost:8000/health
```

The server is now running on port 8000.

---

## What's Included

The default `docker-compose.yml` starts:

| Service | Purpose | Port |
|---------|---------|------|
| `app` | tldw_server API | 8000 |
| `postgres` | Database (optional, SQLite by default) | 5432 |
| `redis` | Caching (optional) | 6379 |

---

## Configuration

### Adding LLM Providers

Edit your `.env` file to add provider API keys:

```bash
# .env
AUTH_MODE=single_user
SINGLE_USER_API_KEY=your-secure-api-key-at-least-16-chars
DATABASE_URL=sqlite:///./Databases/users.db

# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

Then restart:

```bash
docker compose -f Dockerfiles/docker-compose.yml restart app
```

### Persistent Storage

Data is stored in Docker volumes by default. To use host directories:

```yaml
# docker-compose.override.yml
services:
  app:
    volumes:
      - ./data/databases:/app/Databases
      - ./data/uploads:/app/uploads
```

### Using PostgreSQL Instead of SQLite

For better performance with multiple users:

```bash
# .env
DATABASE_URL=postgresql://tldw:your-secure-password@postgres:5432/tldw
```

The postgres service in docker-compose.yml will be used automatically.

---

## Multi-User Mode (Family/Team)

For shared access with individual accounts:

```bash
# .env
AUTH_MODE=multi_user
JWT_SECRET_KEY=your-jwt-secret-at-least-32-chars
DATABASE_URL=postgresql://tldw:your-secure-password@postgres:5432/tldw
```

Initialize and create admin user:

```bash
docker compose -f Dockerfiles/docker-compose.yml exec app \
  python -m tldw_Server_API.app.core.AuthNZ.initialize
# Follow prompts to create admin account
```

---

## Adding HTTPS (Recommended)

### Option 1: Caddy (Automatic HTTPS)

```bash
docker compose -f Dockerfiles/docker-compose.yml \
  -f Dockerfiles/docker-compose.proxy.yml up -d
```

Edit `Dockerfiles/Caddyfile`:
```
yourdomain.com {
    reverse_proxy app:8000
}
```

Caddy will automatically obtain and renew SSL certificates.

### Option 2: Nginx

```bash
docker compose -f Dockerfiles/docker-compose.yml \
  -f Dockerfiles/docker-compose.proxy-nginx.yml up -d
```

Provide your own SSL certificates in the nginx config.

### Option 3: External Reverse Proxy

If you already have Traefik, nginx, or another proxy:

```yaml
# docker-compose.override.yml
services:
  app:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.tldw.rule=Host(`tldw.yourdomain.com`)"
```

---

## Backups

### Database Backup

```bash
# SQLite
docker cp $(docker compose ps -q app):/app/Databases/users.db ./users.db.backup

# PostgreSQL
docker compose exec -T postgres pg_dump -U tldw tldw > backup.sql
```

### Full Volume Backup

```bash
# Stop services
docker compose -f Dockerfiles/docker-compose.yml down

# Backup volumes
docker run --rm -v tldw_server_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/tldw-backup.tar.gz /data

# Restart
docker compose -f Dockerfiles/docker-compose.yml up -d
```

---

## Updating

```bash
# Pull latest code
git pull

# Rebuild and restart
docker compose -f Dockerfiles/docker-compose.yml up -d --build

# Run any migrations
docker compose -f Dockerfiles/docker-compose.yml exec app \
  python -m tldw_Server_API.app.core.AuthNZ.initialize --non-interactive
```

---

## Monitoring

### View Logs

```bash
# All services
docker compose -f Dockerfiles/docker-compose.yml logs -f

# Just the app
docker compose -f Dockerfiles/docker-compose.yml logs -f app
```

### Check Status

```bash
# Container status
docker compose -f Dockerfiles/docker-compose.yml ps

# Health check
curl http://localhost:8000/health
```

### Prometheus + Grafana

For full monitoring:

```bash
make monitoring-up
# Grafana: http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9090
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Port 8000 in use | Change port: `ports: ["8001:8000"]` in override |
| Container won't start | Check logs: `docker compose logs app` |
| Database connection failed | Ensure postgres is healthy: `docker compose ps` |
| Out of disk space | Clean up: `docker system prune -a` |

---

## Docker Compose Files Reference

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Base stack (app + postgres + redis) |
| `docker-compose.override.yml` | Local overrides (auto-loaded) |
| `docker-compose.proxy.yml` | Caddy reverse proxy |
| `docker-compose.proxy-nginx.yml` | Nginx reverse proxy |
| `docker-compose.dev.yml` | Development settings |
| `docker-compose.embeddings.yml` | Embedding workers |

Combine files:
```bash
docker compose -f docker-compose.yml -f docker-compose.proxy.yml up -d
```

---

## Next Steps

- [Production Guide](./Production.md) - Security hardening for public deployment
- [Monitoring Guide](../Monitoring/Metrics_Cheatsheet.md) - Set up metrics and alerts
- [Backup Guide](../User_Guides/Backups_Using_Litestream.md) - Automated backups
