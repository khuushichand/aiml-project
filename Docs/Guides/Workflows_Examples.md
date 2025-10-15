# Workflows Examples

Practical step templates and end‑to‑end definitions you can use as starting points. All examples are `POST /api/v1/workflows` bodies.

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

## 3) Fan‑out / Map over a list

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

## 5) Completion webhook example

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

## Export/Import

- Definitions are immutable per `{name, version}`; export by reading the stored snapshot (`GET /api/v1/workflows/{id}`).
- Import by posting the same body (adjust name/version to avoid unique constraint).

