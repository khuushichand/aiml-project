# Offline / Air-Gapped Deployment

Guide for running tldw_server in environments with limited or no internet access.

## What Works Offline

The following features operate entirely locally and require no internet connection:

| Feature | Requirement |
|---------|------------|
| **Local LLM inference** | Llama.cpp, Kobold.cpp, Ollama, TabbyAPI, vLLM, Aphrodite (with pre-downloaded models) |
| **Local STT** | faster-whisper, NeMo Parakeet/Canary (with pre-downloaded models) |
| **Local TTS** | Kokoro ONNX (with pre-downloaded voice packs) |
| **SQLite databases** | All media, notes, chat, and auth databases |
| **ChromaDB** | Local vector storage and search |
| **Full-text search** | SQLite FTS5 (built-in) |
| **RAG pipeline** | Hybrid search with local embeddings |
| **Document processing** | PDF, EPUB, DOCX, Markdown, HTML, XML ingestion |
| **Chat history** | All conversation storage and retrieval |
| **Note-taking** | Full notebook functionality |
| **Character cards** | Load, edit, and use character cards |
| **API server** | FastAPI serves all endpoints locally |

## What Requires Internet

| Feature | Why |
|---------|-----|
| **Cloud LLM providers** | OpenAI, Anthropic, Cohere, Google, etc. require API access |
| **yt-dlp downloads** | Downloading video/audio from URLs |
| **Web search** | Research and web scraping endpoints |
| **Cloud embeddings** | OpenAI, Cohere, or other remote embedding providers |
| **Cloud TTS** | OpenAI TTS API |
| **Model downloads** | First-time download of STT/embedding/LLM models |
| **pip install** | Installing or updating Python dependencies |
| **Browser extension sync** | Extension communication with the server |

## Configuration for Offline Use

### 1. Disable Cloud Providers

In `Config_Files/config.txt`, comment out or remove cloud provider API keys:

```ini
[API]
# openai_api_key =
# anthropic_api_key =
# cohere_api_key =
```

Or set environment variables to empty:

```bash
export OPENAI_API_KEY=""
export ANTHROPIC_API_KEY=""
```

### 2. Configure Local LLM

Point to a local LLM server:

```ini
[Local-API]
llm_api_url = http://localhost:8080/v1
llm_api_key = not-needed

[LlamaCpp]
llm_api_url = http://localhost:8080
```

### 3. Use Local Embeddings

Configure a local embedding model (sentence-transformers):

```ini
[Embeddings]
provider = local
model = all-MiniLM-L6-v2
```

### 4. Use Local STT

```ini
[STT-Settings]
default_stt_provider = faster_whisper
whisper_model = medium
```

### 5. Disable External Features

```ini
[Search-Engines]
enabled = false

[Web-Scraping]
enabled = false
```

## Pre-Downloading Models

Before going offline, download all required models on a machine with internet access.

### STT Models (faster-whisper)

```python
from faster_whisper import WhisperModel
# This downloads and caches the model
model = WhisperModel("medium", device="cpu", compute_type="int8")
```

Models are cached in `~/.cache/huggingface/hub/`.

### Embedding Models

```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("all-MiniLM-L6-v2")
model.save("/path/to/offline/models/all-MiniLM-L6-v2")
```

Then configure:

```ini
[Embeddings]
provider = local
model = /path/to/offline/models/all-MiniLM-L6-v2
```

### LLM Models (Llama.cpp)

Download GGUF model files manually:

```bash
# Example: download a model from Hugging Face
wget https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf \
  -O /path/to/models/mistral-7b.gguf
```

### TTS Voice Packs (Kokoro)

```bash
pip download kokoro-onnx --no-deps -d /path/to/offline/packages/
# Install from local:
pip install /path/to/offline/packages/kokoro_onnx-*.whl
```

## Docker Image with Bundled Models

For fully air-gapped deployments, build a Docker image that includes models:

```dockerfile
FROM tldw-server:latest

# Copy pre-downloaded models
COPY ./models/whisper-medium /root/.cache/huggingface/hub/models--Systran--faster-whisper-medium/
COPY ./models/all-MiniLM-L6-v2 /app/models/all-MiniLM-L6-v2/
COPY ./models/mistral-7b.gguf /app/models/mistral-7b.gguf

# Configure for offline use
ENV OPENAI_API_KEY=""
ENV ANTHROPIC_API_KEY=""
```

Build and transfer:

```bash
docker build -t tldw-server-offline:latest .
docker save tldw-server-offline:latest | gzip > tldw-offline.tar.gz

# On the air-gapped machine:
docker load < tldw-offline.tar.gz
docker run -p 8000:8000 tldw-server-offline:latest
```

## Verification Checklist

After deploying offline, verify these capabilities:

- [ ] Server starts without errors (`/api/v1/health` returns 200)
- [ ] Local LLM responds (`/api/v1/chat/completions` with local model)
- [ ] Transcription works (`/api/v1/audio/transcriptions` with local file)
- [ ] Document ingestion works (upload a PDF)
- [ ] Search works (full-text and vector)
- [ ] Chat history persists across restarts
- [ ] Notes can be created and retrieved
