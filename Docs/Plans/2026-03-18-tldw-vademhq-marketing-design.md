# tldw / VademHQ Marketing Design

**Date:** 2026-03-18

## Summary

This design splits the public marketing presence into two related but distinct surfaces:

- `tldwproject.com` remains the home of the open-source `tldw` project.
- `VademHQ` becomes the commercial landing page for hosted access, with an early-access and managed-cloud posture.

The split avoids forcing one homepage to serve two incompatible jobs. The open-source site should explain the project, its momentum, and why self-hosting matters. The commercial site should convert overwhelmed individuals into hosted-trial users without pretending the product is already enterprise-first.

## Goals

- Refresh the `tldwproject.com` homepage with current product scope and recent progress.
- Keep `tldwproject.com` clearly open-source, privacy-first, and self-hosting oriented.
- Create a separate `VademHQ` landing page with a stronger customer-facing conversion flow.
- Position `VademHQ` as trusted, professional, and modern, but grounded in privacy.
- Keep claims honest: hosted trial and managed cloud are available now; sync + hosted workspace are work in progress.
- Establish a brand bridge between the two sites without blending them into a single funnel.

## Non-Goals

- No attempt to turn the open-source homepage into a SaaS homepage.
- No enterprise procurement page, multi-seat pricing matrix, or JIRA-style admin/billing flow yet.
- No replatforming into the Next.js WebUI; the marketing work should stay in the existing static-site path.
- No new backend or signup infrastructure in this phase.

## Recommended Implementation Venue

Use the existing static marketing site path under `Docs/Website/`.

Reasoning:

- The current `tldwproject.com` source already appears to live in `Docs/Website/index.html`.
- The product WebUI under `apps/tldw-frontend/` is a logged-in application surface, not the cleanest home for a two-brand marketing split.
- Static HTML pages are easier to deploy to separate domains later while still living in the same repository.

Recommended page/file model:

- `Docs/Website/index.html` -> `tldwproject.com`
- `Docs/Website/vademhq/index.html` -> `VademHQ` root page
- `Docs/Website/assets/marketing.css` -> shared visual system
- `Docs/Website/assets/marketing.js` -> shared non-framework interactions if needed

## Brand Architecture

### tldwproject.com

**Role:** Open-source project home

**Audience:**

- self-hosters
- contributors
- technical evaluators
- privacy-sensitive users

**Positioning:**

Open-source, self-hosted research assistant and media analysis platform.

**Primary outcome:**

Get visitors to understand what `tldw` is and move into docs, GitHub, and self-hosted setup.

**Commercial mention:**

Light only. A small hosted-callout block or footer/header link is enough.

### VademHQ

**Role:** Commercial hosted offering

**Audience:**

- broader users drowning in information
- individual researchers, analysts, journalists, and heavy knowledge workers
- people who want the benefits of `tldw` without running infrastructure

**Positioning:**

Trusted, privacy-first hosted `tldw` for people overwhelmed by information.

**Primary outcome:**

Drive `Start hosted trial`.

**Future framing:**

Individuals first. Team and enterprise licensing are on the roadmap, but not the current lead message.

## Messaging Guardrails

### Claims that are safe to make now

- hosted trial / early access
- managed cloud with sign-up
- privacy-first direction
- built on the open-source `tldw` project
- sync + hosted workspace are in progress

### Claims to avoid

- mature enterprise controls
- fully available team workspace sync
- finished multi-seat licensing
- “zero trust” or “end-to-end encrypted” unless the implementation exists and is verified
- any security guarantee that is not already documented and real

## Page Designs

## 1. Updated tldwproject.com Homepage

### Tone

Technical, clear, privacy-first, credible. More structured than the current page. Less “coming soon,” more “here is what exists now.”

### Section Order

1. Hero
2. What’s New
3. Core Capabilities
4. Why Self-Host tldw
5. Quickstart
6. Light Hosted Mention
7. Footer

### Hero

**Headline direction:**

`Open-source research assistant and media analysis platform`

**Supporting copy:**

Explain ingestion, transcription, hybrid RAG, chat, and self-hosted privacy in one tight paragraph.

**Primary CTA:** `Get Started`

**Secondary CTA:** `View on GitHub`

**Trust line:** `Self-hosted. No telemetry. API-first.`

### What’s New

Use a concise update strip or card grid. Recommended highlights:

- `FastAPI + Next.js WebUI`
- `OpenAI-compatible chat, audio, embeddings, and evals APIs`
- `Unified RAG + evaluations`
- `Expanded streaming speech stack`
- `MCP Unified and stronger admin/ops posture`

This section exists to prove momentum and reduce the stale-project impression.

### Core Capabilities

Use a focused feature grid instead of trying to enumerate every subsystem.

Recommended cards:

