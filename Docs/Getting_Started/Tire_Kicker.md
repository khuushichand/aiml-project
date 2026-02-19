# Try tldw_server in 5 Minutes

This guide gets you from zero to a running tldw_server with working API calls. No prior setup required.

**Time to complete:** 5-10 minutes

## What You'll Have at the End

- A running tldw_server on your machine
- A verified API key that works
- Knowledge of how to make API calls

---

## Fastest Path (30 Seconds)

If you have Python 3.10+ (recommended: 3.12):

```bash
git clone https://github.com/rmusser01/tldw_server.git && cd tldw_server
make quickstart-install
# If `python3` is older than 3.10 on your machine:
# make quickstart-install PYTHON=python3.13  # or python3.12 / python3.11 / python3.10
```

This creates `tldw_Server_API/Config_Files/.env`, initializes auth, and starts the server. Verify with:
```bash
curl http://localhost:8000/health
```

Already have dependencies installed and a Python 3.10+ interpreter selected? Use `make quickstart` (or set `PYTHON=python3.13` / `PYTHON=python3.12` / `PYTHON=.venv/bin/python`).

**Not working?** Continue with the step-by-step options below.

---

## Prerequisites

Python support for this repo:
- Minimum: Python 3.10+
- CI-tested: Python 3.11, 3.12, and 3.13
- Recommended for local development: Python 3.12

