# Production Deployment Guide

This guide covers deploying tldw_server for a team with proper security, authentication, and operational considerations.

**Time to complete:** 1-2 hours (including security setup and testing)

**Prerequisites:**
- Completed [Docker Self-Host Guide](./Docker_Self_Host.md) for Docker basics
- Domain name with DNS configured (for HTTPS)
- PostgreSQL database (required for multi-user production)
- Basic understanding of reverse proxies and SSL certificates

## What You'll Have at the End

- Multi-user tldw_server with JWT authentication
- PostgreSQL database for reliable data storage
- HTTPS with proper security headers
- Monitoring and backup infrastructure

---

## Security Checklist

Before deploying to production, ensure:

- [ ] **Strong secrets** - All keys are 32+ characters, randomly generated
- [ ] **PostgreSQL database** - SQLite is not suitable for production multi-user
- [ ] **HTTPS enabled** - All traffic encrypted via reverse proxy
- [ ] **Rate limiting** - Prevent abuse (built-in, verify configuration)
- [ ] **CORS configured** - Only allow your domains
- [ ] **Secrets in .env** - Never commit secrets to git
- [ ] **Regular backups** - Automated database backups

---

## Multi-User JWT Authentication

Production deployments should use multi-user mode with JWT tokens.

### Step 1: Generate Secure Secrets

```bash
# Generate all required secrets
openssl rand -base64 32  # JWT_SECRET_KEY
openssl rand -base64 32  # MCP_JWT_SECRET
openssl rand -base64 32  # MCP_API_KEY_SALT
openssl rand -hex 32     # API_KEY_PEPPER
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # SESSION_ENCRYPTION_KEY
```

### Step 2: Configure Environment

```bash
# .env for production
AUTH_MODE=multi_user
tldw_production=true

# Database (PostgreSQL required)
DATABASE_URL=postgresql://tldw:SECURE_PASSWORD@postgres:5432/tldw

# JWT Configuration
JWT_SECRET_KEY=<your-32-char-secret>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# MCP Security
MCP_JWT_SECRET=<your-32-char-secret>
MCP_API_KEY_SALT=<your-32-char-secret>

# API Key Security
API_KEY_PEPPER=<your-64-char-hex-secret>
SESSION_ENCRYPTION_KEY=<your-fernet-key>

# CORS (your domains only)
ALLOWED_ORIGINS=https://app.yourdomain.com,https://admin.yourdomain.com

# Hide sensitive info in logs
SHOW_API_KEY_ON_STARTUP=false
```

### Step 3: Initialize with Admin User

```bash
docker compose -f Dockerfiles/docker-compose.yml \
  -f Dockerfiles/docker-compose.override.yml exec app \
  python -m tldw_Server_API.app.core.AuthNZ.initialize

# Follow prompts:
# - Enter admin username
# - Enter admin email
# - Enter admin password (min 10 chars)
```

---

## Database Configuration

### PostgreSQL Setup

```yaml
# docker-compose.override.yml
services:
  postgres:
    environment:
      POSTGRES_USER: tldw
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}  # Set in .env
      POSTGRES_DB: tldw
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U tldw"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

### Connection Pooling

For high-traffic deployments, use PgBouncer:

```bash
docker compose -f Dockerfiles/docker-compose.yml \
  -f Dockerfiles/docker-compose.pg.yml up -d
```

---

## HTTPS Configuration

### With Caddy (Recommended)

```bash
# Caddyfile
tldw.yourdomain.com {
    reverse_proxy app:8000

    # Security headers
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
    }
}
```

```bash
docker compose -f Dockerfiles/docker-compose.yml \
  -f Dockerfiles/docker-compose.proxy.yml up -d
```

### With External Load Balancer

If using AWS ALB, Cloudflare, or similar:

```yaml
# docker-compose.override.yml
services:
  app:
    environment:
      TRUSTED_HOSTS: tldw.yourdomain.com
      FORWARDED_ALLOW_IPS: "*"  # Or specific IPs
```

---

## Scaling

### Horizontal Scaling

For high availability, run multiple app instances:

```yaml
# docker-compose.override.yml
services:
  app:
    deploy:
      replicas: 3
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
```

### Background Workers

For heavy processing (embeddings, media ingestion):

```bash
docker compose -f Dockerfiles/docker-compose.yml \
  -f Dockerfiles/docker-compose.workers.yml up -d
```

---

## Monitoring

### Metrics Endpoint

tldw_server exposes Prometheus metrics at `/metrics`.

### Prometheus + Grafana Stack

```bash
make monitoring-up
```

Access:
- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090

### Health Checks

Set up external monitoring to check:

```bash
# Application health
curl -f https://tldw.yourdomain.com/health

# Database health
curl -f https://tldw.yourdomain.com/health/ready
```

---

## Backups

### Automated PostgreSQL Backups

```bash
# Add to crontab
0 2 * * * docker compose -f /path/to/docker-compose.yml exec -T postgres \
  pg_dump -U tldw tldw | gzip > /backups/tldw-$(date +\%Y\%m\%d).sql.gz
```

### Using Litestream (SQLite)

If using SQLite for specific databases:

```bash
# See Docs/User_Guides/Backups_Using_Litestream.md
```

---

## User Management

### Create Users

```bash
# Via API (as admin)
curl -X POST https://tldw.yourdomain.com/api/v1/auth/register \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username":"newuser","email":"user@example.com","password":"SecurePassword123"}'
```

### API Key Management

```bash
# Create API key for user
curl -X POST https://tldw.yourdomain.com/api/v1/auth/api-keys \
  -H "Authorization: Bearer USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"My App Key","expires_in_days":365}'
```

---

## Troubleshooting

### Check Logs

```bash
# Application logs
docker compose logs -f app

# All services
docker compose logs -f
```

### Common Production Issues

| Issue | Solution |
|-------|----------|
| 502 Bad Gateway | App container crashed - check `docker compose logs app` |
| Database connection refused | Postgres not ready - check `docker compose ps` |
| SSL certificate errors | Caddy needs port 443 open and domain DNS configured |
| High memory usage | Add Redis for caching, check for memory leaks |

---

## Security Hardening Reference

For comprehensive security guidance, see:
- [Production Hardening Checklist](../User_Guides/Production_Hardening_Checklist.md)
- [Multi-User Deployment Guide](../User_Guides/Multi-User_Deployment_Guide.md)
- [AuthNZ Developer Guide](../Code_Documentation/AuthNZ-Developer-Guide/)

---

## Support

- Issues: https://github.com/rmusser01/tldw_server/issues
- Discussions: https://github.com/rmusser01/tldw_server/discussions
