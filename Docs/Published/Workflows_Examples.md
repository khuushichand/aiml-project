# Workflows Examples (Curated)

End-to-end templates and CLI snippets. See the full guide at `../Guides/Workflows_Examples.md`.

## Templates

- Prompt → Log
- Branch on condition
- Fan-out/Map with aggregate
- Policy gate (branch)
- Prompt + RAG + answer synthesis
- Completion webhook
- ACP pipeline L1/L2/L3 (domain-only)

Example (Prompt + RAG):

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

## CLI Snippets

- Create: `curl -X POST /api/v1/workflows -H 'X-API-KEY: $API_KEY' -d @definition.json`
- Run (async): `curl -X POST /api/v1/workflows/{id}/run?mode=async -H 'X-API-KEY: $API_KEY' -d '{"inputs":{}}'`
- Events: `curl /api/v1/workflows/runs/{run_id}/events?limit=100 -H 'X-API-KEY: $API_KEY'`
- Control: `pause|resume|cancel` via `POST /api/v1/workflows/runs/{run_id}/{action}`
- Artifact range: `curl -H 'Range: bytes=0-1023' /api/v1/workflows/artifacts/{artifact_id}/download`
- Manifest verify: `curl /api/v1/workflows/runs/{run_id}/artifacts/manifest?verify=true`

## ACP Pipeline Templates

Bundled ACP templates are available from:

- `GET /api/v1/workflows/templates/pipeline_l1_acp`
- `GET /api/v1/workflows/templates/pipeline_l2_acp`
- `GET /api/v1/workflows/templates/pipeline_l3_acp`

Stage flow:

- `pipeline_l1_acp`: `req -> impl -> done`
- `pipeline_l2_acp`: `req -> plan -> impl -> impl_review -> done`
- `pipeline_l3_acp`: `req -> plan -> plan_review -> impl -> impl_review -> test -> done`

Domain-only scope note:

- Current ACP templates are domain-only by design.
- Planned next phase is deeper ACP + sandbox module integration to spin up instances/workspaces per run.

Run example using L2 template:

```
curl -sS -X GET \
  "http://127.0.0.1:8000/api/v1/workflows/templates/pipeline_l2_acp" \
  -H "X-API-KEY: $API_KEY" > /tmp/pipeline_l2_acp.json

WF_ID=$(curl -sS -X POST \
  "http://127.0.0.1:8000/api/v1/workflows" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d @/tmp/pipeline_l2_acp.json | jq -r .id)

curl -sS -X POST \
  "http://127.0.0.1:8000/api/v1/workflows/${WF_ID}/run?mode=async" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{"inputs":{"task":"implement domain-only flow","reviewer_user_id":"1"}}'
```

## Human-in-the-loop

Use `wait_for_human` to pause and resume via approve/reject endpoints.

Approve with optional edits:

```
curl -sS -X POST \
  "http://127.0.0.1:8000/api/v1/workflows/runs/${RUN_ID}/steps/review/approve" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{"comment":"Looks good","edited_fields":{"text":"Approved text"}}'
```

## Idempotent runs

Provide `idempotency_key` in the run body to deduplicate repeated submissions:

```
curl -sS -X POST \
  "http://127.0.0.1:8000/api/v1/workflows/${WF_ID}/run?mode=async" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{"inputs": {"name": "Alice"}, "idempotency_key": "demo-key-123"}'
```
