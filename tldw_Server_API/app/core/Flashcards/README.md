# Flashcards

Note: This README is scaffolded from the core template. Replace placeholders with accurate details from the implementation and tests.

## 1. Descriptive of Current Feature Set

- Purpose: What Flashcards provides and why it exists.
- Capabilities: Current flashcard generation, review, and export features.
- Inputs/Outputs: Inputs (notes, content) and outputs (decks, cards).
- Related Endpoints: Link API routes (if any) and files.
- Related Schemas: Pydantic models involved.

## 2. Technical Details of Features

- Architecture & Data Flow: Components and data flow.
- Key Classes/Functions: Entry points and how to extend card types.
- Dependencies: Internal modules and external SDKs/services.
- Data Models & DB: Storage schemas via `DB_Management`.
- Configuration: Env vars and config keys.
- Concurrency & Performance: Batching, caching, rate limits.
- Error Handling: Exceptions, retries, and failure modes.
- Security: AuthNZ, permissions, input validation.

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure: Subpackages and responsibilities.
- Extension Points: New card generators, reviewers, or exporters.
- Coding Patterns: DI, logging, rate limiting.
- Tests: Locations, fixtures, example tests.
- Local Dev Tips: Quick start and sample flows.
- Pitfalls & Gotchas: Edge cases and performance notes.
- Roadmap/TODOs: Improvements and backlog items.

