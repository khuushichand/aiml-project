# Local Single-User Setup

Use this profile for development, local debugging, or contributor workflows where you want to run the API directly on your machine with a local Python virtual environment.

For most self-hosted users:
- use `make quickstart` for the Docker single-user + WebUI path,
- use `make quickstart-docker` for the API-only Docker path,
- use `Docker multi-user + Postgres` for team or public deployments.

## Prerequisites

- macOS/Linux/Windows
- Python 3.10+
- `ffmpeg`
- Git

## Install

```bash
git clone https://github.com/rmusser01/tldw_server.git
cd tldw_server
make quickstart-install
```

If your default `python3` is older than 3.10:

```bash
make quickstart-install PYTHON=python3.12
```

## Run

```bash
make quickstart-local
```

Default API URL: `http://127.0.0.1:8000`

## Verify

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/docs > /dev/null && echo "docs-ok"
curl -sS http://127.0.0.1:8000/api/v1/config/quickstart
```

## Optional Add-ons

- If speech is part of day-one setup, continue with [First-Time Audio Setup: CPU Systems](./First_Time_Audio_Setup_CPU.md) or [First-Time Audio Setup: GPU/Accelerated Systems](./First_Time_Audio_Setup_GPU_Accelerated.md) after this profile is running.

## Troubleshoot

- If startup fails on audio dependencies, verify `ffmpeg -version`.
- If install fails due to Python version, rerun with `PYTHON=python3.12` (or another supported version).
- If port `8000` is in use, stop the conflicting process or run via uvicorn on another port.
