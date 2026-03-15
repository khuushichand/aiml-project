# Phase 4: SaaS Revenue — Monetization Ready

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable usage-based billing, enforce storage quotas, add fair-share worker scheduling, and audit Resource Governor coverage.

**Architecture:** Stripe billing integration already exists (checkout, portal, webhooks). We add usage metering sync, storage quota enforcement middleware, admin billing APIs, a billing dashboard UI, fair-share job scheduling, and governor coverage audit tooling.

**Tech Stack:** Python 3.11+, Stripe API, FastAPI, SQLite, React/TypeScript/Ant Design

---

## Task Overview

| Task | Gap | Description | Effort |
|------|-----|-------------|--------|
| 1 | 2.1 | Admin billing management APIs | M |
| 2 | 9.1 | Usage metering reconciliation with Stripe | M |
| 3 | 5.4 | Storage quota enforcement | M |
| 4 | 5.3 | Worker fair-share scheduling | M |
| 5 | 5.2 | Resource Governor endpoint coverage audit | M |
| 6 | 1.5 | Billing Dashboard UI | L |

---

## Key Findings

- Stripe checkout/portal/webhooks already implemented in `app/core/Billing/`
- Usage tracking exists (per-request logs, daily aggregation) but not synced to Stripe
- Storage quotas repo exists with full CRUD but no enforcement middleware or admin endpoints
- Job manager is DB-backed FIFO with no fair-share scheduling
- Resource Governor has middleware but no per-endpoint coverage tracking
