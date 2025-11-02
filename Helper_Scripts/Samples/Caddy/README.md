# Caddy Reverse Proxy (Samples)

This folder contains Caddyfiles for proxying tldw_server with automatic HTTPS via ACME.

## Use with Docker Compose (recommended)

1) Edit `Samples/Caddy/Caddyfile.compose`
- Replace `your.domain.com` with your domain
- Set `tls you@example.com` to your email (for ACME/Let’s Encrypt)

2) Start with the proxy overlay (publishes 80/443; unpublishes the app)
```bash
docker compose -f docker-compose.yml -f docker-compose.proxy.yml up -d --build
```

3) Set app CORS
- In `.env`, set `ALLOWED_ORIGINS=https://your.domain.com`

Notes
- DNS: your domain must resolve to the host for ACME to succeed.
- WebSockets: handled automatically by Caddy for the same routes.
- Timeouts: long read/write timeouts are configured in the Caddyfile.
- Persistence: overlay mounts `caddy_data` and `caddy_config` for certificate storage.

## Standalone (container-only)

```bash
docker run -d --name tldw-caddy \
  -p 80:80 -p 443:443 \
  -v $(pwd)/Samples/Caddy/Caddyfile:/etc/caddy/Caddyfile:ro \
  -v caddy_data:/data -v caddy_config:/config \
  caddy:2
```

Update `Caddyfile` with your domain/email. Ensure the app is reachable as `localhost:8000` or adjust the upstream.
