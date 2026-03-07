# Chat Workflows API

The Chat Workflows module provides a structured, user-facing Q&A flow on top of the chat stack. It is designed for guided interviews and intake flows where the server controls the question order, persists each answer as structured data, and only hands off to free chat when the workflow is finished.

## Overview

- Base path: `/api/v1/chat-workflows`
- OpenAPI tag: `chat-workflows`
- Authentication:
  - Single-user: `X-API-KEY: <key>`
  - Multi-user: `Authorization: Bearer <JWT>`
- Permission split:
  - `chat_workflows.read`
  - `chat_workflows.write`
  - `chat_workflows.run`

## Core Behavior

- Templates are linear step definitions with one authored `base_question` per step.
- Runs are immutable snapshots. Starting a run freezes the template or draft so later template edits do not change the in-flight session.
- Two question modes are supported:
  - `stock`: display the authored question directly.
  - `llm_phrased`: ask the renderer to rephrase the question while preserving authored intent.
- Completion is stop-by-default. Free chat requires an explicit `continue-chat` call after the run reaches `completed`.
- Access control is ownership-scoped for non-admin users. Missing or inaccessible templates/runs return `404`.

## Context Rules

Chat Workflows keeps context explicit in v1:

- `selected_context_refs` is stored on the run.
- `context_refs` is stored on each template step.
- Prior workflow answers are fed back into question rendering.

Implementation note:

- `generate-draft` accepts `context_refs`, but the current draft generator only uses `goal`, `base_question`, and `desired_step_count`.
- The current renderer persists run-level context selections, but broad external context resolution remains intentionally limited in this first version.

## Data Model Summary

### Template

```json
{
  "id": 12,
  "title": "Discovery",
  "description": "Collect implementation context",
  "version": 2,
  "status": "active",
  "steps": [
    {
      "id": "goal",
      "step_index": 0,
      "label": "Goal",
      "base_question": "What outcome are we aiming for?",
      "question_mode": "stock",
      "phrasing_instructions": null,
      "context_refs": []
    }
  ]
}
```

### Run

```json
{
  "run_id": "7eaf4f52-31f4-40f3-992f-2c5d23757b54",
  "template_id": 12,
  "template_version": 2,
  "status": "active",
  "current_step_index": 0,
  "selected_context_refs": [],
  "current_question": "What outcome are we aiming for?",
  "answers": []
}
```

## Endpoints

### Templates

- Create template: `POST /api/v1/chat-workflows/templates`
- List templates: `GET /api/v1/chat-workflows/templates`
- Get template: `GET /api/v1/chat-workflows/templates/{template_id}`
- Update template: `PUT /api/v1/chat-workflows/templates/{template_id}`
- Delete template: `DELETE /api/v1/chat-workflows/templates/{template_id}`

#### Create Template Example

```bash
curl -X POST "http://localhost:8000/api/v1/chat-workflows/templates" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{
    "title": "Discovery",
    "description": "Collect implementation context",
    "version": 1,
    "steps": [
      {
        "id": "goal",
        "step_index": 0,
        "label": "Goal",
        "base_question": "What outcome are we aiming for?",
        "question_mode": "stock",
        "context_refs": []
      }
    ]
  }'
```

Notes:

- `title` and every `base_question` are required.
- Updating `title`, `description`, or `steps` increments the template version.
- `status` supports `active` and `archived`.

### Draft Generation

- Generate draft: `POST /api/v1/chat-workflows/generate-draft`

#### Generate Draft Example

```bash
curl -X POST "http://localhost:8000/api/v1/chat-workflows/generate-draft" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{
    "goal": "Prepare an implementation brief for chat workflows",
    "base_question": "What outcome should this workflow produce?",
    "desired_step_count": 4,
    "context_refs": []
  }'
```

Response shape:

