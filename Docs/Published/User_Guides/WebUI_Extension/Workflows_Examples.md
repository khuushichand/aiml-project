# Workflows Examples

Practical step templates and end-to-end definitions you can use as starting points. All examples are `POST /api/v1/workflows` bodies.

## 1) Prompt → Log

```
{
  "name": "prompt-log",
  "version": 1,
  "steps": [
    {"id": "p1", "type": "prompt", "config": {"template": "Hello {{ inputs.name }}"}},
    {"id": "l1", "type": "log", "config": {"message": "Rendered: {{ last.text }}", "level": "info"}}
  ]
}
```

Run: `POST /api/v1/workflows/{id}/run` with `{ "inputs": { "name": "Alice" } }`.

## 2) Branch on condition (prompt content)

```
{
  "name": "branch-example",
  "version": 1,
  "steps": [
    {"id": "p1", "type": "prompt", "config": {"template": "{{ inputs.flag }}"}},
    {"id": "b1", "type": "branch", "config": {"condition": "{{ last.text == 'ok' }}", "true_next": "l_ok", "false_next": "l_bad"}},
    {"id": "l_ok", "type": "log", "config": {"message": "OK path", "level": "info"}},
    {"id": "l_bad", "type": "log", "config": {"message": "BAD path", "level": "warning"}}
  ]
}
```

## 3) Fan-out / Map over a list

```
{
  "name": "map-delay",
  "version": 1,
  "steps": [
    {"id": "m1", "type": "map", "config": {"items": "{{ inputs.items }}", "step": {"type": "delay", "config": {"milliseconds": 50}}, "concurrency": 4}},
    {"id": "l1", "type": "log", "config": {"message": "Processed {{ last|length }} items", "level": "info"}}
  ]
}
```

## 4) Prompt + RAG search pipeline

```
{
  "name": "prompt-rag",
  "version": 1,
  "steps": [
    {"id": "q", "type": "prompt", "config": {"template": "{{ inputs.query }}"}},
    {"id": "search", "type": "rag_search", "config": {"query": "{{ last.text }}", "search_mode": "hybrid", "top_k": 5, "enable_reranking": true}},
    {"id": "l", "type": "log", "config": {"message": "Docs: {{ last.documents|length }}", "level": "info"}}
  ]
}
```

## 5) Fan-out then Fan-in (aggregate)

"Map" returns a list of outputs which can be consumed by the next step for a simple fan-in.

```
{
  "name": "fanout-fanin",
  "version": 1,
  "steps": [
    {"id": "m1", "type": "map", "config": {
      "items": "{{ inputs.urls }}",
      "step": {"type": "webhook", "config": {"url": "https://example.com/process", "body": {"url": "{{ item }}"}}},
      "concurrency": 3
    }},
    {"id": "reduce", "type": "log", "config": {"message": "Processed {{ last|length }} items", "level": "info"}}
  ]
}
```

## 6) Policy gate (branch)

Gate an operation based on a policy input (or computed flag) using `branch`.

```
{
  "name": "policy-gate",
  "version": 1,
  "steps": [
    {"id": "b1", "type": "branch", "config": {"condition": "{{ inputs.allowed == true }}", "true_next": "do", "false_next": "deny"}},
    {"id": "do", "type": "log", "config": {"message": "Allowed", "level": "info"}},
    {"id": "deny", "type": "log", "config": {"message": "Denied by policy", "level": "warning"}}
  ]
}
```

## 7) Prompt + RAG + Answer synthesis

```
{
  "name": "prompt-rag-answer",
  "version": 1,
  "steps": [
    {"id": "q", "type": "prompt", "config": {"template": "{{ inputs.query }}"}},
    {"id": "search", "type": "rag_search", "config": {"query": "{{ last.text }}", "search_mode": "hybrid", "top_k": 6, "enable_reranking": true}},
    {"id": "answer", "type": "prompt", "config": {"template": "Using the following documents, answer succinctly and include citations where relevant.\n\nDocs: {{ last.documents | tojson }}\n\nQuestion: {{ inputs.query }}"}}
  ]
}
```

## 8) Completion webhook example

```
{
  "name": "webhook-demo",
  "version": 1,
  "on_completion_webhook": {"url": "https://example.com/hook", "include_outputs": true},
  "steps": [
    {"id": "p1", "type": "prompt", "config": {"template": "done"}}
  ]
}
```

## CLI Snippets

Create a definition:

```
curl -sS -X POST "http://127.0.0.1:8000/api/v1/workflows" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d @definition.json
```

Run a saved definition (async):

```
curl -sS -X POST "http://127.0.0.1:8000/api/v1/workflows/${WF_ID}/run?mode=async" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{"inputs": {"name": "Alice"}}'
```

Poll events:

```
curl -sS "http://127.0.0.1:8000/api/v1/workflows/runs/${RUN_ID}/events?limit=100" \
  -H "X-API-KEY: $API_KEY"
```

Pause/Resume/Cancel:

```
curl -sS -X POST "http://127.0.0.1:8000/api/v1/workflows/runs/${RUN_ID}/pause" -H "X-API-KEY: $API_KEY"
curl -sS -X POST "http://127.0.0.1:8000/api/v1/workflows/runs/${RUN_ID}/resume" -H "X-API-KEY: $API_KEY"
curl -sS -X POST "http://127.0.0.1:8000/api/v1/workflows/runs/${RUN_ID}/cancel" -H "X-API-KEY: $API_KEY"
```

Download an artifact range:

```
curl -sS -H "Range: bytes=0-1023" \
  -H "X-API-KEY: $API_KEY" \
  "http://127.0.0.1:8000/api/v1/workflows/artifacts/${ARTIFACT_ID}/download" -o part.bin
```

Verify manifest checksums:

```
curl -sS "http://127.0.0.1:8000/api/v1/workflows/runs/${RUN_ID}/artifacts/manifest?verify=true" \
  -H "X-API-KEY: $API_KEY"
```

## Export/Import
## 9) Human-in-the-loop (wait + approve)

```
{
  "name": "human-approval",
  "version": 1,
  "steps": [
    {"id": "draft", "type": "prompt", "config": {"template": "Draft a short note about {{ inputs.topic }}"}},
    {"id": "review", "type": "wait_for_human", "config": {"instructions": "Review and approve or reject the draft."}},
    {"id": "finalize", "type": "log", "config": {"message": "Approved: {{ last.text or 'ok' }}", "level": "info"}}
  ]
}
```

Flow:
- Run the workflow (async). When it reaches `wait_for_human`, status becomes `waiting_human`.
- Approve with optional edits:

```
curl -sS -X POST \
  "http://127.0.0.1:8000/api/v1/workflows/runs/${RUN_ID}/steps/review/approve" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{"comment":"Looks good","edited_fields":{"text":"Approved text"}}'
```

Or reject:

```
curl -sS -X POST \
  "http://127.0.0.1:8000/api/v1/workflows/runs/${RUN_ID}/steps/review/reject" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{"comment":"Needs more work"}'
```

## 10) Idempotent run submission

Provide `idempotency_key` to deduplicate repeated submissions:

```
curl -sS -X POST \
  "http://127.0.0.1:8000/api/v1/workflows/${WF_ID}/run?mode=async" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{"inputs": {"name": "Alice"}, "idempotency_key": "demo-key-123"}'
```

Repeat with the same key returns the same run.

- Definitions are immutable per `{name, version}`; export by reading the stored snapshot (`GET /api/v1/workflows/{id}`).
- Import by posting the same body (adjust name/version to avoid unique constraint).