| Requirement | Check Command | Install |
|-------------|---------------|---------|
| Python 3.10+ | `python --version` (or `python3 --version` on macOS/Linux) | [python.org](https://www.python.org/downloads/) |
| ffmpeg | `ffmpeg -version` | `brew install ffmpeg` (macOS) or your Linux package manager |
| PyAudio/PortAudio (optional; audio capture paths) | `python -c "import pyaudio"` | Linux: install `portaudio` + `python3-pyaudio`; macOS: `brew install portaudio && pip install pyaudio`; Windows: `pip install pyaudio` |
| Bun (optional; WebUI section below) | `bun --version` | [bun.sh](https://bun.sh/) |
| pip | `pip --version` | Comes with Python |

**Don't have Python/ffmpeg?** Use [Docker instead](#option-b-docker) (requires Docker Desktop or Docker Engine).

Linux package examples:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y ffmpeg portaudio19-dev python3-pyaudio

# Fedora/RHEL (RPM Fusion may be required for ffmpeg)
sudo dnf install -y ffmpeg portaudio-devel python3-pyaudio
```

---

## Option A: Python (Recommended for First-Time Users)

### Step 1: Clone and Install

```bash
# Clone the repository
git clone https://github.com/rmusser01/tldw_server.git
cd tldw_server

# Create virtual environment with a supported Python interpreter
# macOS/Linux (3.12 recommended)
python3.12 -m venv .venv  # or python3.13 / python3.11 / python3.10
source .venv/bin/activate

# Windows (PowerShell)
py -3.12 -m venv .venv  # or -3.13 / -3.11 / -3.10
.venv\Scripts\Activate.ps1

# Confirm the active interpreter version
python --version

# Install dependencies
pip install -e .
```

PyAudio/PortAudio notes:
- Linux: install `portaudio19-dev` + `python3-pyaudio` (Debian/Ubuntu) or `portaudio-devel` + `python3-pyaudio` (Fedora/RHEL).
- macOS: `brew install portaudio`, then `pip install pyaudio` in the activated venv.
- Windows: run `pip install pyaudio` in the activated venv; if build fails, install Microsoft C++ Build Tools and retry.

**Expected output:** Lots of package installation messages, ending with "Successfully installed..."

**Tip:** The install takes 2-3 minutes depending on your internet speed.

### Step 2: Create Configuration

```bash
# Copy the minimal config template
cp tldw_Server_API/Config_Files/.env.quickstart tldw_Server_API/Config_Files/.env
```

Now edit `tldw_Server_API/Config_Files/.env` and change the API key:

```bash
# tldw_Server_API/Config_Files/.env
AUTH_MODE=single_user
SINGLE_USER_API_KEY=my-super-secret-key-at-least-16-chars   # <-- Change this!
DATABASE_URL=sqlite:///./Databases/users.db
```

**Important:** Your API key must be at least 16 characters.

### Step 3: Initialize Authentication

```bash
python -m tldw_Server_API.app.core.AuthNZ.initialize --non-interactive
```

**Expected output:**
```
[INFO] Initializing AuthNZ...
[INFO] Created database tables
[INFO] AuthNZ initialization complete
```

### Step 4: Start the Server

```bash
uvicorn tldw_Server_API.app.main:app --host 127.0.0.1 --port 8000
```

**Expected output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Leave this terminal running.

### Step 5: Verify It Works

Open a **new terminal** and run:

```bash
# Health check (no authentication needed!)
curl http://localhost:8000/health
```

**Expected output:**
```json
{"status":"ok","checks":{"database":"ok","redis":"skipped"}}
```

If you see this, your server is running.

---

## Option B: Docker

If you prefer Docker or don't want to install Python.

**Requires:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (macOS/Windows) or Docker Engine (Linux)

```bash
# Clone the repository
git clone https://github.com/rmusser01/tldw_server.git
cd tldw_server

# Create tldw_Server_API/Config_Files/.env with your API key
cat > tldw_Server_API/Config_Files/.env << 'EOF'
AUTH_MODE=single_user
SINGLE_USER_API_KEY=my-super-secret-key-at-least-16-chars
DATABASE_URL=sqlite:///./Databases/users.db
EOF

# Start with Docker Compose (takes 3-5 minutes first time)
docker compose --env-file tldw_Server_API/Config_Files/.env -f Dockerfiles/docker-compose.yml up -d --build

# Initialize auth
docker compose --env-file tldw_Server_API/Config_Files/.env -f Dockerfiles/docker-compose.yml exec app \
  python -m tldw_Server_API.app.core.AuthNZ.initialize --non-interactive

# Verify
curl http://localhost:8000/health
```

---

## Verification Checklist

Run these commands to verify everything works:

### 1. Health Check (No Auth)

```bash
curl http://localhost:8000/health
```
Expected: `{"status":"ok",...}`

### 2. Authentication Test

```bash
# Replace YOUR_KEY with your SINGLE_USER_API_KEY from tldw_Server_API/Config_Files/.env
curl -H "X-API-KEY: YOUR_KEY" http://localhost:8000/api/v1/llm/providers
```
Expected: `{"providers":[...]}`

### 3. API Documentation

Open in browser: http://localhost:8000/docs

You should see the Swagger UI with all available endpoints.

---

## Optional: Add the WebUI (Bun)

If your API is already running on `http://127.0.0.1:8000`, you can launch the Next.js WebUI with Bun.

### Step 1: Install Bun (if needed)

```bash
# macOS/Linux
curl -fsSL https://bun.sh/install | bash

# Windows (PowerShell)
powershell -c "irm bun.sh/install.ps1 | iex"

# Open a new terminal, then verify:
bun --version
```

### Step 2: Set up the WebUI project

```bash
# from the repo root
cd apps/tldw-frontend
cp .env.local.example .env.local
bun install
```

### Step 3: Run the WebUI

```bash
bun run dev -- -p 8080
```

Confirm `.env.local` has:
```bash
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_API_VERSION=v1
# Optional in single-user mode:
# NEXT_PUBLIC_X_API_KEY=your_single_user_api_key
```

Open in browser: http://localhost:8080

---

## Common Issues

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `Connection refused` | Server not running | Start with `uvicorn ...` command |
| `401 Unauthorized` | Wrong API key | Check `.env` matches your header |
| `API key too short` | Key < 16 chars | Use a longer key |
| `ffmpeg not found` | Missing dependency | Install ffmpeg |
| `ModuleNotFoundError` | Not in venv | Run `source .venv/bin/activate` |
| Port 8000 in use | Another service | Use `--port 8001` instead |

---

## Next Steps

Now that your server is running:

| I want to... | Guide |
|--------------|-------|
| Add LLM providers (OpenAI, Anthropic, etc.) | [Local Development Guide](./Local_Development.md) |
| Launch the WebUI with Bun | [Optional: Add the WebUI (Bun)](#optional-add-the-webui-bun) |
| Run on my home server with Docker | [Docker Self-Host Guide](./Docker_Self_Host.md) |
| Deploy for a team with proper security | [Production Guide](./Production.md) |
| Process my first media file | See README.md Usage Examples |

---

## Quick Reference

```bash
# Start server
uvicorn tldw_Server_API.app.main:app --host 127.0.0.1 --port 8000

# Start with hot reload (for development)
uvicorn tldw_Server_API.app.main:app --reload

# Health check
curl http://localhost:8000/health

# List providers (authenticated)
curl -H "X-API-KEY: YOUR_KEY" http://localhost:8000/api/v1/llm/providers

# API docs
open http://localhost:8000/docs
```
