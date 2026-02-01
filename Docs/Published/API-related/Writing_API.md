# Writing Playground API

The Writing API supports sessions, templates, themes, token utilities, and wordcloud generation for the writing playground.

Base path: `/api/v1/writing`

## Endpoints

- `GET /version` - API version
- `GET /capabilities` - provider/model capabilities
- `GET /sessions` - list sessions
- `POST /sessions` - create session
- `GET /sessions/{session_id}` - get session
- `PATCH /sessions/{session_id}` - update session (requires `expected_version` header)
- `DELETE /sessions/{session_id}` - delete session (requires `expected_version` header)
- `POST /sessions/{session_id}/clone` - clone session
- `GET /templates` - list templates
- `POST /templates` - create template
- `GET /templates/{name}` - get template
- `PATCH /templates/{name}` - update template (requires `expected_version` header)
- `DELETE /templates/{name}` - delete template (requires `expected_version` header)
- `GET /themes` - list themes
- `POST /themes` - create theme
- `GET /themes/{name}` - get theme
- `PATCH /themes/{name}` - update theme (requires `expected_version` header)
- `DELETE /themes/{name}` - delete theme (requires `expected_version` header)
- `POST /tokenize` - tokenize text
- `POST /token-count` - count tokens
- `POST /wordclouds` - create wordcloud (async)
- `GET /wordclouds/{wordcloud_id}` - fetch wordcloud status/result

## WritingSessionResponse

```
{
  "id": "sess_abc",
  "name": "Research draft",
  "payload": {"blocks": []},
  "schema_version": 1,
  "version_parent_id": null,
  "created_at": "2026-01-29T10:00:00Z",
  "last_modified": "2026-01-29T10:10:00Z",
  "deleted": false,
  "client_id": "user_123",
  "version": 2
}
```

## Sessions

Create:
`POST /api/v1/writing/sessions`

Request:
```
{
  "name": "Research draft",
  "payload": {"blocks": []},
  "schema_version": 1
}
```

Update:
`PATCH /api/v1/writing/sessions/{session_id}`

Headers:
- `expected_version: 2`

Request:
```
{
  "name": "Research draft v2",
  "payload": {"blocks": [{"type": "text", "value": "..."}]}
}
```

Delete:
`DELETE /api/v1/writing/sessions/{session_id}` with `expected_version` header.

Clone:
`POST /api/v1/writing/sessions/{session_id}/clone`

## Templates

Templates mirror session payloads. Endpoints and request bodies match the `WritingTemplate*` schemas.

Example create:
```
POST /api/v1/writing/templates
{
  "name": "Blog post",
  "payload": {"blocks": []},
  "schema_version": 1,
  "is_default": true
}
```

## Themes

Themes store CSS and styling metadata.

Example create:
```
POST /api/v1/writing/themes
{
  "name": "Serif",
  "class_name": "theme-serif",
  "css": ".editor { font-family: serif; }",
  "schema_version": 1,
  "is_default": false,
  "order": 10
}
```

## Tokenize

`POST /api/v1/writing/tokenize`

Request:
```
{
  "provider": "openai",
  "model": "gpt-4o",
  "text": "Hello world",
  "options": {"include_strings": true}
}
```

Response:
```
{
  "ids": [123, 456],
  "strings": ["Hello", " world"],
  "meta": {
    "provider": "openai",
    "model": "gpt-4o",
    "tokenizer": "o200k_base",
    "input_chars": 11,
    "token_count": 2,
    "warnings": []
  }
}
```

## Wordclouds

Create:
`POST /api/v1/writing/wordclouds`

Request:
```
{
  "text": "tokenize this text for a wordcloud",
  "options": {"max_words": 50, "min_word_length": 3}
}
```

Response (queued):
```
{
  "id": "<hash>",
  "status": "queued",
  "cached": false
}
```

Poll:
`GET /api/v1/writing/wordclouds/{wordcloud_id}`

Response (ready):
```
{
  "id": "<hash>",
  "status": "ready",
  "cached": true,
  "result": {
    "words": [{"text": "token", "weight": 12}],
    "meta": {"input_chars": 120, "total_tokens": 30, "top_n": 50}
  }
}
```
