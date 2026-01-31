# CLI Reference

This guide covers command-line tools and commands for working with tldw_server.

## Architecture Note

As of v0.1.0+, tldw_server uses a **FastAPI-first architecture**. The primary interface is the REST API, accessible at `http://127.0.0.1:8000/docs` when the server is running. The legacy Gradio UI and `summarize.py` CLI have been deprecated.

**Primary interfaces:**
- **REST API**: Full-featured API with OpenAPI documentation at `/docs`
- **Next.js WebUI**: Modern web interface at `apps/tldw-frontend/`

## Starting the Server

```bash
# Basic development server with auto-reload
python -m uvicorn tldw_Server_API.app.main:app --reload

# Specify host and port
python -m uvicorn tldw_Server_API.app.main:app --host 0.0.0.0 --port 8000 --reload

# Production mode (no reload, multiple workers)
python -m uvicorn tldw_Server_API.app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Useful URLs after startup:**
- API Documentation: `http://127.0.0.1:8000/docs`
- Quickstart Guide: `http://127.0.0.1:8000/api/v1/config/quickstart`
- Setup Wizard (if needed): `http://127.0.0.1:8000/setup`

## Running Tests

```bash
# Run all tests
python -m pytest -v

# Run with coverage report
python -m pytest --cov=tldw_Server_API --cov-report=term-missing

# Run specific test categories
python -m pytest -m "unit" -v        # Unit tests only
python -m pytest -m "integration" -v # Integration tests only

# Run tests for a specific module
python -m pytest tldw_Server_API/tests/TTS/ -v
python -m pytest tldw_Server_API/tests/AuthNZ/ -v
```

## Helper Scripts

Several helper scripts are available in `Helper_Scripts/`:

### Documentation

```bash
# Refresh published documentation (copies to Docs/Published/)
bash Helper_Scripts/refresh_docs_published.sh
```

### TTS Installers

```bash
# Install TTS backends with their dependencies and models
python Helper_Scripts/TTS_Installers/install_tts_kokoro.py
python Helper_Scripts/TTS_Installers/install_tts_chatterbox.py
python Helper_Scripts/TTS_Installers/install_tts_vibevoice.py --variant 1.5B
python Helper_Scripts/TTS_Installers/install_tts_neutts.py --prefetch

# Download Kokoro assets separately
python Helper_Scripts/download_kokoro_assets.py \
  --repo-id onnx-community/Kokoro-82M-v1.0-ONNX-timestamped \
  --model-path models/kokoro/onnx/model.onnx \
  --voices-dir models/kokoro/voices
```

### AuthNZ Initialization

```bash
# Initialize authentication database
python -m tldw_Server_API.app.core.AuthNZ.initialize
```

## Environment Variables

Key environment variables for CLI usage:

| Variable | Purpose |
|----------|---------|
| `AUTH_MODE` | `single_user` or `multi_user` |
| `SINGLE_USER_API_KEY` | API key for single-user mode |
| `DATABASE_URL` | AuthNZ database URL |
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |

See `Docs/Published/Env_Vars.md` for the complete list.

## API Examples with curl

Once the server is running, you can interact with it using curl:

```bash
# Set your API key
export API_KEY="your-api-key-here"

# Check server health
curl -s http://127.0.0.1:8000/health

# List LLM providers
curl -s http://127.0.0.1:8000/api/v1/llm/providers \
  -H "X-API-KEY: $API_KEY" | jq

# Process media
curl -X POST http://127.0.0.1:8000/api/v1/media/process \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=VIDEO_ID"}'

# Chat completion (OpenAI-compatible)
curl -X POST http://127.0.0.1:8000/api/v1/chat/completions \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'

# Text-to-speech
curl -X POST http://127.0.0.1:8000/api/v1/audio/speech \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"kokoro","voice":"af_bella","input":"Hello from tldw_server"}' \
  --output speech.mp3
```

## Git Commands

Standard git operations for development:

```bash
# Check repository status
git status

# View recent commits
git log --oneline -10

# Create a feature branch
git checkout -b feature/my-feature

# Stage and commit changes
git add specific_file.py
git commit -m "Description of changes"
```

## Debugging

### Log Levels

The server uses Loguru for logging. Control verbosity through the config or environment:

```bash
# Set log level via environment
export LOG_LEVEL=DEBUG
python -m uvicorn tldw_Server_API.app.main:app --reload
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Port already in use | Change port: `--port 8001` |
| Database locked | Ensure single connection or use proper context managers |
| Missing API key | Check `.env` file or `Config_Files/config.txt` |
| FFmpeg not found | Install: `brew install ffmpeg` or `apt install ffmpeg` |

## See Also

- [Installation & Setup Guide](Installation-Setup-Guide.md)
- [Authentication Setup](Authentication_Setup.md)
- [API Documentation](../API-related/API_README.md)
- [TTS Getting Started](TTS_Getting_Started.md)
