# Feedback API

The Feedback API collects explicit feedback on chat/RAG responses and implicit feedback signals from the Web UI.

Explicit feedback base path: `/api/v1/feedback`
Implicit feedback endpoint: `/api/v1/rag/feedback/implicit`

## Endpoints

- `POST /api/v1/feedback/explicit` - submit explicit feedback
- `POST /api/v1/rag/feedback/implicit` - submit implicit RAG feedback (click/expand/copy/dwell/citation)

## Explicit Feedback

`POST /api/v1/feedback/explicit`

Request: `ExplicitFeedbackRequest`

Required fields:
- `feedback_type` is required.
- `message_id` OR `query` is required.
- If `feedback_type=helpful`, `helpful` is required.
- If `feedback_type=relevance`, `relevance_score` (1-5) is required.

Example request:
```
{
  "conversation_id": "C_123",
  "message_id": "M_456",
  "feedback_type": "helpful",
  "helpful": true,
  "document_ids": ["doc_1"],
  "chunk_ids": ["chunk_9"],
  "corpus": "media_db",
  "issues": ["not_relevant"],
  "user_notes": "The answer was about a different feature.",
  "query": "how to reset auth",
  "session_id": "sess_abc123",
  "idempotency_key": "fb_01HXYZ"
}
```

Response:
```
{
  "ok": true,
  "feedback_id": "fb_01HXYZ"
}
```

## Implicit Feedback (RAG)

`POST /api/v1/rag/feedback/implicit`

Request: `ImplicitFeedbackEvent`

Example request:
```
{
  "event_type": "dwell_time",
  "query": "how to reset auth",
  "doc_id": "doc_1",
  "chunk_ids": ["chunk_9"],
  "rank": 2,
  "impression_list": ["doc_1", "doc_2", "doc_3"],
  "corpus": "media_db",
  "session_id": "sess_abc123",
  "conversation_id": "C_123",
  "message_id": "M_456",
  "dwell_ms": 3000
}
```

Response:
```
{"ok": true}
```

If implicit feedback is disabled by config:
```
{"ok": true, "disabled": true}
```

## Core Objects

### ExplicitFeedbackRequest

```
{
  "conversation_id": "C_123",
  "message_id": "M_456",
  "feedback_type": "helpful",
  "helpful": true,
  "relevance_score": 4,
  "document_ids": ["doc_1"],
  "chunk_ids": ["chunk_9"],
  "corpus": "media_db",
  "issues": ["not_relevant"],
  "user_notes": "...",
  "query": "how to reset auth",
  "session_id": "sess_abc123",
  "idempotency_key": "fb_01HXYZ"
}
```

### ImplicitFeedbackEvent

```
{
  "event_type": "click",
  "query": "how to reset auth",
  "doc_id": "doc_1",
  "chunk_ids": ["chunk_9"],
  "rank": 2,
  "impression_list": ["doc_1", "doc_2"],
  "corpus": "media_db",
  "user_id": "user_123",
  "session_id": "sess_abc123",
  "conversation_id": "C_123",
  "message_id": "M_456",
  "dwell_ms": 3000
}
```
