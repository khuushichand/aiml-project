# First-Time Production Setup

Version: v0.1.0
Audience: DevOps/SREs and self-hosters deploying tldw_server for the first time

This guide walks you through a secure, production-ready first deployment of tldw_server. It covers Docker Compose (recommended) and a bare-metal alternative, plus the initial setup wizard, TLS, CORS, and basic verification.

Related documents
- Reverse proxy examples (Nginx/Traefik): `Deployment/Reverse_Proxy_Examples.md`
- Postgres migration: `Deployment/Postgres_Migration_Guide.md`
- Metrics and Grafana: `Monitoring/Metrics_Cheatsheet.md`
- Environment variables reference: `Env_Vars.md`
- General installation (local/dev): `User_Guides/Installation-Setup-Guide.md`
- Production hardening checklist: `User_Guides/Production_Hardening_Checklist.md`

## 1) Prerequisites

- OS: Linux (Ubuntu 22.04 LTS or similar recommended). macOS/Windows supported for small installs.
- CPU/RAM: Minimum 2 vCPU / 4 GB RAM; recommended 4+ vCPU / 8+ GB.
- Storage: 50 GB+ SSD for media, databases, and models.
- FFmpeg installed (Docker image includes it; bare-metal must install via package manager).
- DNS configured for your domain (if exposing over the internet).
- TLS via reverse proxy (Nginx/Traefik/Caddy). See reverse proxy guide.
- Database: SQLite is fine for single-user; Postgres recommended for production multi-user.

Security preflight
- Decide auth mode: `single_user` (API key) or `multi_user` (JWT).
- Generate strong secrets:
  - API key: `python -c "import secrets;print(secrets.token_urlsafe(32))"`
  - JWT secret: `openssl rand -base64 64`
- Restrict CORS to your site(s) with `ALLOWED_ORIGINS`.
- In production, set `tldw_production=true` to mask secrets in logs and harden defaults.

## 2) Quick Decision Matrix

- Want the fastest secure start, one host? Choose Docker Compose (recommended).
- Need package-managed services and systemd? Use bare-metal + Nginx.
- Expect multiple users/teams? Prefer Postgres and reverse proxy TLS from day one.

## 3) Option A - Docker Compose (recommended)

The repository ships with a Compose stack for the API + Postgres + Redis.

Step A1 - Clone and prepare env
```bash
git clone https://github.com/<your-org>/tldw_server.git
cd tldw_server

# Copy example env and edit (recommended for Compose)
cp .env.example .env

# Required values (examples)
export AUTH_MODE=multi_user
export JWT_SECRET_KEY="$(openssl rand -base64 64)"
export DATABASE_URL="postgresql://tldw_user:ChangeMeStrong123!@postgres:5432/tldw_users"

# Strong single-user key if you use single_user mode instead
export SINGLE_USER_API_KEY="$(python -c "import secrets;print(secrets.token_urlsafe(32))")"

# Production hardening
export tldw_production=true
export ALLOWED_ORIGINS=https://your.domain.com
```

Step A2 - Bring the stack up
```bash
# Build and start (detached)
docker compose up --build -d

# Check container health
docker compose ps
```

The app listens on `:8000` inside the container and is exposed on the host at `:8000` by default.

Note
- `docker-compose.override.yml` is included with production-leaning defaults (tldw_production, CORS, Postgres). Compose auto-loads it alongside `docker-compose.yml`.

Step A3 - First-time setup (optional wizard)
- The server exposes a local-only setup flow at `/setup` when enabled.
- Check status: `curl http://127.0.0.1:8000/api/v1/setup/status`
- If `enabled` and `needs_setup` are true, open `http://127.0.0.1:8000/setup` on the host.
- Behind a proxy, do not expose `/setup` publicly. If you must reach it remotely on a trusted network, set `TLDW_SETUP_ALLOW_REMOTE=1` temporarily and remove it afterward.

Step A4 - Add TLS and reverse proxy
- Terminate TLS at the proxy; forward to `app:8000`.
- Ensure WebSocket upgrade for `/api/v1/audio/stream/transcribe` and `/api/v1/mcp/*`.
- See: `Deployment/Reverse_Proxy_Examples.md` for Nginx/Traefik configs and labels.
- Caddy example: `Samples/Caddy/Caddyfile` (simple HTTPS reverse proxy to the app).

Step A5 - Verify health
```bash
curl -s http://127.0.0.1:8000/health | jq .
curl -s http://127.0.0.1:8000/ready  | jq .
# OpenAPI (enable explicitly in prod if desired)
open http://127.0.0.1:8000/docs
open http://127.0.0.1:8000/webui/
```

