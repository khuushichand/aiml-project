# Meeting Intelligence Transcription Suite PRD

- **Product Name**: Meeting Intelligence Transcription Suite (working title)
- **Author / Date**: _[Update author]_ / 2025-10-20

## Background

Current transcription workflows focus on generic media ingestion. Power users need meeting-first capabilities: guided structure, actionable insights, and shareable artifacts similar to Granola, Hyprnote, and Shadow. This PRD covers the first release of a meeting-optimized experience across API and WebUI.

## Goals

- Deliver meeting-ready transcripts surfacing decisions, next steps, owners, and highlights without manual cleanup.
- Enable reusable templates for recurring meeting types (stand-up, discovery call, research interview, etc.).
- Integrate transcripts with downstream RAG/chat features for fast follow-ups.
- Support both real-time capture and rapid post-call processing.
- Raise diarization accuracy and speaker attribution confidence for multi-speaker meetings.

## Non-Goals

- Building a conferencing client.
- General document summarization beyond meeting focus.
- Full CRM/PM workflows (provide exports/hooks only).

## Personas & JTBD

- **Product Manager “Riley”** - runs cross-functional meetings; wants quick recap with assigned owners.
- **Sales Lead “Jordan”** - logs discovery calls; needs CRM-ready notes covering objectives, objections.
- **Researcher “Morgan”** - conducts interviews; wants tagged insights, highlight reels, follow-up tasks.
- **Ops Admin “Casey”** - manages process templates; enforces taxonomy, audits compliance.

## Use Cases

- Stand-up: auto-structured summary (`yesterday/today/blockers`) via template.
- Discovery Call: real-time capture → instant summary, action items synced downstream.
- Interview Review: highlights by question, auto-tagged insights.
- Board Meeting: shareable agenda, decisions, next steps, private note stream.

## User Experience

- **Entry Points**: schedule capture (calendar + template), join live meeting (stream ingest), import recording.
- **Template Selection**: library of defaults + organization templates with sections, prompts, tags.
- **Template Controls**: org/team admins decide whether default templates are available and can toggle user-created templates on/off.
- **Real-Time View**: live transcript stream, section progress, inline action items.
- **Post-Processing**: summary cards (Decisions/Risks/Action Items), sentiment heat map, speaker stats.
- **Collaboration**: assign owners, inline editing, export (PDF/Markdown/JSON), push to Slack/Notion/Trello.
- **Search**: filters by meeting type, participants, tags; highlight snippets with waveform context.

## Functional Requirements

- Ingestion: accept audio/video uploads, meeting IDs; prepare connectors (Zoom/Meet/Twilio in later phase).
- Speaker diarization & naming: improved diarization with optional participant mapping.
- Template engine: JSON schema defining sections, prompts, output instructions, follow-up tasks.
- Template governance: base templates ship by default; organizations/teams can enable, disable, or extend them; organization/team owners (admins, team leads) manage shared templates; end users can create personal templates when the feature is toggled on.
- Action item detection: highlight tasks with regex + LLM confirmation; attach due dates and owners.
- Note views: combined transcript/summary/insights with redaction controls.
- Multi-language support: leverage existing STT models with translation fallback and confidence metadata.
- Storage: persist meeting entities and artifacts in existing `Media_DB` structures and transcript tables; enhancements focus on the pipeline leading into ingestion rather than redefining post-ingestion storage.
- API endpoints: CRUD for templates, sessions, artifacts; webhooks for completion; streaming SSE for live updates.
- Security: respect AuthNZ modes, row-level access, redact sensitive segments in logs/export.
- Rate limiting: per-tenant concurrency caps, throttle by meeting duration.

## Success Metrics

- ≥40% of transcription sessions using templates within 30 days.
- <5 minute median time from meeting end to summary availability.
- ≥90% user-rated accuracy on speaker attribution and action item ownership.
- 25% reduction in manual note-taking time (user survey).
- ≥30% of meetings exported or shared via integrations.

## Competitive Inspiration

