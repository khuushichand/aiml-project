# Character Chat API Documentation

## Overview

The Character Chat API provides comprehensive endpoints for managing character-based chat sessions, messages, and interactions. This API enables creating persistent conversations with AI characters, managing message history, and performing character-specific completions.

Implementation status: Character CRUD, chat sessions, messages, search, export, and rate limiting are implemented. Character-specific LLM responses are performed via the core Chat API (`POST /api/v1/chat/completions`) using conversation context from character chats.

## Table of Contents

1. [Authentication](#authentication)
2. [Character Management](#character-management)
3. [Chat Session Management](#chat-session-management)
4. [Message Management](#message-management)
5. [Chat Completions](#chat-completions)
6. [Search and Filtering](#search-and-filtering)
7. [Export/Import](#exportimport)
8. [Rate Limiting](#rate-limiting)
9. [Error Handling](#error-handling)

---

## Authentication

Supported headers:
- Single-user: `X-API-KEY: <key>`
- Multi-user: `Authorization: Bearer <JWT>`

If authentication is required and missing/invalid, endpoints return `401`.

---

## Character Management

### Create Character

Create a new character card.

**Endpoint:** `POST /api/v1/characters/`

**Request Body:**
```json
{
  "name": "Assistant",
  "description": "A helpful AI assistant",
  "personality": "Friendly and knowledgeable",
  "first_message": "Hello! How can I help you today?",
  "scenario": "You are chatting with a helpful assistant",
  "example_messages": [
    {"role": "user", "content": "What can you do?"},
    {"role": "assistant", "content": "I can help with various tasks!"}
  ],
  "tags": ["assistant", "helpful"]
}
```

**Response:** `201 Created`
```json
{
  "id": 1,
  "name": "Assistant",
  "description": "A helpful AI assistant",
  "personality": "Friendly and knowledgeable",
  "first_message": "Hello! How can I help you today?",
  "created_at": "2024-09-04T12:00:00Z",
  "updated_at": "2024-09-04T12:00:00Z",
  "version": 1
}
```

### Get Character

Retrieve a specific character by ID.

**Endpoint:** `GET /api/v1/characters/{character_id}`

**Response:** `200 OK`
```json
{
  "id": 1,
  "name": "Assistant",
  "description": "A helpful AI assistant",
  "personality": "Friendly and knowledgeable",
  "first_message": "Hello! How can I help you today?",
  "scenario": "You are chatting with a helpful assistant",
  "example_messages": [...],
  "tags": ["assistant", "helpful"],
  "created_at": "2024-09-04T12:00:00Z",
  "updated_at": "2024-09-04T12:00:00Z",
  "version": 1
}
```

### List Characters

Get a paginated list of characters.

**Endpoint:** `GET /api/v1/characters/`

**Query Parameters:**
- `limit` (int, default: 100, max: 1000): Number of characters to return
- `offset` (int, default: 0): Number of characters to skip

**Response:** `200 OK`
```json
{
  "characters": [...],
  "total": 50,
  "limit": 20,
  "offset": 0
}
```

### Update Character

Update an existing character's information.

**Endpoint:** `PUT /api/v1/characters/{character_id}?expected_version={version}`

**Query Parameters:**
- `expected_version` (int, required): Expected version for optimistic locking

**Request Body:**
```json
{
  "name": "Updated Assistant",
  "description": "An even more helpful AI assistant"
}
```

**Response:** `200 OK`
```json
{
  "id": 1,
  "name": "Updated Assistant",
  "description": "An even more helpful AI assistant",
  "version": 2,
  ...
}
```

### Delete Character

Soft delete a character (marks as deleted but preserves data).

**Endpoint:** `DELETE /api/v1/characters/{character_id}?expected_version={version}`

**Response:** `204 No Content`

---

## Chat Session Management

### Create Chat Session

Start a new chat session with a character.

**Endpoint:** `POST /api/v1/chats/`

**Request Body:**
```json
{
  "character_id": 1,
  "title": "Evening Chat",
  "parent_conversation_id": null
}
```

**Response:** `201 Created`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "character_id": 1,
  "title": "Evening Chat",
  "rating": null,
  "created_at": "2024-09-04T12:00:00Z",
  "last_modified": "2024-09-04T12:00:00Z",
  "message_count": 0,
  "version": 1
}
```

### Get Chat Session

Retrieve a specific chat session.

**Endpoint:** `GET /api/v1/chats/{chat_id}`

**Response:** `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "character_id": 1,
  "title": "Evening Chat",
  "rating": null,
  "created_at": "2024-09-04T12:00:00Z",
  "last_modified": "2024-09-04T12:00:00Z",
  "message_count": 5,
  "version": 1
}
```

### List User Chats

Get all chat sessions for the current user.

**Endpoint:** `GET /api/v1/chats/`

**Query Parameters:**
- `character_id` (int): Filter by character
- `limit` (int, default: 50): Number of chats to return
- `offset` (int, default: 0): Number of chats to skip

**Response:** `200 OK`
```json
{
  "chats": [...],
  "total": 10,
  "limit": 20,
  "offset": 0
}
```

### Update Chat Session

Update chat session metadata.

**Endpoint:** `PUT /api/v1/chats/{chat_id}`

**Query Parameters:**
- `expected_version` (int, required): Expected version for optimistic locking

**Request Body:**
```json
{
  "title": "Updated Chat Title",
  "rating": 5
}
```

**Response:** `200 OK`

### Delete Chat Session

Soft delete a chat session.

**Endpoint:** `DELETE /api/v1/chats/{chat_id}?expected_version={version}` (version optional)

**Response:** `204 No Content`

---

## Message Management

### Send Message

Add a new message to a chat session.

**Endpoint:** `POST /api/v1/chats/{chat_id}/messages`

**Request Body:**
```json
{
  "role": "user",
  "content": "Hello! Tell me about yourself.",
  "parent_message_id": null,
  "image_base64": null
}
```

**Response:** `201 Created`
```json
{
  "id": "msg_123456",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "parent_message_id": null,
  "sender": "user",
  "content": "Hello! Tell me about yourself.",
  "timestamp": "2024-09-04T12:00:00Z",
  "ranking": null,
  "has_image": false,
  "version": 1
}
```

### Get Messages

Retrieve messages from a chat session, with optional character context for AI completions.

**Endpoint:** `GET /api/v1/chats/{chat_id}/messages`

**Query Parameters:**
- `limit` (int, default: 50): Number of messages to return
- `offset` (int, default: 0): Number of messages to skip
- `include_deleted` (bool, default: false): Include soft-deleted messages
- `include_character_context` (bool, default: false): Include character personality information
- `format_for_completions` (bool, default: false): Format response for use with `/api/v1/chat/completions`

**Response:** `200 OK`

Standard format:
```json
{
  "messages": [
    {
      "id": "msg_123456",
      "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
      "sender": "user",
      "content": "Hello!",
      "timestamp": "2024-09-04T12:00:00Z",
      "version": 1
    },
    {
      "id": "msg_123457",
      "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
      "sender": "assistant",
      "content": "Hello! I'm your helpful assistant.",
      "timestamp": "2024-09-04T12:00:05Z",
      "version": 1
    }
  ],
  "total": 2,
  "limit": 50,
  "offset": 0
}
```

With `format_for_completions=true&include_character_context=true`:
```json
{
  "character_name": "Assistant",
  "character_id": 1,
  "chat_id": "550e8400-e29b-41d4-a716-446655440000",
  "messages": [
    {
      "role": "system",
      "content": "You are Assistant.\nA helpful AI assistant.\nFriendly and knowledgeable."
    },
    {
      "role": "user",
      "content": "Hello!"
    },
    {
      "role": "assistant",
      "content": "Hello! I'm your helpful assistant."
    }
  ],
  "total": 2,
  "usage_instructions": "Use these messages with POST /api/v1/chat/completions"
}
```

### Get Chat Context (compact)

Return compact context for a chat, including character name and messages formatted for completions when available.

**Endpoint:** `GET /api/v1/chats/{chat_id}/context`

**Response:** `200 OK`
```json
{
  "character_name": "Assistant",
  "messages": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"}
  ]
}
```

### Get Specific Message

Retrieve a single message by ID.

**Endpoint:** `GET /api/v1/messages/{message_id}`

**Response:** `200 OK`

### Edit Message

Edit the content of an existing message.

**Endpoint:** `PUT /api/v1/messages/{message_id}?expected_version={version}`

**Request Body:**
```json
{
  "content": "Updated message content"
}
```

**Response:** `200 OK`

### Delete Message

Soft delete a message.

**Endpoint:** `DELETE /api/v1/messages/{message_id}?expected_version={version}`

**Response:** `204 No Content`

### Search Messages

Search for messages within a chat session.

**Endpoint:** `GET /api/v1/chats/{chat_id}/messages/search`

**Query Parameters:**
- `query` (string, required): Search query
- `limit` (int, default: 50): Maximum results

**Response:** `200 OK`
```json
{
  "messages": [...],
  "total": 5,
  "limit": 50,
  "offset": 0
}
```

---

## Chat Completions

To generate AI responses in character chat sessions, use the main OpenAI-compatible chat completions endpoint:

**Endpoint:** `POST /api/v1/chat/completions`

This endpoint supports:
- Multiple LLM providers (OpenAI, Anthropic, local models, etc.)
- Streaming responses
- System prompts for character personality
- Conversation history
- Ephemeral or persistent operation (see `save_to_db` below)

### Workflow for Character Chat Completions

1. **Get formatted messages from the chat session:**
```bash
curl -X GET "http://localhost:8000/api/v1/chats/{chat_id}/messages?format_for_completions=true&include_character_context=true" \
  -H "X-API-KEY: your-api-key"
```

2. **Use the formatted messages with the completions endpoint:**
```bash
curl -X POST "http://localhost:8000/api/v1/chat/completions" \
  -H "X-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
 -d '{
    "model": "gpt-3.5-turbo",
    "messages": [messages from step 1],
    "temperature": 0.7,
    "max_tokens": 500
  }'
```

By default, chats are ephemeral (not saved). To persist conversation/messages automatically, add `"save_to_db": true` to the request body:

```bash
curl -X POST "http://localhost:8000/api/v1/chat/completions" \
  -H "X-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [messages from step 1],
    "save_to_db": true
  }'
```

Server default for persistence can be configured via environment variable `CHAT_SAVE_DEFAULT=true` or in `Config_Files/config.txt` under `[Chat-Module]` with `chat_save_default = True`.

3. **Save the AI response as a new message (optional):**
```bash
curl -X POST "http://localhost:8000/api/v1/chats/{chat_id}/messages" \
  -H "X-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "assistant",
    "content": "[AI response from step 2]"
  }'
```

See the main [Chat API documentation](/api/v1/docs#/chat) for complete details on the chat completions endpoint.

Also see: `Docs/API-related/Chat_API_Documentation.md` for a focused Chat API reference.

---

## Search and Filtering

### Search Characters

Search for characters by name, description, or tags.

**Endpoint:** `GET /api/v1/characters/search/`

**Query Parameters:**
- `q` (string, required): Search query
- `limit` (int, default: 20): Maximum results

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "name": "Assistant",
    "description": "A helpful AI assistant",
    "tags": ["assistant", "helpful"],
    ...
  }
]
```

### Filter by Tags

Filter characters by specific tags.

**Endpoint:** `GET /api/v1/characters/filter`

**Query Parameters:**
- `tags` (array): List of tags to filter by (passed as multiple query params)
- `match_all` (bool, default: false): If true, require all tags; if false, match any tag
- `limit` (int, default: 50, max: 200): Maximum results
- `offset` (int, default: 0): Pagination offset

**Response:** `200 OK`
```json
[
  {
    "id": 2,
    "name": "Wizard",
    "description": "A wise wizard",
    "tags": ["fantasy", "wizard", "magic"],
    ...
  }
]
```

---

## Export/Import

### Export Character

Export a character in various formats.

**Endpoint:** `GET /api/v1/characters/{character_id}/export`

**Query Parameters:**
- `format` (string, default: "v3"): Export format ("v3", "v2", or "json")
- `include_world_books` (bool, default: false): Include associated world books

**Response:** `200 OK`

For V3 format:
```json
{
  "spec": "chara_card_v3",
  "spec_version": "3.0",
  "data": {
    "name": "Assistant",
    "description": "A helpful AI assistant",
    "personality": "Friendly and knowledgeable",
    "scenario": "You are chatting with a helpful assistant",
    "first_mes": "Hello! How can I help you today?",
    "mes_example": "Example conversation",
    "creator_notes": "Notes from creator",
    "system_prompt": "System instructions",
    "post_history_instructions": "Additional instructions",
    "alternate_greetings": [],
    "tags": ["assistant", "helpful"],
    "creator": "Author name",
    "character_version": "1.0",
    "extensions": {}
  }
}
```

### Export Chat History

Export a chat session's history.

**Endpoint:** `GET /api/v1/chats/{chat_id}/export`

**Query Parameters:**
- `format` (string, default: "json"): Export format ("json", "markdown", or "text")
- `include_metadata` (bool, default: true): Include chat metadata
- `include_character` (bool, default: true): Include character information

**Response:** `200 OK`

For JSON format:
```json
{
  "chat_id": "550e8400-e29b-41d4-a716-446655440000",
  "character_name": "Assistant",
  "character_id": 1,
  "title": "Evening Chat",
  "created_at": "2024-09-04T12:00:00Z",
  "messages": [
    {
      "id": "msg_123456",
      "sender": "user",
      "content": "Hello!",
      "timestamp": "2024-09-04T12:00:00Z"
    },
    {
      "id": "msg_123457",
      "sender": "assistant",
      "content": "Hello! How can I help you?",
      "timestamp": "2024-09-04T12:00:05Z"
    }
  ],
  "metadata": {
    "version": 1,
    "message_count": 2
  }
}
```

For Markdown format, returns a plain text markdown representation of the conversation.

### Import Character

Import a character from various formats including V3.

**Endpoint:** `POST /api/v1/characters/import`

**Request:** Multipart form data
- `character_file`: Character card file (supports PNG, WEBP, JSON, MD formats)

**Response:** `201 Created`
```json
{
  "id": 1,
  "name": "Imported Character",
  "message": "Character 'Imported Character' imported successfully"
}
```

**Note:** The endpoint automatically detects the format. For JSON files, it supports Character Card V3 format among others.

---

## Rate Limiting

The API implements several rate limits to prevent abuse:

### Character Operations
- **Max operations per hour**: 100 per user
- **Max characters per user**: 1000
- **Max import file size**: 10MB

### Chat Operations
- **Max concurrent chats per user**: 100
- **Max messages per chat**: 1000
- **Max chat completions per minute**: 20
- **Max message sends per minute**: 60

### Checking Rate Limit Status

To check your current rate limit usage:

**Endpoint:** `GET /api/v1/characters/rate-limit-status`

**Response:** `200 OK`
```json
{
  "operations_remaining": 95,
  "operations_limit": 100,
  "reset_time": "2024-09-04T13:00:00Z",
  "characters_count": 15,
  "characters_limit": 1000
}
```

When rate limited, the API returns `429 Too Many Requests`:
```json
{
  "detail": "Rate limit exceeded. Max 20 chat completions per minute."
}
```

**Note:** Rate limit information is not currently returned in response headers. Use the rate limit status endpoint to check your usage.

---

## Error Handling

The API uses standard HTTP status codes and returns detailed error messages:

### Common Status Codes

- `200 OK`: Successful GET/PUT request
- `201 Created`: Successful POST request creating new resource
- `204 No Content`: Successful DELETE request
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Missing or invalid authentication
- `403 Forbidden`: Authenticated but not authorized for resource
- `404 Not Found`: Resource doesn't exist
- `409 Conflict`: Version conflict (optimistic locking)
- `422 Unprocessable Entity`: Validation error
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

### Error Response Format

```json
{
  "detail": "Detailed error message",
  "error": "ErrorType",
  "chat_id": "optional-related-chat-id",
  "message_id": "optional-related-message-id"
}
```

### Optimistic Locking

Many update/delete operations require an `expected_version` parameter to prevent concurrent modification conflicts. If the version doesn't match, a `409 Conflict` error is returned:

```json
{
  "detail": "Version mismatch. Expected 2, found 3"
}
```

---

## Usage Examples

### Complete Chat Flow Example

1. **Create a character:**
```bash
curl -X POST "http://localhost:8000/api/v1/characters/" \
  -H "X-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Helper",
    "description": "A helpful assistant",
    "personality": "Friendly",
    "first_message": "Hello!"
  }'
```

2. **Create a chat session:**
```bash
curl -X POST "http://localhost:8000/api/v1/chats/" \
  -H "X-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "character_id": 1,
    "title": "My Chat"
  }'
```

3. **Send a message:**
```bash
curl -X POST "http://localhost:8000/api/v1/chats/{chat_id}/messages" \
  -H "X-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "Hello!"
  }'
```

4. **Get AI response using chat completions:**
```bash
curl -X POST "http://localhost:8000/api/v1/chat/completions" \
  -H "X-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "How are you?"}
    ],
    "max_tokens": 150
  }'
```

5. **Export chat history:**
```bash
curl -X GET "http://localhost:8000/api/v1/chats/{chat_id}/export?format=markdown" \
  -H "X-API-KEY: your-api-key"
```

### Python Client Example

```python
import requests
import json

class CharacterChatClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
    
    def create_character(self, name, description, personality, first_message):
        response = requests.post(
            f"{self.base_url}/api/v1/characters/",
            headers=self.headers,
            json={
                "name": name,
                "description": description,
                "personality": personality,
                "first_message": first_message
            }
        )
        return response.json()
    
    def create_chat(self, character_id, title=None):
        response = requests.post(
            f"{self.base_url}/api/v1/chats/",
            headers=self.headers,
            json={
                "character_id": character_id,
                "title": title
            }
        )
        return response.json()
    
    def send_message(self, chat_id, content, role="user"):
        """Send a message to a chat session."""
        response = requests.post(
            f"{self.base_url}/api/v1/chats/{chat_id}/messages",
            headers=self.headers,
            json={
                "role": role,
                "content": content
            }
        )
        return response.json()
    
    def get_messages_for_completions(self, chat_id):
        """Get messages formatted for use with chat completions."""
        response = requests.get(
            f"{self.base_url}/api/v1/chats/{chat_id}/messages",
            headers=self.headers,
            params={
                "format_for_completions": True,
                "include_character_context": True,
                "limit": 50
            }
        )
        return response.json()
    
    def get_completion(self, chat_id, message, max_tokens=500):
        # First get the formatted messages with character context
        context = self.get_messages_for_completions(chat_id)
        
        # Add the new message
        messages = context["messages"]
        messages.append({"role": "user", "content": message})
        
        # Call the main chat completions endpoint
        response = requests.post(
            f"{self.base_url}/api/v1/chat/completions",
            headers=self.headers,
            json={
                "model": "gpt-3.5-turbo",
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.7
            }
        )
        
        # Extract the response
        result = response.json()
        if "choices" in result and len(result["choices"]) > 0:
            ai_response = result["choices"][0]["message"]["content"]
            
            # Save the AI response back to the conversation
            self.send_message(chat_id, ai_response, role="assistant")
            
            return {
                "response": ai_response,
                "usage": result.get("usage", {})
            }
        return result

# Usage
client = CharacterChatClient("http://localhost:8000", "your-api-key")

# Create a character
character = client.create_character(
    name="Assistant",
    description="A helpful AI assistant",
    personality="Friendly and knowledgeable",
    first_message="Hello! How can I help you?"
)

# Start a chat
chat = client.create_chat(character["id"], "Evening Chat")

# Send message
message = client.send_message(chat["id"], "Hello!")

# Get AI response through chat completions
response = client.get_completion(chat["id"], "Tell me a joke")
if "response" in response:
    print(response["response"])
else:
    print("Error getting completion:", response)
```

---

## Related Documentation

- Core Chat API: `Docs/API-related/Chat_API_Documentation.md`
- Chatbook features (dictionaries, documents, import/export): `Docs/API-related/Chatbook_Features_API_Documentation.md`

---

## Notes

- All timestamps are in UTC ISO 8601 format
- Character IDs are integers
- Chat and message IDs are UUIDs
- Soft deletes preserve data but mark as deleted
- Optimistic locking prevents concurrent modification conflicts
- Rate limits are per-user, not per-API-key
- Streaming responses use Server-Sent Events (SSE)

---

## Version History

- **v1.0.0** (2024-09-04): Initial release with complete character chat API

---

*For more information about the tldw_server project, visit the [main documentation](README.md).*
