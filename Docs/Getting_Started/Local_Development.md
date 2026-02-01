# Local Development Guide

This guide is for developers building applications against the tldw_server API. It covers provider configuration, development workflow, and API usage examples.

**Time to complete:** 15-30 minutes (depending on which providers you configure)

**Prerequisite:** Complete the [Tire Kicker Guide](./Tire_Kicker.md) first to have a running server.

---

## Configure LLM Providers

tldw_server supports 16+ LLM providers. Add their API keys to your `.env` file.

### Commercial Providers (Fastest Setup)

```bash
# Add to .env - uncomment the providers you want to use

# OpenAI (GPT-4, GPT-4o, etc.)
OPENAI_API_KEY=sk-...

# Anthropic (Claude)
ANTHROPIC_API_KEY=sk-ant-...

# Google (Gemini)
GOOGLE_API_KEY=...

# Groq (fast inference)
GROQ_API_KEY=gsk_...

# DeepSeek
DEEPSEEK_API_KEY=...

# Mistral
MISTRAL_API_KEY=...

# Cohere
COHERE_API_KEY=...
```

After adding keys, restart the server and verify:

```bash
# List configured providers
curl -H "X-API-KEY: YOUR_KEY" http://localhost:8000/api/v1/llm/providers

# Quick test - send a chat request
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "X-API-KEY: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"Say hello"}]}'
```

**Tip:** If the chat request fails with a provider error, check that your API key is valid.

### Local Models (Ollama)

For local inference without API costs:

```bash
# 1. Install Ollama: https://ollama.ai
# 2. Pull a model
ollama pull llama3.2

# 3. Add to .env
OLLAMA_API_IP=http://localhost:11434/v1/chat/completions

# 4. Use in requests
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "X-API-KEY: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"ollama/llama3.2","messages":[{"role":"user","content":"Hello"}]}'
```

### Other Local Backends

| Backend | Config Variable | Default URL |
|---------|----------------|-------------|
| llama.cpp | `LLAMA_API_IP` | `http://localhost:8080/v1/chat/completions` |
| Kobold.cpp | `KOBOLD_API_IP` | `http://localhost:5001/api/v1/generate` |
| vLLM | `VLLM_API_IP` | `http://localhost:8000/v1/chat/completions` |
| TabbyAPI | `TABBY_API_IP` | `http://localhost:5000/v1/chat/completions` |
| Oobabooga | `OOBA_API_IP` | `http://localhost:5000/v1/chat/completions` |

---

## Development Workflow

### Hot Reload Mode

For active development with auto-reload on code changes:

```bash
uvicorn tldw_Server_API.app.main:app --reload --host 127.0.0.1 --port 8000
```

### Mock Mode (No LLM Costs)

For testing without making real LLM API calls:

```bash
make server-up-dev
# This sets CHAT_FORCE_MOCK=1 which returns mock responses
```

### Running Tests

```bash
# All unit tests
python -m pytest -m unit -v

# Integration tests (requires running server)
python -m pytest -m integration -v

# E2E critical smoke tests
python -m pytest tldw_Server_API/tests/e2e/ --critical-only -v

# With coverage
python -m pytest --cov=tldw_Server_API --cov-report=term-missing
```

---

## API Usage Examples

### Chat Completions

**Python:**
```python
import httpx

response = httpx.post(
    "http://localhost:8000/api/v1/chat/completions",
    headers={"X-API-KEY": "your-api-key"},
    json={
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": "Explain RAG in one sentence"}],
        "stream": False
    }
)
print(response.json()["choices"][0]["message"]["content"])
```

**curl:**
```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "X-API-KEY: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

**JavaScript:**
```javascript
const response = await fetch("http://localhost:8000/api/v1/chat/completions", {
  method: "POST",
  headers: {
    "X-API-KEY": "your-api-key",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    model: "openai/gpt-4o-mini",
    messages: [{ role: "user", content: "Hello!" }]
  })
});
const data = await response.json();
console.log(data.choices[0].message.content);
```

### Streaming Responses

```python
import httpx

with httpx.stream(
    "POST",
    "http://localhost:8000/api/v1/chat/completions",
    headers={"X-API-KEY": "your-api-key"},
    json={
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": "Write a haiku"}],
        "stream": True
    }
) as response:
    for line in response.iter_lines():
        if line.startswith("data: "):
            print(line[6:], end="", flush=True)
```

### Embeddings

```bash
curl -X POST http://localhost:8000/api/v1/embeddings \
  -H "X-API-KEY: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "text-embedding-3-small",
    "input": "Hello, world!"
  }'
```

### Audio Transcription

```bash
curl -X POST http://localhost:8000/api/v1/audio/transcriptions \
  -H "X-API-KEY: YOUR_KEY" \
  -F "file=@audio.mp3" \
  -F "model=whisper-1"
```

### Media Ingestion

```bash
# Ingest a YouTube video
curl -X POST http://localhost:8000/api/v1/media/add \
  -H "X-API-KEY: YOUR_KEY" \
  -F "media_type=video" \
  -F "title=Example Video" \
  -F "urls=https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

**Note:** Media ingestion can take a while for long videos (transcription + processing).

---

## Debugging

### View Server Logs

Logs are printed to stdout by default. Look for:
- `[INFO]` - Normal operations
- `[WARNING]` - Non-critical issues
- `[ERROR]` - Errors requiring attention

### Common Debug Commands

```bash
# Check what providers are configured
curl -H "X-API-KEY: YOUR_KEY" http://localhost:8000/api/v1/llm/providers

# Check server config
curl http://localhost:8000/api/v1/config/quickstart

# Health check
curl http://localhost:8000/health
```

### Environment Variables for Debugging

```bash
# Enable debug logging
LOG_LEVEL=DEBUG uvicorn tldw_Server_API.app.main:app --reload

# Force mock responses (no LLM costs)
CHAT_FORCE_MOCK=1 uvicorn tldw_Server_API.app.main:app --reload
```

---

## Next Steps

- [Docker Self-Host Guide](./Docker_Self_Host.md) - Run on your home server
- [Production Guide](./Production.md) - Deploy for a team
- [API Documentation](http://localhost:8000/docs) - Full endpoint reference
- [RAG Guide](../User_Guides/RAG_Deployment_Guide.md) - Set up retrieval-augmented generation
