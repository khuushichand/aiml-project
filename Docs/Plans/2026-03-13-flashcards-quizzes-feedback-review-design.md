# Flashcards And Quizzes Feedback Review Design

Date: 2026-03-13  
Status: Approved

## Summary

This design translates a large body of user feedback about flashcards and quizzes into a repo-grounded feature review for `tldw_server`.

The goal is not to restate every request. The goal is to identify which additions fit the current flashcards/quizzes architecture, which ideas need more groundwork, and which requests should stay out of scope for now.

## Current Baseline

The current implementation already covers a meaningful part of the requested study workflow:

- Dedicated flashcards workspace with `Study`, `Manage`, and `Transfer` tabs.
- Rating-based spaced repetition review with scheduling metadata and analytics summary.
- Deck and card CRUD, tags, bulk import/export flows, and undo-oriented UX patterns.
- Card models for `basic`, `basic_reverse`, and `cloze`.
- APKG import and APKG export support.
- Flashcard generation preview/edit/save flow in `Transfer`.
- Quiz generation, attempts, results, and flashcard-to-quiz handoff.

Relevant code and docs anchors:

- `apps/packages/ui/src/components/Flashcards/`
- `apps/packages/ui/src/components/Quiz/`
- `apps/packages/ui/src/services/flashcards.ts`
- `apps/packages/ui/src/services/quizzes.ts`
- `tldw_Server_API/app/api/v1/endpoints/flashcards.py`
- `tldw_Server_API/app/api/v1/endpoints/quizzes.py`
- `tldw_Server_API/app/api/v1/schemas/flashcards.py`
- `tldw_Server_API/app/api/v1/schemas/quizzes.py`
- `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- `Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md`

## Product Framing

This review uses an architectural-fit lens rather than a pure wishlist lens.

Each candidate feature is evaluated against:

- User pain and repetition in the feedback
- Fit with the existing flashcards/quizzes backend and WebUI
- Scope and implementation surface area
- Reuse of current import, review, and quiz-generation primitives
- Ability to strengthen the module without forcing a new product line

## Recommended Additions

### 1. Structured Q&A Import With Approval Flow

This is the strongest next feature.

The repeated user pain is not “generate cards from anything” in the abstract. It is specifically “take my already-written Q&A and convert it into cards without rewriting it for me.” That maps well to the existing `Transfer` tab and generated-draft review flow.

Recommended scope:

- Accept pasted structured text, Markdown, and lightweight exported note content.
- Parse question/answer blocks into candidate flashcards.
- Present candidates in a review queue before save.
- Allow per-card edit, reject, approve, and bulk approve actions.
- Preserve text fidelity by default and avoid silent LLM rewriting.

Recommended non-scope for v1:

- Live screen-reading
- OneNote runtime integration
- Screenshare capture
- “Create deck from anything on screen”

Why this fits the repo:

- Reuses `Transfer` as the intake surface.
- Extends the existing preview/edit/save generation model.
- Solves the most urgent authoring pain without a new subsystem.

### 2. Whole-Deck Document View Plus Multi-Card Editing

The feedback repeatedly asks for two connected capabilities:

- see the full deck at once
- edit many cards quickly

Those should be treated as one feature family rather than separate projects.

Recommended scope:

- Add a deck-level document or table view in `Manage`.
- Show many cards in one scrollable page with deck/tag filters.
- Support inline edits for common fields.
- Support batch operations from the same surface.
- Preserve the existing drawer-based edit flow for detailed edits.

Why this fits the repo:

- The current `Manage` surface already owns browsing, selection, editing, and bulk actions.
- Existing undo and optimistic-update patterns can extend naturally here.
- This improves both authoring and maintenance after imports.

### 3. First-Class Card Image Support, Then Image Occlusion

The feedback treats images as essential, especially for lecture-slide and anatomy-heavy workflows. The repo currently supports text-oriented cards with `front`, `back`, `notes`, and `extra`, but not first-class card media.

Recommended sequencing:

- Step 1: add durable image support for flashcards
- Step 2: add image occlusion authoring on top of that media model

Why this order matters:

- Image occlusion without a real card-media model will create brittle storage and editing behavior.
- Card media is a reusable primitive for imports, previews, authoring, and future quiz surfaces.

### 4. Scheduler Parity Upgrade

If the module aims to attract serious Anki-style usage, the scheduler matters as much as import/export.

Recommended scope:

- Add an optional modern scheduler path such as FSRS.
- Preserve compatibility with the existing review flow and rating buttons.
- Expose clearer “why is this due?” metadata in the UI.
- Keep review-history-backed calculations explainable and testable.

Why this fits the repo:

- Review history and scheduling fields already exist.
- This is a deep backend improvement inside the current model, not a separate product.

### 5. Card-Level Study Assistant And Quiz Remediation

The strongest AI-native opportunity in the feedback is not general tutoring. It is tight, contextual help while studying.

Recommended scope:

- “Explain this card”
- “Give a mnemonic”
- “Ask a follow-up question”
- “Create practice questions from missed or selected cards”

Why this fits the repo:

- The repo already has broad LLM infrastructure.
- Quiz generation already exists and can be connected more tightly to flashcard state.
- This can stay contextual and lightweight instead of turning into a full tutoring workflow.

## Deferred Ideas That Need Groundwork

### Subdecks / Hierarchical Decks

Valuable, but the current deck model is flat. Proper hierarchy would need schema, query, API, and navigation changes across backend and UI.

### Stronger Anki Round-Trip Fidelity

The repo already supports APKG import/export, so the real next step is higher-fidelity round-tripping rather than claiming “Anki compatibility” as a binary state.

### Per-Card Review History / Question Log

This fits the model well because review data already exists, but it is a secondary layer on top of stronger authoring and in-session assistance work.

## Out Of Scope For This Phase

These ideas were intentionally not recommended for the next repo-grounded roadmap:

- Live screenshare or cross-app scanner workflows
- Direct OneNote runtime ingestion or screen parsing
- Dedicated Anki remote compatibility
- Native iOS app
- Public deck marketplace
- Real-time collaborative deck editing and sharing sync
- Hosted third-party proprietary deck platform

These requests are not invalid. They are simply too far from the current flashcards/quizzes module shape and would force major new product and platform work.

## Recommended Roadmap Order

1. Structured Q&A import with approval flow
2. Whole-deck document view plus multi-card editing
3. First-class card image support
4. Image occlusion authoring
5. Scheduler parity upgrade
6. Card-level study assistant and quiz remediation

This order is deliberate:

- Start by improving capture because that is the strongest repeated user pain.
- Improve maintenance next so larger imported decks stay usable.
- Add media primitives before media-heavy authoring workflows.
- Upgrade scheduling after authoring throughput is stronger.
- Layer contextual AI study help after the core study loop is more complete.

## Explicit Decisions

- Translate the user’s “scanner” request into a buildable structured Q&A import feature, not live capture.
- Treat “see the whole deck” and “edit many cards at once” as one roadmap item.
- Do not market APKG support as full Anki parity.
- Do not expand current scope into mobile-native, device-hardware, or collaborative-platform work in this phase.

## Success Criteria For This Review

This review is successful if it:

- Distinguishes existing capabilities from missing ones
- Converts broad feedback into repo-native feature candidates
- Identifies the smallest high-value next step
- Protects the current module from scope distortion

## Next Planning Target

The next implementation-planning step should focus on:

`Structured Q&A import with approval flow`

That feature has the best combination of user value, architectural fit, and reuse of the current flashcards transfer pipeline.
