# Job System Unification Staging Checklist

Audience: Ops + Backend
Status: Draft

Related
- PRD: `Docs/Product/Completed/Job_System_Unification_PRD.md`
- Mapping matrix: `Docs/Product/Job_System_Unification_Mapping_Matrix.md`
- Jobs module: `Docs/Code_Documentation/Jobs_Module.md`

## Scope
Validate the remaining operational items for Jobs unification in staging:
- Retention scheduler enabled and observable.
- Worker wiring for embeddings/chatbooks/prompt studio.
- Admin visibility and scoping behavior.

## Checklist

### 1) Retention scheduler validation (Owner: Ops)
- [ ] Set envs: `JOBS_PRUNE_ENFORCE=true`, `JOBS_PRUNE_DRY_RUN=true` (staging), optional `JOBS_PRUNE_INTERVAL_SEC=300`.
- [ ] Restart API and confirm log line: `Started Jobs prune scheduler: interval=... dry_run=...`.
- [ ] Dry-run via API: `POST /api/v1/jobs/prune` with `{"statuses":["completed","failed","cancelled"],"older_than_days":30,"dry_run":true}`.
- [ ] Confirm response contains `{"deleted": <int>}`; review counts vs expectations.
- [ ] Optional: verify outbox includes `jobs.pruned` events via `GET /api/v1/jobs/events`.
- [ ] Move to live prune (staging only): set `JOBS_PRUNE_DRY_RUN=false`, confirm prune counts in logs, then revert if needed.

### 2) Worker wiring verification (Owner: Backend/Infra)
- [ ] Embeddings Redis worker(s) running for `chunking`, `embedding`, `storage`, `content`.
  - Entrypoint: `python -m tldw_Server_API.app.core.Embeddings.services.redis_worker --stage all`.
  - Logs show stream subscriptions, including `embeddings:content`.
- [ ] Chatbooks Jobs worker running (core backend).
  - Entrypoint: `python -m tldw_Server_API.app.core.Chatbooks.services.jobs_worker`.
  - Logs show `Chatbooks Jobs worker starting` and no `BACKEND is not core` warnings.
- [ ] Prompt Studio Jobs worker running (core backend).
  - Entrypoint: `python -m tldw_Server_API.app.core.Prompt_Management.prompt_studio.services.jobs_worker`.
  - Logs show `Prompt Studio Jobs worker starting` and no `BACKEND is not core` warnings.
- [ ] Admin polling sees Jobs counters: `GET /api/v1/jobs/stats` returns data when jobs exist.
- [ ] Embeddings orchestrator summary reachable (admin-only): `GET /api/v1/embeddings/orchestrator/summary`.

### 3) Admin visibility + scoping (Owner: Backend/QA)
- [ ] Admin can list jobs: `GET /api/v1/jobs/list` (optional `domain` filter).
- [ ] Admin can read job events: `GET /api/v1/jobs/events` (or `/api/v1/jobs/events/stream`).
- [ ] Non-admin tokens return 403 on `/api/v1/jobs/list` and `/api/v1/jobs/stats` (if non-admin creds available).
- [ ] User-facing embeddings job endpoints still return legacy fields:
  - `/api/v1/media/embeddings/jobs`
  - `/api/v1/media/embeddings/jobs/{job_id}`

## Optional smoke script
- Script: `Helper_Scripts/checks/job_system_unification_smoke.py`
- Example:
```
python Helper_Scripts/checks/job_system_unification_smoke.py \
  --base-url http://127.0.0.1:8000 \
  --api-key "$SINGLE_USER_API_KEY"
```