- **Granola** - guided pre-meeting briefs, real-time anchored notes.
- **Hyprnote** - templated notes, AI-suggested follow-ups, shareable history.
- **Shadow** - robust diarization, secure workspace, knowledge graph linking.

## Technical Approach

- **Pipeline**: reuse existing STT stack (faster_whisper, NeMo, Qwen2Audio); extend chunking to persist template context; integrate enhanced diarization via upgraded models or libraries (e.g., pyannote) and tune for meeting scenarios.
- **LLM Prompts**: template-specific prompt library with deterministic formats; provider fallback logic.
- **Template Engine**: store in DB with versioning; validate via Pydantic schemas.
- **Real-Time Transport**: WebSocket primary, SSE fallback; broadcast structural updates via incremental JSON patches.
- **Storage**: leverage current `Media_DB` meeting/transcript tables; add required metadata columns or link tables while keeping downstream ingestion flows unchanged.
- **Search/RAG**: index summaries + transcripts with meeting IDs for contextual retrieval.
- **Integrations**: Phase 1 exports (Markdown, JSON, Slack webhook); Phase 2 calendar ingestion (Google/Outlook) and CRM connectors (HubSpot/Notion).
- **Security & Compliance**: encryption at rest, optional PII redaction patterns, audit logging.
- **Performance**: streaming latency <2s; full summary completion within SLA; background tasks for artifact generation.

## Phased Roadmap

1. **MVP (≈6 weeks)**
   - Template CRUD + default library
   - Meeting metadata schema, offline processing pipeline
   - Summary & action items generation
   - WebUI: template picker, transcript + summary view, manual owner assignment
   - API docs & automated tests
   - Instrumentation scaffold: event tracking for template usage, baseline metrics, feedback hooks

2. **Live Experience (≈8 weeks)**
   - Real-time streaming UI and SSE endpoint
   - Live action item callouts, diarization updates
   - Slack export, manual calendar import (ICS)
   - Expand analytics: latency reporting, post-meeting survey prompt

3. **Integrations & Intelligence (≈10+ weeks)**
   - Automated owner mapping from calendar participants
   - CRM/PM exports (Notion, HubSpot, Jira)
   - Analytics dashboards (meeting trends)
   - Knowledge base linking within RAG

## Dependencies & Risks

- Diarization accuracy for multi-speaker meetings (need evaluation of model trade-offs).
- Prompt consistency across LLM providers; regression testing for each template.
- WebUI performance with long transcripts.
- Compliance requirements around data retention and redaction.
- Third-party integration timelines (OAuth approvals, API quotas).
- LLM provider costs and throttling when handling concurrent real-time sessions.

## Test Strategy

- Unit tests for template engine, action item extractor, summary prompt logic (mocked LLM).
- Integration tests for meeting pipeline (ingest → artifact).
- Load tests for concurrent live meetings and long recordings.
- UX acceptance tests with seeded meeting recordings.
- Red-team testing focused on PII redaction and access control.

## Analytics & Instrumentation

- Track template usage, summary edits, export destinations.
- Monitor STT/LLM error rates and latency (Loguru + structured metrics).
- Gather user feedback post-meeting via optional prompt.
- Establish pre-launch baselines for manual note-taking effort and diarization accuracy to compare post-launch metrics.

## Open Questions

- Policy for cross-team template visibility when multiple teams exist under one org.
- Handling partial attendance or late joins in diarization mapping.
- Requirements for fully offline/on-prem deployments.
- Integration prioritization (Slack, Notion, HubSpot, Jira, etc.).
- Monetization strategy: free tier limits vs. premium features.

## Next Steps

1. Re-review PRD scope and governance wording; refine while context is fresh.
2. Plan enhanced diarization spike: select candidate models, assemble sample recordings, define accuracy metrics.
3. Map instrumentation work: enumerate events, fields, and storage strategy for metrics and surveys.
4. Outline template governance implementation: default set definition, toggle controls, admin/user flows.
5. Draft UX flow sketches for scheduling, live view, and recap; align API contracts for template CRUD and meeting sessions.
6. Build solo execution checklist: break roadmap into weekly milestones with deliverables and validation steps.
