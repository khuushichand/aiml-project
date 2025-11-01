# Prompt Studio API

The Prompt Studio module provides a structured workflow to design, version, test, evaluate, and optimize prompts within projects. It exposes cohesive APIs for projects, prompts (with versioning), test cases, evaluations, optimizations, and real-time updates.

## Overview

- Projects group all Prompt Studio entities (prompts, test cases, evaluations, optimizations) under a workspace.
- Prompts are versioned. Every update creates a new immutable version for reproducibility.
- Test cases define inputs, expected outputs, tags, and a golden flag; they form the corpus for evaluation.
- Evaluations run a prompt (or prompt version) against a set of test cases and save metrics.
- Optimizations run strategies to iteratively improve prompts (e.g., iterative refinement, hyperparameter tuning).
- Real-time updates are available via WebSocket with SSE fallback.

Authentication follows the server's standard modes (single-user API key or multi-user JWT). Endpoints are project-scoped: reads require access, writes require write access. Rate limits apply to generation/optimization endpoints.

 Tag in OpenAPI: `prompt-studio`.

## More Examples

### Update Project
```bash
curl -X PUT "http://localhost:8000/api/v1/prompt-studio/projects/update/1" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{"description": "Updated description"}'
```

### Delete Project (soft)
```bash
curl -X DELETE "http://localhost:8000/api/v1/prompt-studio/projects/delete/1" \
  -H "X-API-KEY: $API_KEY"
```

### Archive / Unarchive Project
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/projects/archive/1" -H "X-API-KEY: $API_KEY"
curl -X POST "http://localhost:8000/api/v1/prompt-studio/projects/unarchive/1" -H "X-API-KEY: $API_KEY"
```

### Update Test Case
```bash
curl -X PUT "http://localhost:8000/api/v1/prompt-studio/test-cases/update/101" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{"name": "Short text (v2)", "is_golden": true}'
```

### Delete Test Case
```bash
curl -X DELETE "http://localhost:8000/api/v1/prompt-studio/test-cases/delete/101" \
  -H "X-API-KEY: $API_KEY"
```

### Delete Evaluation
```bash
curl -X DELETE "http://localhost:8000/api/v1/prompt-studio/evaluations/501" -H "X-API-KEY: $API_KEY"
```

### Cancel Optimization
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/optimizations/cancel/701" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{"reason": "Stopping for manual review"}'
```

### Record an Optimization Iteration
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/optimizations/iterations/701" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{"iteration_number": 4, "metrics": {"accuracy": 0.82}, "tokens_used": 1400, "cost": 0.08}'
```

### List Optimization Iterations
```bash
curl -X GET "http://localhost:8000/api/v1/prompt-studio/optimizations/iterations/701?page=1&per_page=20" \
  -H "X-API-KEY: $API_KEY"
```

### Get Optimization History & Timeline
```bash
curl -X GET "http://localhost:8000/api/v1/prompt-studio/optimizations/history/701" -H "X-API-KEY: $API_KEY"
```

## Endpoints

### Projects
- Create: `POST /api/v1/prompt-studio/projects/`
- List: `GET /api/v1/prompt-studio/projects/`
- Get: `GET /api/v1/prompt-studio/projects/get/{project_id}`
- Update: `PUT /api/v1/prompt-studio/projects/update/{project_id}`
- Delete: `DELETE /api/v1/prompt-studio/projects/delete/{project_id}?permanent=false`
- Archive: `POST /api/v1/prompt-studio/projects/archive/{project_id}`
- Unarchive: `POST /api/v1/prompt-studio/projects/unarchive/{project_id}`
- Stats: `GET /api/v1/prompt-studio/projects/stats/{project_id}`

### Prompts (Versioned)
- Create: `POST /api/v1/prompt-studio/prompts/create`
- List: `GET /api/v1/prompt-studio/prompts/list/{project_id}`
- Get: `GET /api/v1/prompt-studio/prompts/get/{prompt_id}`
- Update (new version): `PUT /api/v1/prompt-studio/prompts/update/{prompt_id}`
- History: `GET /api/v1/prompt-studio/prompts/history/{prompt_id}`
- Revert (new version): `POST /api/v1/prompt-studio/prompts/revert/{prompt_id}/{version}`

### Test Cases
- Create: `POST /api/v1/prompt-studio/test-cases/create`
- Bulk Create: `POST /api/v1/prompt-studio/test-cases/bulk`
- List: `GET /api/v1/prompt-studio/test-cases/list/{project_id}`
- Get: `GET /api/v1/prompt-studio/test-cases/get/{test_case_id}`
- Update: `PUT /api/v1/prompt-studio/test-cases/update/{test_case_id}`
- Delete: `DELETE /api/v1/prompt-studio/test-cases/delete/{test_case_id}?permanent=false`
- Import: `POST /api/v1/prompt-studio/test-cases/import` (CSV or JSON payload)
- Export: `POST /api/v1/prompt-studio/test-cases/export/{project_id}` (CSV or JSON)
- Generate: `POST /api/v1/prompt-studio/test-cases/generate`

### Evaluations
- Create: `POST /api/v1/prompt-studio/evaluations`
  - Supports async run via background task
- List: `GET /api/v1/prompt-studio/evaluations?project_id=...&prompt_id=...`

### Optimizations
- Create: `POST /api/v1/prompt-studio/optimizations/create`
- List: `GET /api/v1/prompt-studio/optimizations/list/{project_id}`
- Get: `GET /api/v1/prompt-studio/optimizations/get/{optimization_id}`
- Cancel: `POST /api/v1/prompt-studio/optimizations/cancel/{optimization_id}`
- Strategies: `GET /api/v1/prompt-studio/optimizations/strategies`
- Compare: `POST /api/v1/prompt-studio/optimizations/compare`

### Real-time API
- WebSocket base: `WS /api/v1/prompt-studio/ws`
- WebSocket per project: `WS /api/v1/prompt-studio/ws/{project_id}`
- SSE fallback: `GET /api/v1/prompt-studio/ws` (text/event-stream)

## Common Schemas

- ProjectCreate, ProjectUpdate, ProjectResponse
- PromptCreate, PromptUpdate, PromptResponse, PromptVersion
- TestCaseCreate, TestCaseUpdate, TestCaseResponse, TestCaseBulkCreate, TestCaseImportRequest, TestCaseExportRequest, TestCaseGenerateRequest
- EvaluationCreate, EvaluationResponse, EvaluationMetrics
- OptimizationCreate, OptimizationResponse, OptimizationConfig

## Quick Examples

### Create a Project
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/projects/" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{
        "name": "Demo Project",
        "description": "Exploring prompt versions",
        "status": "active"
      }'
```