```json
{
  "template_draft": {
    "title": "Prepare an implementation brief for chat workflows",
    "description": "Generated workflow for Prepare an implementation brief for chat workflows",
    "version": 1,
    "steps": [
      {
        "id": "step-1",
        "step_index": 0,
        "label": "Step 1",
        "base_question": "What outcome should this workflow produce?",
        "question_mode": "stock",
        "context_refs": []
      }
    ]
  }
}
```

### Runs

- Start run: `POST /api/v1/chat-workflows/runs`
- Get run: `GET /api/v1/chat-workflows/runs/{run_id}`
- Get run transcript: `GET /api/v1/chat-workflows/runs/{run_id}/transcript`
- Submit answer: `POST /api/v1/chat-workflows/runs/{run_id}/answer`
- Cancel run: `POST /api/v1/chat-workflows/runs/{run_id}/cancel`
- Continue into free chat: `POST /api/v1/chat-workflows/runs/{run_id}/continue-chat`

### Start Run Rules

Provide exactly one of:

- `template_id`
- `template_draft`

Optional fields:

- `selected_context_refs`
- `question_renderer_model`

#### Start From Saved Template

```bash
curl -X POST "http://localhost:8000/api/v1/chat-workflows/runs" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{
    "template_id": 12,
    "selected_context_refs": []
  }'
```

#### Start From Draft Snapshot

```bash
curl -X POST "http://localhost:8000/api/v1/chat-workflows/runs" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{
    "template_draft": {
      "title": "Ad hoc intake",
      "version": 1,
      "steps": [
        {
          "id": "goal",
          "step_index": 0,
          "label": "Goal",
          "base_question": "What are we trying to learn?",
          "question_mode": "stock",
          "context_refs": []
        }
      ]
    },
    "selected_context_refs": []
  }'
```

### Transcript Behavior

`GET /runs/{run_id}/transcript` returns structured assistant/user messages derived from persisted answers. If the run is still active, the current unanswered assistant prompt is appended at the end.

Example response:

```json
{
  "run_id": "run-123",
  "messages": [
    {
      "role": "assistant",
      "content": "What outcome are we aiming for?",
      "step_index": 0
    },
    {
      "role": "user",
      "content": "Ship a chat workflows feature",
      "step_index": 0
    }
  ]
}
```

### Submit Answer

```bash
curl -X POST "http://localhost:8000/api/v1/chat-workflows/runs/run-123/answer" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{
    "step_index": 0,
    "answer_text": "Ship a chat workflows feature"
  }'
```

Rules:

- Only `active` runs accept answers.
- `step_index` must match the run's current step.
- `answer_text` must be non-empty after trimming.
- The response returns the updated run. If the final step was answered, `status` becomes `completed`.

### Cancel Run

```bash
curl -X POST "http://localhost:8000/api/v1/chat-workflows/runs/run-123/cancel" \
  -H "X-API-KEY: $API_KEY"
```

Rules:

- Completed runs cannot be canceled.
- Repeated cancel calls are idempotent once the run is already `canceled`.

### Continue To Free Chat

```bash
curl -X POST "http://localhost:8000/api/v1/chat-workflows/runs/run-123/continue-chat" \
  -H "X-API-KEY: $API_KEY"
```

Response:

```json
{
  "conversation_id": "4b2a58b7-cd63-4020-8432-f5f1db09ab53"
}
```

Rules:

- The run must already be `completed`.
- The first successful call creates and stores `free_chat_conversation_id`.
- Later calls return the same stored conversation id.

## Error Cases

- `400 Bad Request`
  - empty `goal`
  - empty `answer_text`
  - invalid `step_index`
  - both or neither of `template_id` / `template_draft`
  - `continue-chat` called before completion
- `404 Not Found`
  - template or run does not exist
  - template or run exists but belongs to a different non-admin user/tenant
- `503 Service Unavailable`
  - storage dependency is present in routing but does not implement the required DB method

## Related Docs

- Developer guide: `../Code_Documentation/Chat_Developer_Guide.md`
- Design doc: `../../Plans/2026-03-07-chat-workflows-design.md`
