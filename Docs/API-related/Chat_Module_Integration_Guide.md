# Chat Module Integration Guide

## Overview
This guide documents the integration points for the refactored chat module components and how they interact with planned future modules.

### Chat Persistence (Ephemeral by default)
- By default, `/api/v1/chat/completions` requests are ephemeral and do not write messages to the database.
- To persist a chat, include `"save_to_db": true` in the request JSON. When set, the server creates/loads a conversation and stores messages and responses.
- You can change the server-wide default (without modifying clients):
  - Environment: `CHAT_SAVE_DEFAULT=true` (highest precedence)
  - Config file: `tldw_Server_API/Config_Files/config.txt`
    - Under `[Chat-Module]`: `chat_save_default = True`
  - Fallback legacy default (if neither is set): `[Auto-Save] save_character_chats`

Example persisted request:
```bash
curl -X POST "http://localhost:8000/api/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [{"role":"user","content":"Save this conversation."}],
    "save_to_db": true
  }'
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Chat Endpoint                         │
│                 (/chat/completions)                      │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                  Security Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Auth Utils   │  │Image Valid.  │  │Chat Validators│  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                  Business Logic                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │Chat Helpers  │  │Character Mgmt│  │Conversation   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                  Data Layer                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │Transaction   │  │Database      │  │Streaming      │  │
│  │Utils         │  │Operations    │  │Handler        │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Authentication (AuthNZ)
**Purpose**: Unified authentication/authorization for single-user and multi-user modes

**Key Components**:
- `get_request_user`: FastAPI dependency that authenticates requests and returns a `User`
  - Single-user: validates `X-API-KEY`
  - Multi-user: validates Bearer JWT or `X-API-KEY` (API key manager)
- `jwt_service.decode_access_token`: Verifies and decodes JWT access tokens
- `AuthNZ.settings.get_settings()`: Centralized configuration (mode, keys, algorithms)

**Integration Points**:
- Endpoints should use `Depends(get_request_user)` instead of legacy helpers
- For direct token verification in services, use `jwt_service.decode_access_token`
- Legacy `auth_utils.py` has been removed; use AuthNZ equivalents

### 2. Image Validation (`image_validation.py`)
**Purpose**: Secure image upload validation and processing

**Key Functions**:
- `validate_data_uri()`: Validate data URI format
- `estimate_decoded_size()`: Calculate decoded size without decoding
- `validate_image_url(url) -> (is_valid, mime_type, decoded_bytes)`: Accepts only data: URIs for security
- `safe_decode_base64_image(base64_data, mime_type) -> bytes|None`: Final decode with size/mime checks

**Future Integration**:
- **Malware Scanning Module** (Planned)
  - Hook point: After `safe_decode_base64_image()`
  - Interface: `async def scan_image(bytes, mime_type) -> bool`
- **Image Processing Module** (Future)
  - Resize, compress, format conversion
  - Thumbnail generation

### 3. Transaction Utils (`transaction_utils.py`)
**Purpose**: Database transaction management with retry logic

**Key Functions**:
- `db_transaction()`: Async context manager for transactions
- `@transactional`: Decorator for automatic transactions
- `save_conversation_with_messages()`: Atomic save operations

**Integration Points**:
- All database operations should use these utilities
- Integrates with future distributed transaction coordinator
- Works with database connection pooling

### 4. Streaming Utils (`streaming_utils.py`)
**Purpose**: Manage streaming responses with timeout and heartbeat

**Key Functions**:
- `StreamingResponseHandler`: Main streaming handler class
- `create_streaming_response_with_timeout()`: Create managed streams

**Future Integration**:
- **Task Management Module** (Planned)
  - Will replace internal task handling
  - Interface: `TaskManager.create_task()`, `TaskManager.cancel_task()`
- **WebSocket Module** (Future)
  - Real-time streaming over WebSocket
  - Shared heartbeat mechanism

### 5. Chat Helpers (`chat_helpers.py`)
**Purpose**: Business logic for chat operations

**Key Functions**:
- `validate_request_payload()`: Validate chat requests
- `get_or_create_character_context()`: Character management
- `prepare_llm_messages()`: Format messages for LLMs

**Integration Points**:
- Works with RAG system for context retrieval
- Integrates with prompt template system
- Connects to character management

### 6. Chat Validators (`chat_validators.py`)
**Purpose**: Comprehensive input validation

**Key Functions**:
- `validate_conversation_id()`: UUID/alphanumeric validation
- `validate_temperature()`: Parameter range validation
- `validate_request_size()`: Payload size limits

**Integration Points**:
- Used by all chat-related endpoints
- Can be extended for custom validation rules
- Works with rate limiting for request throttling

## Integration Examples

### Example 1: Adding Malware Scanning

```python
# In image_validation.py, inside safe_decode_base64_image():
# After final size check and before returning decoded bytes
# (Function signature in code: safe_decode_base64_image(base64_data: str, mime_type: str) -> Optional[bytes])

# INTEGRATION POINT: Add malware scanning here
if ENABLE_VIRUS_SCAN:
    from app.core.Security.malware_scanner import scan_image
    is_safe = await scan_image(decoded_data, mime_type)
    if not is_safe:
        logger.warning("Image failed security scan")
        return None
```

### Example 2: Integrating Task Management

```python
# In streaming_utils.py, within create_streaming_response_with_timeout():
# Replace direct asyncio.create_task scheduling with a TaskManager (if you have one).

# BEFORE (simplified):
stream_task = asyncio.create_task(stream_gen.__anext__())
heartbeat_task = asyncio.create_task(heartbeat_gen.__anext__())

