# tldw Homepage Messaging Refresh Design

**Date:** 2026-03-21

## Summary

This phase keeps the currently restored old `tldwproject.com` homepage structure, but rewrites the broader homepage copy so it reads like a serious open-source, self-hosted research tool while keeping `The Young Lady's Illustrated Primer` as the central project ambition. The page should show what `tldw` does today, but the Primer goal should remain the core thesis rather than a side reference.

## Goals

- Keep the old live homepage structure and styling.
- Reframe the homepage around a practical, self-hostable tool people can run now.
- Keep `The Young Lady's Illustrated Primer` as the main project goal in the homepage story.
- Prioritize self-hosters and curious end users over contributors or platform evaluators.
- Give the page a more open-source / hackerish tone instead of generic product-marketing language.
- Keep setup instructions from phase 1 intact and accurate.

## Non-Goals

- No redesign of the homepage layout, art direction, or navigation.
- No changes to `Docs/Website/vademhq/index.html`.
- No attempt to turn the OSS homepage into a SaaS landing page.
- No feature-matrix explosion in the hero itself.

## Approved Direction

The homepage should lead with:

- a direct job-to-be-done line
- explicit connection to `The Young Lady's Illustrated Primer`
- self-hosted, privacy-first operation
- dense open-source capability proof beneath the hero

The homepage should not lead with:

- generic startup language
- soft productivity framing
- hiding the project's larger ambition

## Copy Strategy

### Hero

- Keep the old visual structure.
- Lead with a direct job line such as ingesting, transcribing, searching, and talking to source material.
- Explicitly name `The Young Lady's Illustrated Primer` in the hero copy.
- Make the lead read like a self-hosted step toward that goal, not a generic productivity tool.

### Quick Start

- Keep the factual quickstart blocks from phase 1.
- Tighten the intro copy so it feels calmer and less procedural.

### About

- Make this the philosophical center of the homepage.
- Say plainly that the project is trying to build toward a Primer-like assistant.
- Explain that the current software is the open-source, self-hosted path toward that goal through ingestion, transcription, retrieval, APIs, notes, prompts, and control over the stack.

### Proof Panel

- Keep the right-hand panel dense and technical.
- Use it as a serious OSS capability slab, not polished trust-marketing.
- Favor categories like OpenAI-compatible APIs, FastAPI + WebUI, hybrid RAG, local or hosted models, STT/TTS, MCP, notes/prompts/chatbooks, and wide format support.

### Features

- Keep outcome-oriented headings, but make the body copy more concrete and infra-minded.
- Favor phrases like ingest messy sources, retrieve across transcripts and docs, run local or hosted models, and self-host and inspect the stack.

### FAQ

- Stay honest about beta status.
- Use a blunter, more technical tone.
- Keep privacy, support, and contribution guidance intact.

## Verification

Update homepage regression tests so they continue to enforce:

- old live structure remains intact
- setup/version guidance from phase 1 remains accurate
- hero names the direct job and the Primer goal
- about copy keeps the Primer as the main project ambition
- dense capability proof remains visible
- outdated generic-practical copy from the rejected pass is removed
