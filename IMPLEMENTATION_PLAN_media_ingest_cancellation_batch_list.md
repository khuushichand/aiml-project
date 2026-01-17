## Stage 1: Batch job list endpoint
**Goal**: Add a batch list endpoint for media ingest jobs and cover it with tests.
**Success Criteria**: `GET /api/v1/media/ingest/jobs?batch_id=...` returns matching jobs for owner/admin; integration test passes.
**Tests**: `python -m pytest tldw_Server_API/tests/MediaIngestion_NEW/integration/test_media_ingest_jobs.py -k batch`
**Status**: Complete

## Stage 2: Deeper cancellation in audio/video pipelines
**Goal**: Propagate cancellation into ffmpeg/STT steps and surface cancelled results.
**Success Criteria**: FFmpeg conversion and Whisper segmentation honor cancel checks; audio/video pipelines return `Cancelled` without DB writes.
**Tests**: `python -m pytest tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_cancellation.py`
**Status**: Complete

## Stage 3: Deployment documentation updates
**Goal**: Document media ingest worker flag and batch list endpoint in deployment/env docs.
**Success Criteria**: Deployment guides and env var lists mention `MEDIA_INGEST_JOBS_WORKER_ENABLED`.
**Tests**: N/A
**Status**: Complete