# AFTER (conceptual):
task_manager = get_default_task_manager()  # your central task manager
stream_task = await task_manager.create_task(stream_gen.__anext__(), name=f"stream_{conversation_id}")
heartbeat_task = await task_manager.create_task(heartbeat_gen.__anext__(), name=f"heartbeat_{conversation_id}")
```

### Example 3: Hooking Rate Limiting into Chat Flow

```python
# Prefer integrating with the existing chat rate limiter (ConversationRateLimiter)
# In chat endpoint, before provider call:
allowed, error = await rate_limiter.check_rate_limit(user_id, conversation_id, estimated_tokens)
if not allowed:
    raise HTTPException(status_code=429, detail=error)
```

## Testing Integration

### Unit Testing
Representative tests can be added following the project’s pytest patterns. Current repository test coverage is evolving; use the suggested paths below as guidance when creating tests for new or refactored modules:
- `tests/AuthNZ/` for AuthNZ helpers
- `tests/Utils/` for utility modules (e.g., image validation)
- `tests/DB_Management/` for transactional helpers
- `tests/Chat/` for chat streaming and handlers

### Integration Testing
```python
import httpx
from httpx import ASGITransport

async def test_chat_completion_with_all_features(app):
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"X-API-KEY": "test-key"}
        payload = {
            "messages": [{"role": "user", "content": "Hello"}],
            "model": "openai/gpt-4o-mini",
            "stream": True
        }
        resp = await client.post("/api/v1/chat/completions", json=payload, headers=headers)
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("text/event-stream")
```

## Configuration

### Environment and Config
```bash
# Authentication (env)
AUTH_MODE=multi_user  # or single_user
SINGLE_USER_API_KEY=your-secret-key  # single_user mode
# For multi_user JWTs, configure JWT_* in AuthNZ settings (e.g., JWT_SECRET_KEY or RSA keys)

# Chat module settings come from tldw_Server_API/Config_Files/config.txt
# under the [Chat-Module] section (not env):
[
Chat-Module]
max_base64_image_size_mb = 3
streaming_idle_timeout_seconds = 300
streaming_heartbeat_interval_seconds = 30
rate_limit_per_minute = 60
rate_limit_per_user_per_minute = 20
rate_limit_per_conversation_per_minute = 10
rate_limit_tokens_per_minute = 10000
chat_save_default = False
```

### Feature Flags (Future)
```python
FEATURES = {
    "malware_scanning": False,  # Enable when module is ready
    "centralized_tasks": False,  # Enable when task manager is ready
    "websocket_streaming": False,  # Enable for WebSocket support
}
```

## Migration Guide

### For Existing Deployments

1. **Update imports** in `chat.py`:
```python
# Old
from app.core.Chat.old_functions import validate_token

# New (AuthNZ)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from fastapi import Depends
```

2. **Update database operations** to use transactions:
```python
# Old
db.add_message(message)
db.add_conversation(conversation)

# New
async with db_transaction(db):
    await save_conversation_with_messages(db, conversation, messages)
```

3. **Update streaming responses**:
```python
# Old
return StreamingResponse(generator)

# New
return create_streaming_response_with_timeout(
    stream=generator,
    conversation_id=conv_id,
    save_callback=save_func,
    idle_timeout=STREAMING_IDLE_TIMEOUT,            # from [Chat-Module] streaming_idle_timeout_seconds
    heartbeat_interval=STREAMING_HEARTBEAT_INTERVAL # from [Chat-Module] streaming_heartbeat_interval_seconds
)
```

## Performance Considerations

### Optimization Points
1. **Authentication**: Token validation is O(1) with constant-time comparison
2. **Image Validation**: Size estimation prevents memory exhaustion
3. **Transactions**: Retry logic reduces database contention
4. **Streaming**: Heartbeat prevents connection timeouts

### Benchmarks
- Authentication: <1ms per request
- Image validation: <10ms for 3MB image
- Transaction retry: 200ms backoff between retries
- Streaming heartbeat: 30-second intervals

## Security Considerations

### Security Features
1. **Timing Attack Prevention**: Constant-time token comparison
2. **Resource Exhaustion Prevention**: Pre-decode size validation
3. **SQL Injection Prevention**: Parameterized queries in transactions
4. **XSS Prevention**: Strict roles/content schemas; images only via validated data URIs

### Security Checklist
- [ ] Enable authentication in production
- [ ] Configure rate limiting
- [ ] Set appropriate size limits
- [ ] Enable HTTPS only
- [ ] Rotate API tokens regularly
- [ ] Monitor failed authentication attempts

## Troubleshooting

### Common Issues

1. **MRO Error in Tests**
   - **Cause**: Multiple inheritance from BaseModel
   - **Fix**: Remove BaseModel from classes using mixins

2. **Streaming Timeout**
   - **Cause**: No data sent within idle timeout
   - **Fix**: Adjust `[Chat-Module] streaming_idle_timeout_seconds` or ensure heartbeat is working

3. **Transaction Retry Exhausted**
   - **Cause**: Database contention
   - **Fix**: Increase `DB_TRANSACTION_RETRIES` or optimize queries

4. **Image Validation Failure**
   - **Cause**: Unsupported format or size
   - **Fix**: Check `ALLOWED_IMAGE_TYPES` and `MAX_IMAGE_SIZE`

## Future Roadmap

### Phase 1 (Current)
- ✅ Security hardening
- ✅ Code modularization
- ✅ Test coverage

### Phase 2 (Next)
- [ ] Centralized task management
- [ ] Malware scanning integration
- [ ] Enhanced rate limiting

### Phase 3 (Future)
- [ ] WebSocket streaming
- [ ] Distributed transactions
- [ ] Advanced caching layer

## Support

For questions or issues:
1. Check the troubleshooting section
2. Review test files for usage examples
3. Consult the API documentation
4. Open an issue on GitHub

---

*Last Updated: 2025-10-08*
*Version: 1.0.0*