- Ingest media, documents, and web content
- Transcribe and synthesize speech
- Search with hybrid RAG
- Use local or hosted LLMs behind one interface
- Capture outputs, prompts, and knowledge artifacts
- Run it on infrastructure you control

### Why Self-Host tldw

This section should do more work than the current page.

Core themes:

- privacy and data ownership
- no telemetry
- local or controlled deployment
- open-source auditability
- consistent APIs across local and hosted models

### Quickstart

Retain the practical setup commands already present, but tighten the copy around the recommended path.

Prioritize:

- `make quickstart`
- Docker + WebUI path
- docs links
- localhost references

### Light Hosted Mention

One compact block:

`Need hosted access instead of self-hosting? VademHQ offers managed trials built on the open-source tldw project.`

**CTA:** `Visit VademHQ`

This must not visually compete with the main OSS CTAs.

## 2. VademHQ Landing Page

### Tone

Trusted and professional first, modern and prosumer second, always from a privacy-first direction.

### Section Order

1. Hero
2. Trust Bar
3. Problem Framing
4. Outcome-Focused Features
5. How It Works
6. Privacy / Trust
7. Early Access + WIP Disclosure
8. Future Team / Enterprise Path
9. Final CTA

### Hero

**Headline direction:**

`A calmer way to work with too much information`

Alternative:

`Hosted tldw for people drowning in information`

**Supporting copy:**

Talk about bringing transcripts, files, links, notes, and research into one managed place without having to self-host the stack yourself.

**Primary CTA:** `Start hosted trial`

**Secondary CTA:** `See how it works`

### Trust Bar

Short factual signals:

- `Privacy-first`
- `Managed cloud`
- `Built on open-source tldw`
- `Early access`

### Problem Framing

Lead with overload:

- too many tabs
- too many saved files
- too many transcripts and notes
- too much context spread across tools

Avoid enterprise jargon here.

### Outcome-Focused Features

Do not dump the full project feature matrix. Keep the content outcome-oriented:

- Bring scattered source material into one place
- Search across transcripts, notes, and documents
- Turn long media into usable knowledge
- Use AI assistance without giving up control
- Start fast without running your own infrastructure

### How It Works

Simple 3-step flow:

1. Bring in your sources
2. Search, ask, and connect ideas
3. Keep a living knowledge base instead of a pile of tabs

### Privacy / Trust

This is where the commercial page earns credibility.

Key content:

- privacy-first posture
- managed hosting instead of DIY deployment
- open-source foundation
- honest explanation of current stage

### Early Access + WIP Disclosure

Keep this explicit:

- available now: hosted trial / managed cloud sign-up
- in progress: sync + fuller hosted workspace features

### Team / Enterprise Path

One short section:

`Starting with individuals now. Team and enterprise deployment paths are planned as the product matures.`

That creates room for the later B2B shift without forcing it into the lead message.

### Final CTA

**Primary CTA:** `Start hosted trial`

**Secondary CTA:** `Prefer self-hosting? Visit tldwproject.com`

## Visual Direction

## Shared rules

- Both pages should feel related, but not identical.
- Both should stay privacy-first.
- Avoid generic SaaS gradients with empty claims.
- Mobile and desktop should both feel intentional, not merely functional.

## tldwproject.com visual direction

- dark, atmospheric, project-oriented
- serious and technical
- keep some of the current visual identity, but improve structure and readability

## VademHQ visual direction

- lighter and calmer than the OSS page
- premium editorial feel rather than hacker aesthetic
- strong typography and restrained accents
- clean sections with more whitespace and less density

## SEO / Metadata

Each page should have its own:

- title
- description
- Open Graph title and description
- canonical URL

Recommended canonicals:

- `https://tldwproject.com`
- `https://vademhq.com`

The VademHQ page should not reuse OSS metadata or title structure.

## Cross-Linking Rules

- `tldwproject.com` gets a light hosted pointer to VademHQ
- `VademHQ` gets an explicit “built on open-source tldw” bridge
- `VademHQ` includes a clear self-hosting return path
- neither page should try to do the other page’s job

## Accessibility / QA Requirements

- visible focus states
- skip link
- mobile-safe navigation and CTA layout
- sufficient contrast in both pages
- no misleading hidden claims

## Verification Strategy

Add regression tests that validate:

- both HTML pages exist
- titles and meta descriptions are distinct and correct
- `tldwproject.com` keeps an OSS/self-hosting orientation
- `VademHQ` contains `Start hosted trial`
- `VademHQ` contains the early-access / WIP disclosure
- both pages cross-link appropriately

## Final Recommendation

Implement the marketing refresh as two static sibling sites under `Docs/Website`, backed by shared CSS and small regression tests. This gives the project a clearer open-source home, creates a commercial conversion surface that can mature independently, and avoids entangling public marketing with the logged-in product application.
