# Workflow Brainstorming

This document outlines concrete, production-oriented workflow ideas, what each enables, and the minimal additions needed to implement them cleanly using the Workflows module. It also includes high-leverage new step types to unlock broader scenarios.

## Quick Wins (Works Today)

- News/site monitor → summarize → TTS → notify
  - Graph: process_media(kind=web_scraping) → prompt(summary) → tts → webhook (Slack/Email)
  - Needs: Scheduler (cron) via “workflow_run” job; enable egress allowlist for the webhook host.

- Paper roundup → context pack → daily digest
  - Graph: rag_search(topic queries) → prompt(synthesize insights) → webhook(upload digest) → optional tts
  - Needs: RAG configured; Scheduler for periodic runs.

- FAQ / Q&A from a document
  - Graph: process_media(kind=pdf|xml|ebook) → prompt(generate Q&A) → webhook(save into KB)
  - Needs: Destination API (webhook or MCP tool).

- Podcast/video summary → narration
  - Graph: process_media(kind=podcast) → prompt(summarize) → tts(attach_download_link)
  - Needs: ffmpeg for post-process normalization (optional).

- Researcher “compare sources” brief
  - Graph: map(items) → process_media(web_scraping) → prompt(per-item summaries) → prompt(merge+compare) → webhook
  - Needs: None beyond map/branch.

## Content Engineering

- Multilingual translation + dubbing
  - Graph: process_media(any) → prompt(translate) → tts(lang/voice)
  - Needs: TTS language/voice options (present). Optional dedicated translate step.

- Claims extraction and indexing
  - Graph: process_media(any) → prompt(extract entities/claims as JSON) → webhook → vector store API
  - Needs: Optional “embed” step for direct vectorization.

- Social microcontent generator
  - Graph: process_media → prompt(generate thread/titles/captions) → webhook(schedule posts)
  - Needs: Webhook allowlist; secrets injection for API keys (per-run secrets).

## Ops/Knowledge Management

- Internal release notes digest (GitHub/CI feed)
  - Graph: mcp_tool(fetch commits/releases) → prompt(summarize) → webhook(Slack/Confluence)
  - Needs: MCP tool configured; webhook allowlist.

- Policy/compliance checker
  - Graph: process_media(any) → policy_check → branch(flagged?) → webhook(security) | continue(index)
  - Needs: policy_check step (added).

- Support ticket triage from inbox
  - Graph: process_media(email) → prompt(route/priority/summary) → webhook(create ticket) → optional tts for IVR
  - Needs: Ticketing webhook allowlist.

## Data/AI Engineering

- Dataset distillation for evals
  - Graph: process_media → prompt(extract structured cases) → webhook(store eval dataset) → evaluations run
  - Needs: Optional “eval” step adapter.

- Retrieval re-index job (nightly)
  - Graph: media_ingest(batch) → prompt(tagging/metadata enrichment) → webhook(trigger embeddings/vector jobs)
  - Needs: Scheduling; vector/embeddings APIs.

## User-Facing/Assistant

- Meeting assistant (transcribe → action items)
  - Graph: process_media(audio) → prompt(extract action items) → webhook(create tasks)
  - Needs: Dedicated stt_transcribe + diarize steps (future), or reuse endpoints via process_media.

- Interactive “review & approve” pipelines
  - Graph: process_media → prompt(draft) → wait_for_human → branch(approved?) → webhook(publish) | prompt(revise)
  - Needs: UI affordance to approve/resume runs (wait_for_human supported).

## New Step Types That Unlock More

- policy_check (added)
  - Detects PII/blocked terms/length to gate flow. Emits flags + blocked boolean.

- Candidate future types (optional):
  - rss_fetch/atom_fetch - pull items on demand for monitors.
  - embed - vectorize + upsert into configured vector stores.
  - translate - provider-agnostic translate wrapper.
  - stt_transcribe + diarize - first-class audio transcription steps.
  - notify - simplified internal notifier for common channels.
  - diff/change_detector - compare snapshots for material changes.

## Triggers & Scheduling

- Cron: via /api/v1/scheduler/workflows (CRUD) and “workflow_run” job.
- Event-driven (future): signed inbound trigger endpoint; file-drop watcher.

## Ops Considerations

- Egress/SSRF allowlist enforcement for webhooks/providers.
- Per-run secrets injection, never persisted; mask logs.
- Quotas/rate-limits by tenant/user.
- Prefer Postgres for heavy Workflows usage; SQLite fine for dev.
- Artifacts retention + GC.

## WebUI Enhancements (nice-to-have)

- Cron helper presets, templates gallery, approve/resume UX for wait_for_human.
- Node palette from /step-types schemas/examples.
- Event filtering and payload modal polish (partially present).

## Quick-Start Templates To Ship

- Site Watch + Digest + TTS (cron)
- PDF → Q&A (single-run)
- Paper Roundup (rag_search → summary)
- Policy Checker (policy_check + branch)
- Podcast → Summary → Narration (single-run)
