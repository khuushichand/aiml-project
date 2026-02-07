# Implementation Plan: Content Moderation, Parental Controls & Self-Monitoring

## Overview
Two interconnected features for tldw:
1. **Parental Controls (Guardian → Child)**: Guardian-configured content blocking/notification on supervised accounts
2. **Self-Monitoring (User → Self)**: Awareness-focused topic notifications for adult users

## Stage 1: Guardian Relationship DB & Schemas [In Progress]
**Goal**: Database layer for guardian-child relationships + Pydantic schemas
**Files**:
- `app/core/DB_Management/Guardian_DB.py` - SQLite DB with guardian_relationships, consent tracking
- `app/api/v1/schemas/guardian_schemas.py` - Pydantic models for CRUD operations
**Success Criteria**: Guardian links can be created, queried, and dissolved; consent tracked
**Status**: In Progress

## Stage 2: Supervised Policy Layer [Not Started]
**Goal**: Policy engine layering guardian rules on top of ModerationService
**Files**:
- `app/core/Moderation/supervised_policy.py` - SupervisedPolicy class extending ModerationPolicy
**Success Criteria**: Guardian block/notify rules compose with existing ModerationPolicy
**Status**: Not Started

## Stage 3: Self-Monitoring Service [Not Started]
**Goal**: Awareness-oriented monitoring with dedup, notification routing, crisis resources
**Files**:
- `app/core/Monitoring/self_monitoring_service.py` - SelfMonitoringService class
**Success Criteria**: Users can create awareness profiles with topic watchlists, notifications fire with dedup
**Status**: Not Started

## Stage 4: API Endpoints [Not Started]
**Goal**: REST endpoints for both use cases
**Files**:
- `app/api/v1/endpoints/guardian_controls.py` - Guardian CRUD + supervised policy management
- `app/api/v1/endpoints/self_monitoring.py` - Self-monitoring profile CRUD
**Success Criteria**: All CRUD operations accessible via REST API
**Status**: Not Started

## Stage 5: Tests [Not Started]
**Goal**: Comprehensive test coverage
**Files**:
- `tests/Guardian/test_guardian_db.py`
- `tests/Guardian/test_supervised_policy.py`
- `tests/Monitoring/test_self_monitoring.py`
- `tests/Guardian/test_guardian_endpoints.py`
- `tests/Monitoring/test_self_monitoring_endpoints.py`
**Status**: Not Started

## Stage 6: Integration & Registration [Not Started]
**Goal**: Wire up in main.py, add feature flags, write design doc
**Files**:
- `app/main.py` (edit)
- `app/core/feature_flags.py` (edit)
- `Docs/Design/Content_Moderation_Parental_Self_Monitoring.md`
**Status**: Not Started