Notes
- For multi-user production, keep Postgres running via the `postgres` service in the Compose file. Back up its volume.
- To scale CPU workers: set `UVICORN_WORKERS` via the app environment and rebuild or override in Compose.

Optional: Add a reverse proxy with Caddy (automatic HTTPS)
```bash
# Use the proxy variant with the base compose file
docker compose -f docker-compose.yml -f docker-compose.proxy.yml up -d

# Edit the hostname/email in Samples/Caddy/Caddyfile.compose before starting
```

Optional: Add a reverse proxy with Nginx
```bash
# Use the nginx proxy variant with the base compose file
docker compose -f docker-compose.yml -f docker-compose.proxy-nginx.yml up -d

# Ensure Samples/Nginx/nginx.conf has your domain and cert paths
# Map /etc/letsencrypt into the container or adjust the paths accordingly
```

## 4) Option B - Bare-Metal (systemd + Nginx)

Step B1 - System packages
```bash
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv ffmpeg nginx curl
```

Step B2 - App install
```bash
git clone https://github.com/<your-org>/tldw_server.git
cd tldw_server
python3.11 -m venv /opt/tldw_server/venv
source /opt/tldw_server/venv/bin/activate
pip install -U pip
pip install -e .[multiplayer]

cp .env.authnz.template .env
vi .env   # set AUTH_MODE, keys, DATABASE_URL, ALLOWED_ORIGINS, tldw_production=true

# Initialize AuthNZ DB and seed admin (mode-aware)
python -m tldw_Server_API.app.core.AuthNZ.initialize
```

Step B3 - Systemd service
Create `/etc/systemd/system/tldw.service`:
```ini
[Unit]
Description=tldw Server API
After=network.target

[Service]
Type=simple
User=tldw
Group=tldw
WorkingDirectory=/opt/tldw_server
EnvironmentFile=/opt/tldw_server/.env
Environment="PYTHONPATH=/opt/tldw_server"
ExecStart=/opt/tldw_server/venv/bin/python -m uvicorn tldw_Server_API.app.main:app \
  --host 127.0.0.1 --port 8000 --workers 4 --proxy-headers --log-level info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tldw
sudo systemctl status tldw --no-pager
```

Step B4 - Nginx reverse proxy + TLS
Use the examples in `Deployment/Reverse_Proxy_Examples.md` or configure a site:
```nginx
server {
  listen 443 ssl http2;
  server_name your.domain.com;
  ssl_certificate     /etc/letsencrypt/live/your.domain.com/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/your.domain.com/privkey.pem;
  client_max_body_size 200m;
  proxy_read_timeout   3600;
  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

## 5) Configuration essentials

- `AUTH_MODE`: `single_user` or `multi_user`.
- `SINGLE_USER_API_KEY` (single-user) or `JWT_SECRET_KEY` (multi-user).
- `DATABASE_URL`: SQLite for dev; Postgres URL recommended in production multi-user.
- `ALLOWED_ORIGINS`: Comma-separated or JSON array of trusted origins.
- `tldw_production`: `true` in production to mask secrets and enable production guards.
- Provider keys: e.g., `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.

See `Env_Vars.md` for the complete list and `User_Guides/Authentication_Setup.md` for AuthNZ details.

## 6) Verify and smoke test

Health/ready
```bash
curl -f http://127.0.0.1:8000/health
curl -f http://127.0.0.1:8000/ready
```

Auth check (single-user example)
```bash
curl -s -H "X-API-KEY: $SINGLE_USER_API_KEY" http://127.0.0.1:8000/api/v1/llm/providers | jq .
```

Media test (small file)
```bash
curl -s -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -F "files=@Samples/sample.pdf" \
  http://127.0.0.1:8000/api/v1/media/process | jq .status
```

## 7) Production checklist (summary)

- Secrets:
  - Strong `SINGLE_USER_API_KEY` (single-user) or `JWT_SECRET_KEY` (multi-user).
  - Don’t print keys on startup in production; keep `SHOW_API_KEY_ON_STARTUP` unset/false.
- Database:
  - Use Postgres for multi-user; back up volumes regularly.
  - If migrating from SQLite, follow `Deployment/Postgres_Migration_Guide.md`.
- Network:
  - TLS via reverse proxy; enable WebSocket upgrades.
  - Restrict `ALLOWED_ORIGINS`.
- Observability:
  - Enable Prometheus scraping; import Grafana dashboards (see Metrics Cheatsheet).
  - Centralize logs; set `LOG_LEVEL=info`.
- Rate limits:
  - Keep global and module-specific rate limiters enabled and tuned for your users.

For a comprehensive list, see `User_Guides/Production_Hardening_Checklist.md`.
