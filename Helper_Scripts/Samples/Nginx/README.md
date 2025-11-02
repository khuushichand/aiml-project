# Nginx Reverse Proxy (Samples)

This folder contains a minimal Nginx config to run tldw_server behind TLS with WebSocket support.

## Use with Docker Compose (recommended)

1) Edit `Samples/Nginx/nginx.conf`
- Set `server_name your.domain.com`
- Update certificate paths under `ssl_certificate` and `ssl_certificate_key`
  - Defaults assume host-managed LetsEncrypt at `/etc/letsencrypt/...`

2) Start with the proxy overlay (publishes 80/443; unpublishes the app)
```bash
docker compose -f docker-compose.yml -f docker-compose.proxy-nginx.yml up -d --build
```

3) Set app CORS
- In `.env`, set `ALLOWED_ORIGINS=https://your.domain.com`

Notes
- WebSockets: config upgrades `/` so endpoints like `/api/v1/audio/stream/transcribe` and `/api/v1/mcp/*` work.
- Certificates: either mount host `/etc/letsencrypt` (as in the overlay) or replace paths to match your setup.
- Timeouts: `proxy_read_timeout` set high for streaming/inference.

## Standalone (container-only)

```bash
docker run -d --name tldw-nginx \
  -p 80:80 -p 443:443 \
  -v $(pwd)/Samples/Nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro \
  -v /etc/letsencrypt:/etc/letsencrypt:ro \
  nginx:stable
```

Ensure the app is reachable on the docker network at `app:8000` (adjust upstream in the config if needed).
