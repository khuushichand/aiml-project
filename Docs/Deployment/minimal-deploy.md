# Minimal Deployment Profile

## Overview
tldw_server supports a minimal deployment mode using only SQLite for storage,
with no Redis or PostgreSQL required. This is suitable for:
- Single-user self-hosted deployments
- Development and testing
- Resource-constrained environments

## Configuration

### Environment Variables
```bash
AUTH_MODE=single_user
DATABASE_URL=sqlite:///./Databases/users.db
REDIS_ENABLED=false
```

### What's Included
- Full API functionality
- SQLite for all databases (AuthNZ, Media, Notes, Audit)
- In-memory cache (replaces Redis)
- All LLM providers
- Audio transcription and TTS

### What's Not Included
- Distributed rate limiting (in-memory only)
- Multi-node scaling (single instance)
- MFA (requires PostgreSQL)
- Persistent cache across restarts

## Minimum Hardware Requirements
- CPU: 2 cores
- RAM: 4GB (8GB recommended for transcription)
- Disk: 10GB + storage for media files
- OS: Linux or macOS

## Quick Start

```bash
# Install
pip install -e .

# Configure
cp tldw_Server_API/Config_Files/.env.example tldw_Server_API/Config_Files/.env
# Edit .env: set AUTH_MODE=single_user, add API keys

# Initialize auth
python -m tldw_Server_API.app.core.AuthNZ.initialize

# Start
python -m uvicorn tldw_Server_API.app.main:app --host 0.0.0.0 --port 8000
```

## Docker (Minimal)

```yaml
services:
  tldw:
    build: .
    ports:
      - "8000:8000"
    environment:
      - AUTH_MODE=single_user
      - DATABASE_URL=sqlite:///./Databases/users.db
      - REDIS_ENABLED=false
    volumes:
      - ./data:/app/Databases
```

No Redis or PostgreSQL services needed.

## Upgrading to Full Profile
To add Redis and PostgreSQL later:
1. Set `REDIS_URL=redis://redis:6379`
2. Set `DATABASE_URL=postgresql://...`
3. Add Redis and PostgreSQL to docker-compose
4. Restart the server
