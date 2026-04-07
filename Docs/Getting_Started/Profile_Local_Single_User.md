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

> **Windows users:** Use WSL2 or Git Bash. The `make` targets require a Unix-like shell.

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

## What to Do Next

1. **Browse the API docs** at http://127.0.0.1:8000/docs
2. **Configure an LLM provider** — add at least one provider API key to `tldw_Server_API/Config_Files/.env`:
   ```bash
   # Example: add OpenAI
   echo 'OPENAI_API_KEY=sk-your-key-here' >> tldw_Server_API/Config_Files/.env
   # Then restart the server
   ```
3. **Try your first API call:**
   ```bash
   # Get your API key (printed during setup, or check .env)
   API_KEY=$(grep SINGLE_USER_API_KEY tldw_Server_API/Config_Files/.env | cut -d= -f2-)

   curl http://127.0.0.1:8000/api/v1/chat/completions \
     -H "X-API-Key: $API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hello!"}]}'
   ```
4. **Add the WebUI** — see [Local Profile: Add the WebUI](../../README.md#local-profile-add-the-webui) in the main README.
5. **Set up speech** (optional) — follow the [CPU](./First_Time_Audio_Setup_CPU.md) or [GPU](./First_Time_Audio_Setup_GPU_Accelerated.md) audio guide.

### Guided Setup Wizard (Optional)

For a visual configuration wizard, edit `tldw_Server_API/Config_Files/config.txt` and set:
```ini
[Setup]
enable_first_time_setup = true
setup_completed = false
```
Then restart the server and visit http://127.0.0.1:8000/setup.
