# Sidecar Workers

Sidecar mode runs Jobs workers as separate processes instead of threads inside the API server.
This isolates failures, avoids blocking the main event loop, and is recommended when you run multiple Uvicorn workers.
It also reduces SQLite lock contention by avoiding per-Uvicorn-worker background threads.

Source of truth:
- `Docs/Deployment/sidecar_workers_manifest.json`
- `Helper_Scripts/Deployment/generate_sidecar_files.py`
After changes, regenerate: `python Helper_Scripts/Deployment/generate_sidecar_files.py`.

Important: set `TLDW_WORKERS_SIDECAR_MODE=true` for the API process so it skips in-process workers.

## Workers and entrypoints

{{WORKER_LIST}}

## Option A: start-sidecars.sh (local/dev)

```bash
./start-sidecars.sh
```

Tunable env vars:
- `TLDW_SIDECAR_WORKERS={{DEFAULT_WORKERS}}`
{{OPTIONAL_NOTE}}
- `TLDW_ENV_FILE=/path/to/.env`
- `TLDW_LOG_DIR=/path/to/logs`
- `TLDW_WORKERS_MANIFEST=/path/to/sidecar_workers_manifest.json`
- `UVICORN_HOST/UVICORN_PORT/UVICORN_WORKERS/UVICORN_RELOAD/UVICORN_EXTRA_ARGS`

## Option B: Docker Compose overlay

```bash
# Base compose + sidecar workers
docker compose -f Dockerfiles/docker-compose.yml -f Dockerfiles/docker-compose.workers.yml up -d --build

# Postgres variant
docker compose -f Dockerfiles/docker-compose.postgres.yml -f Dockerfiles/docker-compose.workers.yml up -d --build
```

## Option C: systemd (Linux)

Example units and timers are in `Docs/Deployment/systemd/`.
Copy the ones you need into `/etc/systemd/system/` and update:
- `WorkingDirectory` to your repo root
- `ExecStart` to your venv python
- `User`/`Group` and `EnvironmentFile`

```bash
sudo cp Docs/Deployment/systemd/tldw-worker-chatbooks.service /etc/systemd/system/
sudo cp Docs/Deployment/systemd/tldw-worker-chatbooks.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tldw-worker-chatbooks.service
```

Timers are optional. They periodically attempt to start the worker if it is not running.
Most installs should enable the `.service` units and skip the `.timer` units.

## Option D: launchd (macOS)

Example plists are in `Docs/Deployment/launchd/`.
Copy to `~/Library/LaunchAgents` (per-user) or `/Library/LaunchDaemons` (system-wide),
update the paths, and adjust `UserName`/`GroupName` as needed (LaunchDaemons should use
a dedicated service account; LaunchAgents should remove those keys or set them to your login user),
then load them.

```bash
mkdir -p ~/Library/LaunchAgents
cp Docs/Deployment/launchd/com.tldw.worker.chatbooks.plist ~/Library/LaunchAgents/

# Modern macOS (10.11+)
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.tldw.worker.chatbooks.plist

# Legacy (deprecated)
launchctl load -w ~/Library/LaunchAgents/com.tldw.worker.chatbooks.plist
```

Ensure the log directory exists (default `/opt/tldw_server/logs/launchd`).
Use `launchctl list | grep tldw.worker` to confirm the worker is running.
