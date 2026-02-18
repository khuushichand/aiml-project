# Implementation Plan: HCI Review - Data Operations

## Scope

Pages: `app/data-ops/`, `components/data-ops/*`
Finding IDs: `7.1` through `7.5`

## Finding Coverage

- `7.1` (Important): No backup success/failure history or scheduling
- `7.2` (Important): Retention policies applied immediately with no impact preview
- `7.3` (Important): No GDPR data subject request handling (right to erasure, portability)
- `7.4` (Nice-to-Have): No backup size trending or storage growth monitoring
- `7.5` (Important): Encryption key rotation has no rollback or status tracking

## Key Files

- `admin-ui/app/data-ops/page.tsx` -- Tabbed layout hosting 4 section components
- `admin-ui/components/data-ops/BackupsSection.tsx` -- Backup list (filtered by dataset/user), create backup, restore
- `admin-ui/components/data-ops/RetentionPoliciesSection.tsx` -- Policy list with editable days, immediate apply warning
- `admin-ui/components/data-ops/ExportsSection.tsx` -- Audit log export + user export (CSV/JSON)
- `admin-ui/components/data-ops/MaintenanceSection.tsx` -- Cleanup settings, notes title settings, FTS maintenance, crypto key rotation
- `admin-ui/lib/api-client.ts` -- Backup CRUD, retention policies, exports, maintenance endpoints

## Stage 1: Backup Scheduling + History

**Goal**: Move beyond manual-only backups to scheduled backups with a success/failure audit trail.
**Success Criteria**:
- BackupsSection adds "Schedule" tab alongside existing backup list.
- Schedule form: dataset selector, frequency (daily, weekly, monthly), time of day, retention count (max backups to keep).
- Schedule CRUD: create, view, edit, pause/resume, delete schedules.
- Backup list adds "Status" column with icons: success (green check), failed (red X), in-progress (spinner).
- Failed backups show error message on hover/click.
- "Backup History" section shows last 20 backups across all datasets with timestamp, dataset, size, duration, status.
- History filterable by status (success/failed) and dataset.
**Tests**:
- Unit test for schedule form validation (frequency + time required).
- Unit test for backup history table with mixed statuses.
- Unit test for schedule pause/resume toggle.
**Status**: Complete

## Stage 2: Retention Impact Preview + Key Rotation Tracking

**Goal**: Prevent accidental data loss from retention policies and make key rotation observable.
**Success Criteria**:
- Retention policy edit: before saving, "Preview Impact" button fetches estimated affected row counts.
- Preview shows: "Changing from 90 to 30 days will delete approximately X audit log entries, Y job records, Z backup files."
- Preview requires explicit "I understand" confirmation checkbox before save is enabled.
- Encryption key rotation: replace single "Rotate" button with a multi-step wizard.
- Wizard steps: 1) Confirmation + warning, 2) Progress bar with status messages ("Re-encrypting batch 1 of N..."), 3) Completion summary with count of re-encrypted records.
- Rotation status persisted: if page is refreshed during rotation, shows current status.
- Rotation history: last rotation timestamp, records affected, initiated by (username).
**Tests**:
- Unit test for impact preview rendering with various counts.
- Unit test for confirmation checkbox gating save button.
- Unit test for rotation wizard step progression.
- Unit test for rotation progress bar updates.
**Status**: Complete

## Stage 3: GDPR Data Subject Requests + Backup Trending

**Goal**: Enable compliance with data subject requests and provide storage growth visibility.
**Success Criteria**:
- New "Data Subject Requests" section in data-ops page.
- Request form: user identifier (email or user ID), request type (export, erasure, access).
- Export request: generates downloadable archive of all user data across databases (media, chat, notes, audit, embeddings).
- Erasure request: shows all data categories for the user with record counts, admin selects categories to delete, confirmation with "This action cannot be undone" warning.
- Access request: shows summary of what data exists for this user (categories + counts) without downloading.
- Request log: tracks all data subject requests with timestamp, type, requester, status, completion date.
- BackupsSection adds storage trending chart: backup size over time (last 10 backups per dataset).
- Trending chart shows growth rate: "Storage growing at X MB/month."
**Tests**:
- Unit test for data subject request form validation.
- Unit test for erasure confirmation flow with category selection.
- Unit test for request log rendering.
- Unit test for storage trending chart with growth rate.
**Status**: Complete

## Dependencies

- Stage 1 backup scheduling requires backend endpoints for schedule CRUD. If not available, schedule configuration can be stored client-side (localStorage) with a note that backend persistence is needed.
- Stage 2 retention impact preview requires a backend endpoint that estimates affected rows without actually deleting (dry-run).
- Stage 2 key rotation progress requires the backend to support a polling endpoint for rotation status.
- Stage 3 GDPR data subject requests require backend endpoints to enumerate user data across databases and perform targeted deletion. This is likely the most backend-dependent stage.
