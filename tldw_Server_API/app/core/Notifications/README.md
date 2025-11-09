# Notifications

## 1. Descriptive of Current Feature Set

- Purpose: Unified helper to deliver outputs (primarily Watchlists) via email or store them as Chatbook documents for later review.
- Capabilities:
  - Email delivery (async) via central AuthNZ email service with optional attachments.
  - Chatbook persistence using the Chat document generator and per‑user ChaCha DB.
  - Sensible defaults: fallback to the user’s email when no recipients provided (configurable).
- Inputs/Outputs:
  - Input: subject/body/attachments for email; title/content/metadata for Chatbook.
  - Output: `NotificationResult` with channel/status/details.
- Related Endpoints (usage within Watchlists output delivery):
  - Create notification service and deliver email/chatbook: tldw_Server_API/app/api/v1/endpoints/watchlists.py:2168, tldw_Server_API/app/api/v1/endpoints/watchlists.py:2195, tldw_Server_API/app/api/v1/endpoints/watchlists.py:2223
- Related Schemas: internal dataclass `NotificationResult` (no Pydantic model): tldw_Server_API/app/core/Notifications/service.py:18

## 2. Technical Details of Features

- Architecture & Data Flow
  - `NotificationsService` wires to the AuthNZ email service and Chat document generator to deliver content via two channels: tldw_Server_API/app/core/Notifications/service.py:1
  - Email: `deliver_email(...)` sends one email per recipient via `get_email_service()`; returns aggregated status with per‑recipient results: tldw_Server_API/app/core/Notifications/service.py:40
  - Chatbook: `deliver_chatbook(...)` stores a document in the user’s ChaCha DB using `DocumentGeneratorService`: tldw_Server_API/app/core/Notifications/service.py:87

- Dependencies
  - Email: tldw_Server_API/app/core/AuthNZ/email_service.py (provider configured elsewhere).
  - Chatbook: `CharactersRAGDB` (per‑user DB) and `DocumentGeneratorService`:
    - tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py:1
    - tldw_Server_API/app/core/Chat/document_generator.py:1
  - DB path helpers: tldw_Server_API/app/core/DB_Management/db_path_utils.py:1

- Configuration
  - Email provider/credentials are managed by the AuthNZ email service; this module does not introduce new env variables.
  - Watchlists endpoints construct delivery plans from request payload; attachments are optional and derived from produced content.

- Concurrency & Performance
  - Email delivery is async and performed per recipient; aggregation combines results into a single `NotificationResult`.
  - Chatbook persistence is synchronous and returns the created document ID.

- Error Handling & Safety
  - Email: catches exceptions per recipient and returns `sent|partial|failed|skipped` status (skipped when no recipients are available).
  - Chatbook: returns `stored|failed` with error details on exceptions.

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure
  - `service.py` — `NotificationsService`, email and Chatbook delivery logic, result shape.
- Extension Points
  - Add additional channels (e.g., webhook, in‑app notifications) by adding methods to `NotificationsService` and associated provider wiring.
  - Keep side effects well‑scoped and return a `NotificationResult` for each channel.
- Tests
  - Email and Chatbook flows (fakes/monkeypatches): tldw_Server_API/tests/Notifications/test_notifications_service.py:1
- Local Dev Tips
  - For email, ensure the AuthNZ email provider is configured; otherwise tests should monkeypatch `get_email_service`.
  - For Chatbook, document IDs are written to per‑user ChaCha DB; use a temp DB in tests.
- Pitfalls & Gotchas
  - Avoid large attachments when not necessary; Watchlists helpers include an option to inline or attach content.
  - Ensure recipients are present or enable the fallback to user email when appropriate.
