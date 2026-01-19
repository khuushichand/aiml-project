# Jobs Admin Examples

Quick examples for common Jobs admin operations. Replace `$BASE` with your server URL and `$API_KEY` with your key (single-user mode) or use a Bearer token in multi-user mode.

## Stats

List queue stats by domain/queue/job_type, including queued (ready), scheduled, processing, and quarantined.

```bash
curl -X GET "$BASE/api/v1/jobs/stats?domain=chatbooks&queue=default" \
  -H "X-API-KEY: $API_KEY" \
  -H "Accept: application/json"
```

## Prune (destructive; use dry run first)

Preview deletion of completed/failed/cancelled jobs older than 30 days for a scoped queue:

```bash
curl -X POST "$BASE/api/v1/jobs/prune" \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "statuses": ["completed","failed","cancelled"],
        "older_than_days": 30,
        "domain": "chatbooks",
        "queue": "default",
        "job_type": "export",
        "dry_run": true
      }'
```

Execute the prune (requires confirm header):

```bash
curl -X POST "$BASE/api/v1/jobs/prune" \
  -H "X-API-KEY: $API_KEY" \
  -H "X-Confirm: true" \
  -H "Content-Type: application/json" \
  -d '{
        "statuses": ["completed","failed","cancelled"],
        "older_than_days": 30,
        "domain": "chatbooks",
        "queue": "default",
        "job_type": "export",
        "dry_run": false
      }'
```

## TTL Sweep (destructive; use confirm)

Cancel queued jobs older than 1 day and processing jobs running longer than 2 hours:

```bash
curl -X POST "$BASE/api/v1/jobs/ttl/sweep" \
  -H "X-API-KEY: $API_KEY" \
  -H "X-Confirm: true" \
  -H "Content-Type: application/json" \
  -d '{
        "age_seconds": 86400,
        "runtime_seconds": 7200,
        "action": "cancel",
        "domain": "chatbooks",
        "queue": "default"
      }'
```

## Requeue Quarantined

Dry run (count only) for a scoped set:

```bash
curl -X POST "$BASE/api/v1/jobs/batch/requeue_quarantined" \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "domain": "chatbooks",
        "queue": "default",
        "job_type": "export",
        "dry_run": true
      }'
```

Real run (requires confirm header):

```bash
curl -X POST "$BASE/api/v1/jobs/batch/requeue_quarantined" \
  -H "X-API-KEY: $API_KEY" \
  -H "X-Confirm: true" \
  -H "Content-Type: application/json" \
  -d '{
        "domain": "chatbooks",
        "queue": "default",
        "job_type": "export",
        "dry_run": false
      }'
```

## Integrity Sweep

Dry run scan (scoped):

```bash
curl -X POST "$BASE/api/v1/jobs/integrity/sweep" \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "fix": false,
        "domain": "chatbooks",
        "queue": "default"
      }'
```

Fix globally (clear stale leases on non-processing rows; requeue expired processing):

```bash
curl -X POST "$BASE/api/v1/jobs/integrity/sweep" \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "fix": true }'
```

## Notes

- Confirmation header `X-Confirm: true` is required for destructive actions when `dry_run` is false.
- In multi-user mode, use `Authorization: Bearer <token>` instead of `X-API-KEY`.
- For idempotent finalize guarantees, set `JOBS_REQUIRE_COMPLETION_TOKEN=true` and ensure workers pass `completion_token` (workers already use `lease_id`).
