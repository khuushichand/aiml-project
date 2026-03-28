# Remaining 27 Findings — Backend-Heavy Implementation Plan

**Date:** 2026-03-27
**Context:** 93 of 120 findings addressed (61 commits). 27 remain — nearly all require new backend endpoints, DB schema changes, or major infrastructure. 3 permanently deferred (5.12, 10.8, 3.6).

---

## Phase A: Backend Schema & Endpoint Sprint (~2 weeks)

> Focus: Add all missing backend endpoints in one concentrated sprint, then wire frontends.

### A1: Incident & Dependencies Backend (5.4, 5.5, 5.6, 5.7)

| Finding | Backend Work | Complexity |
|---------|-------------|-----------|
| 5.4 | `GET /admin/dependencies/health` — probe DB, cache, queue, storage with timeout | Medium |
| 5.5 | `GET /admin/dependencies/uptime-history` — time-series health check storage | Large |
| 5.6 | `POST /admin/incidents/{id}/notify` — emit via `JobsNotificationsService` pattern | Large |
| 5.7 | Add computed `time_to_acknowledge`, `time_to_resolve` to incident response + `GET /admin/incidents/stats` | Medium |

**Reuse:** `jobs_notifications_service.py` for 5.6, `admin_monitoring.py` for 5.4
**New files:** Extend `admin_monitoring.py`, new health-check time-series table

### A2: Billing & Subscription Backend (7.5, 7.7, 7.9)

| Finding | Backend Work | Complexity |
|---------|-------------|-----------|
| 7.5 | `GET /admin/subscriptions/{id}/events` — query audit log by resource_type=subscription | Medium |
| 7.7 | Add `availability_type` enum to feature registry schema | Medium |
| 7.9 | `GET /admin/billing/analytics` — MRR, churn rate, trial conversion from subscription + plan tables | Large |

**New files:** `admin_subscriptions.py` router

### A3: AI & Usage Backend (4.2, 4.10, 4.12, 6.2, 6.5)

| Finding | Backend Work | Complexity |
|---------|-------------|-----------|
| 4.2 | `admin_provider_budget_thresholds` table + CRUD endpoints | Large |
| 4.10 | `GET /admin/mcp/tool-usage` — aggregate from ACP audit DB by tool name | Medium |
| 4.12 | `POST /admin/voice-commands/dry-run` — validate pipeline without executing | Medium |
| 6.2 | `GET/POST /admin/security/risk-weights` — store as JSON in admin settings | Medium |
| 6.5 | `GET /admin/usage/cost-attribution?group_by=user|org` — join usage + pricing | Medium |

### A4: Webhook & Debug Backend (10.1, 10.2, 8.3)

| Finding | Backend Work | Complexity |
|---------|-------------|-----------|
| 10.1 | Webhook CRUD: new `admin_webhooks.py` + `admin_webhooks_service.py` + delivery log table | Large |
| 10.2 | Extend `UserNotificationRow` with `delivery_status` + `delivered_at` | Medium |
| 8.3 | `admin_debug.py` — permission resolver, rate limit simulator, token validator (3 endpoints) | Large |

### A5: Small Backend Additions (3.10, 5.9-backend, 2.12-backend)

| Finding | Backend Work | Complexity |
|---------|-------------|-----------|
| 3.10 | `DELETE /admin/users/{id}/virtual-keys/{key_id}` + revoke | Small |
| 5.9 | Add `runbook_url` column to incidents table (schema migration) | Small |

---

## Phase B: Frontend Integration Sprint (~1.5 weeks)

> Wire all new backend endpoints into the admin-ui.

### B1: Incident & Dependencies Frontend

| Finding | Frontend Work |
|---------|--------------|
| 5.4 | Expand `dependencies/page.tsx` to show all services in health grid |
| 5.5 | Add uptime sparkline per dependency |
| 5.6 | Add "Notify Team" button to incident cards |
| 5.7 | Display TTR/TTA columns + MTTR summary card |

### B2: Billing Frontend

| Finding | Frontend Work |
|---------|--------------|
| 7.5 | Expandable lifecycle timeline on subscription rows |
| 7.7 | `availability_type` badge in feature registry |
| 7.9 | New billing analytics section (MRR, churn, conversion cards) |

### B3: AI & Usage Frontend

| Finding | Frontend Work |
|---------|--------------|
| 4.2 | Provider budget section in budgets page |
| 4.10 | Usage column in MCP tools tab |
| 4.12 | Dry-run results panel on voice command detail |
| 6.2 | Risk weight config dialog in security page |
| 6.5 | Cost attribution tab in usage page |

### B4: Webhook & Debug Frontend

| Finding | Frontend Work |
|---------|--------------|
| 10.1 | New `app/webhooks/page.tsx` with CRUD + delivery log |
| 10.2 | Delivery status column in notifications panel |
| 8.3 | 3 new debug tool cards in `debug/page.tsx` |

---

## Phase C: Remaining Frontend Polish (~1 week)

| Finding | Work |
|---------|------|
| 2.5 | Org detail tabs refactor (Members, Teams, BYOK, Billing) |
| 6.8 | Move maintenance mode toggle from flags to data-ops |
| 9.7 | Optimistic updates for flag toggle, agent enable, budget enforcement |
| 9.9 | Remove deprecated ConfirmDialog export |
| 10.3 | Storage breakdown card on Data Ops page |
| 10.5 | Rate limit analytics section on resource-governor page |
| 11.1 | Chart text alternatives + sr-only data tables for 5 chart components |
| 11.4 | Create LiveRegion wrapper component for loading states |
| 11.5 | Use StatusIndicator consistently in health grid |

---

## Summary

| Phase | Findings | Duration |
|-------|----------|----------|
| A (Backend) | 17 endpoints | ~2 weeks |
| B (Frontend integration) | 14 UI changes | ~1.5 weeks |
| C (Polish) | 9 UI changes | ~1 week |
| **Total** | **24 active** | **~4.5 weeks** |

3 permanently deferred: 5.12, 10.8, 3.6
