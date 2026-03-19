# Hosted Staging Operations Runbook

Version: v0.1.0
Audience: operators supporting the hosted staging environment before first paid launch

This runbook covers backups, restore drills, monitoring, and the minimum support posture for hosted staging. It is intentionally narrow: the goal is to prove the launch surface can be operated safely, not to document every possible production topology.

Production cutover and rollback guidance live with the rest of the hosted deployment material in the private hosted repo. Keep live Stripe proof in staging and use production for non-mutating topology validation only.

## 1) Backup coverage

Hosted staging has two state classes:

1. `Managed PostgreSQL state`
   - AuthNZ users
   - org and billing state
   - any other data stored behind `DATABASE_URL`

2. `Durable application storage`
   - per-user app databases and file-backed artifacts
   - Chroma and local durable storage paths used by the hosted launch profile

Use these helpers where they actually apply:

- `Helper_Scripts/backup_all.sh`
  - backs up file-based databases and Chroma-style storage
- `Helper_Scripts/restore_all.sh`
  - restores the file-based backup created by `backup_all.sh`
- `Helper_Scripts/pg_backup_restore.py`
  - handles PostgreSQL content-backend backup and restore when that backend is configured for PostgreSQL

Important: the hosted AuthNZ and billing cluster still needs provider-native managed Postgres backups or snapshots. The file-based helpers do not replace managed database snapshots for `DATABASE_URL`.

## 2) Backup procedure

For the durable application data:

```bash
./Helper_Scripts/backup_all.sh --output-dir ./Backups
```

For PostgreSQL content-backend dumps when applicable:

```bash
source .venv/bin/activate
python Helper_Scripts/pg_backup_restore.py backup \
  --backup-dir ./tldw_DB_Backups/postgres \
  --label staging-content
```

For the managed AuthNZ/billing Postgres cluster:

- enable automated provider snapshots
- document the restore target and retention window
- verify at least one recent successful backup before every release cut

## 3) Required restore drill before launch

Do not launch paid staging rehearsals until you have performed a restore drill:

1. restore the managed Postgres snapshot into a scratch database or scratch staging environment
2. restore durable application data with:

```bash
./Helper_Scripts/restore_all.sh <backup-directory>
```

3. if PostgreSQL content dumps are part of the deployment, restore them with:

```bash
source .venv/bin/activate
python Helper_Scripts/pg_backup_restore.py restore \
  --dump-file ./tldw_DB_Backups/postgres/staging-content_<timestamp>.dump
```

4. run:
   - `Helper_Scripts/validate_hosted_saas_profile.py`
   - `Helper_Scripts/Deployment/hosted_staging_preflight.py`
   - `bun run e2e:hosted:staging`

The restore drill is not complete until the scratch environment passes the hosted preflight and the smoke lane.

## 4) Monitoring and alerting baseline

Use these existing references:

- `Docs/Deployment/Monitoring/README.md`
- `Docs/Deployment/Monitoring/Alerts/README.md`
- `Docs/Deployment/Monitoring/Metrics_Cheatsheet.md`

At minimum, staging operators should be able to answer:

- Is the public app up and returning healthy `/health` and `/ready` responses?
- Are HTTP 5xx rates or latency spiking?
- Are billing webhooks arriving and processing?
- Are backups succeeding on schedule?
- Is durable storage nearing quota or filling unexpectedly?

## 5) Minimum support checklist for first paid customers

Before first paid launch rehearsal, confirm:

- `admin-ui` operators can locate a user, org, and plan state without direct DB surgery
- the team can identify whether a failure is auth, billing, webhook, or storage related
- there is a path to issue refunds, replay webhooks, or unblock a user manually
- on-call knows where staging logs, monitoring, and backup evidence live
- the hosted staging preflight and smoke lane are part of the release checklist

## 6) Incident triage order

When staging breaks during the launch prove-out:

1. confirm public reachability with `/health`, `/ready`, `/login`, `/signup`, and `/api/v1/billing/plans`
2. inspect recent staging deploy/config changes
3. inspect Stripe webhook delivery status if billing state is stale
4. inspect backup freshness before making invasive repair changes
5. prefer reversible fixes; do not improvise schema or data rewrites during incident response

Related documents:

- `Docs/Operations/Hosted_Stripe_Test_Mode_Runbook.md`
- Private hosted deployment runbooks and cutover guidance