### Create a Prompt (v1)
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/prompts/create" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{
        "project_id": 1,
        "name": "Summarizer",
        "system_prompt": "Summarize the content clearly.",
        "user_prompt": "{{text}}"
      }'
```

### Add Test Cases (Bulk)
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/test-cases/bulk" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{
        "project_id": 1,
        "test_cases": [
          {"name": "Short text", "inputs": {"text": "Hello world"}, "expected_outputs": {"summary": "Hello world."}},
          {"name": "Long text", "inputs": {"text": "..."}, "expected_outputs": {"summary": "..."}}
        ]
      }'
```

### Update Prompt (new version)
```bash
curl -X PUT "http://localhost:8000/api/v1/prompt-studio/prompts/update/12" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{"system_prompt": "Summarize concisely.", "change_description": "Tighten style"}'
```

### Revert Prompt to Specific Version
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/prompts/revert/12/1" -H "X-API-KEY: $API_KEY"
```

### Export Test Cases (JSON)
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/test-cases/export/1" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{"format": "json", "include_golden_only": false, "tag_filter": ["smoke"]}'
```

### Import Test Cases via CSV Upload (multipart/form-data)

Sample CSV (save as `cases.csv`):
```
name,description,input.text,expected.summary,tags,is_golden
Short,,"Hello world","Hello world.","smoke,basic",true
Long,"Longer passage","This is a longer passage...","A concise summary...","regression",false
```

Upload with curl:
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/test-cases/import/csv-upload" \
  -H "X-API-KEY: $API_KEY" \
  -F project_id=1 \
  -F signature_id=2 \
  -F auto_generate_names=true \
  -F file=@cases.csv;type=text/csv
```

Download a CSV template derived from a signature (fields):
```bash
curl -L "http://localhost:8000/api/v1/prompt-studio/test-cases/import/template?signature_id=2" \
  -H "X-API-KEY: $API_KEY" -o template.csv
```

Notes:
- Use `input.<field>` for inputs and `expected.<field>` for expected outputs. Values may be raw strings or JSON; JSON will be parsed when present.
- Separate multiple tags with commas (`,`). The importer splits on commas.
- `signature_id` is optional; provide when schema validation is desired.

CSV column schema (conceptual JSON Schema):
```
{
  "type": "object",
  "properties": {
    "name": { "type": "string" },
    "description": { "type": "string" },
    "tags": { "type": "string", "description": "Comma-separated tags" },
    "is_golden": { "type": "boolean" },
    "input.*": { "type": ["string", "object"], "description": "Input fields; prefix with input." },
    "expected.*": { "type": ["string", "object"], "description": "Expected output fields; prefix with expected." }
  },
  "required": [ "input.*" ]
}
```

### Run Evaluation
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/evaluations" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{
        "project_id": 1,
        "prompt_id": 12,
        "name": "Baseline Eval",
        "test_case_ids": [1,2,3],
        "config": {"model_name": "gpt-4o-mini", "temperature": 0.2, "max_tokens": 256}
      }'
```

### Create Optimization Job
```bash
curl -X POST "http://localhost:8000/api/v1/prompt-studio/optimizations/create" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{
        "project_id": 1,
        "name": "Refine Summarizer",
        "initial_prompt_id": 12,
        "test_case_ids": [1,2,3],
        "optimization_config": {
          "optimizer_type": "iterative",
          "max_iterations": 20,
          "target_metric": "accuracy",
          "early_stopping": true
        }
      }'
```

### Subscribe to Real-time Updates (WebSocket)
```js
const ws = new WebSocket("ws://localhost:8000/api/v1/prompt-studio/ws");
ws.onopen = () => ws.send(JSON.stringify({ type: "subscribe", entity_type: "project", entity_id: 1 }));
ws.onmessage = (evt) => console.log("event", evt.data);
```

## Access Control & Limits

- Reads require project access; writes require project write access
- SecurityConfig defines limits (e.g., max prompt length, max test cases)
- Rate limiting is applied to generation/optimization endpoints

## Notes

- Prompt updates create new versions; reverting also creates a new version
- Evaluations can run synchronously or as background tasks
- Real-time updates support both WebSocket and SSE fallback
- Real-time updates support both WebSocket and SSE fallback
