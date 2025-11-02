# Proxy Overlays (Compose)

Use these overlays to place a TLS reverse proxy in front of the app and remove direct exposure of port 8000. Pick one: Caddy (automatic HTTPS) or Nginx (manual certificates).

## Caddy (automatic HTTPS)

Overlay file: `docker-compose.proxy.yml`

- Pros: Automatic HTTPS via ACME; simple config
- Cons: Requires public DNS for your domain

Usage
```bash
docker compose -f docker-compose.yml -f docker-compose.proxy.yml up -d --build
```

Edit `Samples/Caddy/Caddyfile.compose`:
- Replace `your.domain.com`
- Set `tls you@example.com`

See: `Samples/Caddy/README.md`

## Nginx (manual certs)

Overlay file: `docker-compose.proxy-nginx.yml`

- Pros: Traditional, flexible
- Cons: You manage certs (e.g., host `/etc/letsencrypt`)

Usage
```bash
docker compose -f docker-compose.yml -f docker-compose.proxy-nginx.yml up -d --build
```

Edit `Samples/Nginx/nginx.conf`:
- Set `server_name your.domain.com`
- Set `ssl_certificate` and `ssl_certificate_key` paths

See: `Samples/Nginx/README.md`

## App Configuration Notes

- Set `ALLOWED_ORIGINS=https://your.domain.com` in `.env`
- Keep `tldw_production=true` in production
- The app’s container port 8000 remains internal; the proxy publishes 80/443

## Related

- Reverse proxy examples (config snippets): `Deployment/Reverse_Proxy_Examples.md`
- First-time production setup: `Deployment/First_Time_Production_Setup.md`
- Long-term admin operations: `Deployment/Long_Term_Admin_Guide.md`
