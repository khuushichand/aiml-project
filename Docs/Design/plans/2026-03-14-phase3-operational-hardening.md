# Phase 3: Operational Hardening — Production Quality

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make deployments reliable and observable with Redis-backed state, Grafana dashboards, backup verification, extended setup, operations guide, and unified backup script.

**Architecture:** Redis governor already exists as an alternative (`governor_redis.py`). We make it the default when Redis is available, add Grafana dashboard JSON files, create backup verification tests, write an operations runbook, and build a unified backup script.

**Tech Stack:** Python 3.11+, Redis, Grafana JSON, Bash, pytest

**Note:** MFA for SQLite (Gap 3.4) was found to be already fully implemented. Skipped.

---

## Task Overview

| Task | Gap | Description | Effort |
|------|-----|-------------|--------|
| 1 | 7.1+7.2 | Redis-backed state + horizontal scaling docs | L |
| 2 | 4.1 | Grafana dashboards | M |
| 3 | 4.3 | Automated backup restore testing | M |
| 4 | 6.1 | Extended setup wizard documentation | M |
| 5 | 6.2 | Admin operations guide / runbook | M |
| 6 | 10.4 | Unified backup/restore script | M |

---

## Task 1: Redis-Backed State + Horizontal Scaling (Gaps 7.1+7.2)

Make the Redis governor the default when Redis is available, and document horizontal scaling.

**Files:**
- Modify: `tldw_Server_API/app/core/Resource_Governance/governor.py` — add factory to select Redis vs Memory backend
- Create: `Docs/Deployment/horizontal-scaling.md` — document multi-node deployment

The governor_redis.py already exists. The key change is making the governor initialization in main.py prefer Redis when available.

## Task 2: Grafana Dashboards (Gap 4.1)

Create JSON dashboard files for the monitoring stack.

**Files:**
- Create: `Dockerfiles/Monitoring/grafana/dashboards/tldw-overview.json`
- Create: `Dockerfiles/Monitoring/grafana/dashboards/tldw-api-performance.json`
- Create: `Dockerfiles/Monitoring/grafana/dashboards/tldw-resource-governor.json`

## Task 3: Automated Backup Restore Testing (Gap 4.3)

Write tests that create a backup, corrupt/modify the DB, restore, and verify integrity.

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_backup_restore_verification.py`

## Task 4: Extended Setup Wizard Documentation (Gap 6.1)

Document the setup wizard flow and what configurations are available.

**Files:**
- Create: `Docs/Deployment/setup-wizard-guide.md`

## Task 5: Admin Operations Guide (Gap 6.2)

Create a runbook for operators covering common tasks, troubleshooting, and emergency procedures.

**Files:**
- Create: `Docs/Operations/admin-operations-runbook.md`

## Task 6: Unified Backup/Restore Script (Gap 10.4)

Create a script that backs up all user databases, ChromaDB data, and media files.

**Files:**
- Create: `Helper_Scripts/backup_all.sh`
- Create: `Helper_Scripts/restore_all.sh`
