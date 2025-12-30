# Claims Notifications Delivery

This guide documents alert email digests and review-event delivery for the Claims system, including how to run without SMTP using the mock provider.

## Overview
- **Alert digests**: periodic summaries of `unsupported_ratio` events sent via email (optional).
- **Review notifications**: delivery of review assignment/update events via webhook/Slack/email.
- **Channels**: configured per alert (`/api/v1/claims/alerts`) and/or globally in monitoring settings (`/api/v1/claims/monitoring/config`).
- **Delivery behavior**: best-effort, background threads, short timeouts, with backoff for webhooks. Email delivery uses the configured email provider without additional retries.

## Quick Start (No SMTP Available)
By default the email provider is `mock`, which logs to console or writes JSON/HTML files locally.

Set these environment variables:
```bash
EMAIL_PROVIDER=mock
EMAIL_MOCK_OUTPUT=console   # console|file|both
EMAIL_MOCK_FILE_PATH=./mock_emails
```

Then enable the digest and recipients:
```bash
CLAIMS_ALERT_EMAIL_DIGEST_ENABLED=true
CLAIMS_ALERT_EMAIL_DIGEST_INTERVAL_SEC=86400
CLAIMS_ALERT_EMAIL_DIGEST_MAX_EVENTS=500
```

Configure recipients (global monitoring defaults):
```bash
curl -X PATCH "http://127.0.0.1:8000/api/v1/claims/monitoring/config" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -d '{
    "email_recipients": ["alerts@example.com"],
    "enabled": true
  }'
```

Create an alert that enables email:
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/claims/alerts" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -d '{
    "name": "Unsupported ratio breach",
    "alert_type": "threshold_breach",
    "channels": { "email": true },
    "threshold_ratio": 0.3
  }'
```

With `EMAIL_PROVIDER=mock`, emails will appear in logs or as files under `EMAIL_MOCK_FILE_PATH`.

Mock email output (file mode):
```bash
EMAIL_PROVIDER=mock
EMAIL_MOCK_OUTPUT=file
EMAIL_MOCK_FILE_PATH=./mock_emails
```
Each send writes a JSON payload and HTML file into `EMAIL_MOCK_FILE_PATH`.

Full minimal setup (env + config + alert):
```bash
export EMAIL_PROVIDER=mock
export EMAIL_MOCK_OUTPUT=console
export CLAIMS_ALERT_EMAIL_DIGEST_ENABLED=true
export CLAIMS_ALERT_EMAIL_DIGEST_INTERVAL_SEC=86400

curl -X PATCH "http://127.0.0.1:8000/api/v1/claims/monitoring/config" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -d '{
    "email_recipients": ["alerts@example.com"],
    "enabled": true
  }'

curl -X POST "http://127.0.0.1:8000/api/v1/claims/alerts" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -d '{
    "name": "Unsupported ratio breach",
    "alert_type": "threshold_breach",
    "channels": { "email": true },
    "threshold_ratio": 0.3
  }'
```

## SMTP Setup (Optional)
To send real email via SMTP, set:
```bash
EMAIL_PROVIDER=smtp
EMAIL_FROM=noreply@example.com
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your_user
SMTP_PASSWORD=your_password
SMTP_USE_TLS=true
```

## Review Notifications
Review assignments and review status updates emit `claims_notifications` records and are delivered using the monitoring settings’ channels:
- **Email recipients**: `email_recipients` from `/api/v1/claims/monitoring/config`.
- **Webhooks/Slack**: `webhook_url` and `slack_webhook_url` from the same config.

Notifications are marked delivered when any channel succeeds.

## Observability
- Alert delivery metrics: `claims_alert_email_*`, `claims_alert_webhook_*`.
- Review delivery metrics: `claims_review_email_*`, `claims_review_webhook_*`.
- Alert events stored in `claims_monitoring_events` with `delivered_at`.
- Review events stored in `claims_notifications` with `delivered_at`.

## Disabling Delivery
- Disable monitoring globally by setting `CLAIMS_MONITORING_ENABLED=false`, or
- Remove all channels (email/webhook/Slack) from the monitoring config or alert config.
