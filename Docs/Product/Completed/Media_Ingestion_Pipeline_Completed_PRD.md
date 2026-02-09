# Media Ingestion Pipeline PRD (Completed Scope)

- Title: Media Ingestion Pipeline (Completed Scope)
- Owner: Core Maintainers
- Status: Implemented through Stage 2, plus Stage 3 streaming persistence initial slice
- Target Version: v0.2.x
- Last Updated: 2026-02-09

## 1. Summary

This document captures the shipped scope of the media ingestion pipeline program. It records what is already implemented so the active PRD can focus on remaining roadmap work.

## 2. Delivered Foundation

### 2.1 End-to-End Ingestion Contract
- Validation -> processing -> persistence -> downstream handoff pattern is implemented across core ingestion paths.
- Upload path validation is enforced through `Upload_Sink.FileValidator`.
- URL path guardrails plus shared post-download validator parity are in place for document-like, audio, and video paths.

### 2.2 Processor Coverage
- Core media processors are established for major ingestion classes (audio, video, PDF, books, plaintext, MediaWiki, OCR/VLM, code paths).
- Processor outputs are normalized into structured payloads with status/content/chunk/metadata semantics.

### 2.3 Persistence + Downstream Integration
- Media DB v2 persistence path is operational for core ingest endpoints.
- Collections/watchlists and successful `/api/v1/media/add` dual-write bridge is implemented.
- Embeddings dispatch contract (`jobs|background|auto`) and provenance metadata contract are implemented.
- Claims extraction remains feature-flagged and non-fatal as designed.

## 3. Delivered Roadmap Stages

### Stage 0 - Foundations (Complete)
- Core processors for major media formats.
- Upload validation with extension/size controls and optional Yara paths.
- Media DB persistence and chunking baseline.
- Watchlists/collections integration and embeddings enqueue hook.

### Stage 1 - Observability & Job Control (Delivered)
- Async ingestion job endpoints + worker (`/api/v1/media/ingest/jobs`) with retry/backoff.
- Standardized `ingestion_*` metrics for failures, durations, and chunk counts.
- Collections provenance metadata consistency (`run_id`, `source_id`, origin tags).
- URL-path validator parity with upload validator for core media classes.
- `/media/add` to collections dual-write bridge.
- Sanitization/documentation hardening defaults for HTML/XML/archive-driven ingestion.
- MediaWiki checkpoint hardening delivered; parity for all long-running flows remains part of future hardening.

### Stage 2 - Backend Parity & Scaling (Delivered)
- SQLite-specific ingestion SQL assumptions removed from targeted runtime paths (including conflict-safe upsert behavior where required).
- Queue-based distributed execution support for heavy workloads (e.g., transcription/OCR).
- Resource Governor ingestion budget enforcement integrated into `/api/v1/media/add` with ledger accounting and admin diagnostics.
- Structure-index hierarchy writes delivered.
- OCR/VLM extraction/chunk parity expansion delivered.

### Stage 3 - Delivered Initial Slice
- Streaming media transcript persistence initial implementation delivered for `/api/v1/audio/stream/transcribe`:
  - Opt-in partial/final transcript snapshots.
  - Persistence through existing Media DB transcript upsert path.
  - Fail-open behavior when persistence is unavailable.

## 4. Delivered API and Data Baseline

### API Baseline
- Persistent ingest: `/api/v1/media/add`.
- Typed process endpoints: `/api/v1/media/process-{audios|videos|documents|pdfs|ebooks|emails}`.
- Web/media ingest variants: `/api/v1/media/process-web-scraping`, `/api/v1/media/ingest-web-content`.
- MediaWiki long-form ingest endpoints.
- Async ingest jobs endpoints.

### Data Baseline
- Media DB v2 baseline entities in active use: `Media`, `DocumentVersions`, `MediaChunks`, `UnvectorizedMediaChunks`, `Keywords`, `MediaKeywords`, `Transcripts`, `Claims`, `DocumentStructureIndex`, `sync_log`.
- Per-user collections storage and link semantics are integrated for watchlists/reading/add flows.

## 5. Delivered Observability and Security Baseline

### Observability
- Standard ingestion counters/histograms for request outcomes, processing duration, validation failures, chunk totals, embeddings enqueue outcomes.
- Structured logging conventions in ingestion paths.

### Security/Compliance Baseline
- Config-driven file size and timeout enforcement.
- Optional Yara support path.
- Sanitization defaults for risky document/web inputs.
- Audit/sync-log attribution through DB writes.

## 6. Acceptance Snapshot

The completed scope is considered delivered for the following criteria:
- Stage 0/1/2 capabilities are present in production code paths.
- Resource Governor integration for ingestion bytes/concurrency is active in `/api/v1/media/add`.
- Queue/distributed handling for heavy ingestion classes is present.
- Structure index and OCR/VLM parity work landed.
- Streaming transcript persistence initial capability is present with fail-open semantics.

## 7. Remaining Work Handoff

Active roadmap items now live in:
- `Docs/Product/Media_Ingestion_Pipeline_PRD.md` (remaining scope only).

That document tracks unfinished Stage 3+ items:
- Agentic ingestion workflows.
- Built-in summary/highlight artifacts.
- Inline quality scoring and remediation.
- Streaming persistence lifecycle hardening beyond initial delivery.

## 8. References
- Remaining PRD: `Docs/Product/Media_Ingestion_Pipeline_PRD.md`.
- Ingestion code: `tldw_Server_API/app/core/Ingestion_Media_Processing/`.
- Database: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`.
- Collections & Watchlists: `Docs/Product/Content_Collections_PRD.md`, `Docs/Product/Watchlist_PRD.md`.
- Infrastructure: `Docs/Product/Infrastructure_Module_PRD.md`.
