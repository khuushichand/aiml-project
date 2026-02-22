# Docker Compose & Images

This folder contains the base Compose stack for tldw_server, optional overlays, and worker/infra stacks. All commands assume you run from the repo root.

## Base Stack

- File: `Dockerfiles/docker-compose.yml`
- Services: `app` (FastAPI), `postgres`, `redis`
- Start (single-user, SQLite users DB):
  - `docker compose --env-file tldw_Server_API/Config_Files/.env -f Dockerfiles/docker-compose.yml up -d --build`
  - First start in `single_user` mode auto-generates a secure `SINGLE_USER_API_KEY` if missing/placeholder and runs `AuthNZ.initialize --non-interactive` only when `/app/Databases/.authnz_initialized_single_user` is absent in the attached Docker volume.
  - If that marker exists in the volume, AuthNZ initialization is skipped on container restart; it runs again only if the volume is replaced or the marker is removed.
- Start (multi-user, Postgres users DB):
  - `export AUTH_MODE=multi_user`
  - `export DATABASE_URL=postgresql://tldw_user:TestPassword123!@postgres:5432/tldw_users`
  - `docker compose -f Dockerfiles/docker-compose.yml up -d --build`
- Logs and status:
  - `docker compose -f Dockerfiles/docker-compose.yml ps`
  - `docker compose -f Dockerfiles/docker-compose.yml logs -f app`

## Overlays & Profiles

- Production overrides: `Dockerfiles/docker-compose.override.yml`
  - `docker compose -f Dockerfiles/docker-compose.yml -f Dockerfiles/docker-compose.override.yml up -d --build`
  - Sets production flags, disables API key echo, and tightens defaults.

- Reverse proxy (Caddy): `Dockerfiles/docker-compose.proxy.yml`
  - `docker compose -f Dockerfiles/docker-compose.yml -f Dockerfiles/docker-compose.proxy.yml up -d --build`
  - Exposes 80/443 via Caddy; unpublish app port on host.

- Reverse proxy (Nginx): `Dockerfiles/docker-compose.proxy-nginx.yml`
  - `docker compose -f Dockerfiles/docker-compose.yml -f Dockerfiles/docker-compose.proxy-nginx.yml up -d --build`
  - Mount `Samples/Nginx/nginx.conf` and your certs.

- Postgres (basic standalone): `Dockerfiles/docker-compose.postgres.yml`
  - Start a standalone Postgres you can point `DATABASE_URL` to.
  - Example:
    - `export DATABASE_URL=postgresql://tldw_user:TestPassword123!@localhost:5432/tldw_users`
    - `docker compose -f Dockerfiles/docker-compose.postgres.yml up -d`

- Postgres + pgvector + pgbouncer (dev): `Dockerfiles/docker-compose.pg.yml`
  - `docker compose -f Dockerfiles/docker-compose.pg.yml up -d`

- Dev overlay (unified streaming pilot): `Dockerfiles/docker-compose.dev.yml`
  - `docker compose -f Dockerfiles/docker-compose.yml -f Dockerfiles/docker-compose.dev.yml up -d --build`
  - Sets `STREAMS_UNIFIED=1` (keep off in production until validated).

- WebUI overlay: `Dockerfiles/docker-compose.webui.yml`
  - `docker compose -f Dockerfiles/docker-compose.yml -f Dockerfiles/docker-compose.webui.yml up -d --build`
  - Adds `webui` (Next.js standalone) on `http://localhost:8080`.

- Embeddings workers + monitoring: `Dockerfiles/docker-compose.embeddings.yml`
  - Base workers only: `docker compose -f Dockerfiles/docker-compose.embeddings.yml up -d`
  - With monitoring profile (Prometheus + Grafana):
    - `docker compose -f Dockerfiles/docker-compose.embeddings.yml --profile monitoring up -d`
  - With debug profile (Redis Commander):
    - `docker compose -f Dockerfiles/docker-compose.embeddings.yml --profile debug up -d`
  - Scale workers: `docker compose -f Dockerfiles/docker-compose.embeddings.yml up -d --scale chunking-workers=3 --scale embedding-workers=2 --scale storage-workers=1 --scale content-workers=1`

## Images

- App image: `Dockerfiles/Dockerfile.prod` (built by base compose)
  - Uses a multi-stage build so compiler/dev packages stay in the builder stage.
- WebUI image: `Dockerfiles/Dockerfile.webui` (used by WebUI overlay)
- Worker image: `Dockerfiles/Dockerfile.worker` (used by embeddings compose)

## Notes

- Run compose commands from repo root so relative paths resolve correctly.
- For production, pair the app with a reverse proxy and set strong secrets in `.env`.
- GPU for embeddings workers: ensure the host has NVIDIA runtime configured and adjust `CUDA_VISIBLE_DEVICES` as needed in the embeddings compose.
- To avoid publishing the app port on host when using a proxy overlay, do not also map `8000:8000` in `app`.

## Troubleshooting

- Health checks: `app` responds on `/ready`; `postgres`/`redis` include health checks.
- If the app fails waiting for DB, verify `DATABASE_URL` and Postgres readiness.
- `single_user` quickstart bootstraps a strong `SINGLE_USER_API_KEY` (when missing/placeholder) and performs one-time AuthNZ initialization based on the marker file `/app/Databases/.authnz_initialized_single_user` stored in the attached volume.
- Initialization is skipped when that marker already exists, and will re-run only after volume replacement or marker removal (force re-init by deleting the marker, or by reinitializing the auth DB and clearing the marker).
- For `multi_user`, run AuthNZ initialization manually to create your admin account.
- View full logs: `docker compose ... logs -f`
