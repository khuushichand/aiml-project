# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to Some kind of Versioning


## [0.1.25] 2026-02-X

### Added

- Alibaba Model Studio image backend support for `/api/v1/files/create` image generation via the new `modelstudio` backend.
- Model Studio adapter support for sync generation, async task submission/polling, and `auto` mode.
- Model Studio image configuration fields in `[Image-Generation]`:
  `modelstudio_image_base_url`, `modelstudio_image_api_key`, `modelstudio_image_default_model`, `modelstudio_image_region`, `modelstudio_image_mode`, `modelstudio_image_poll_interval_seconds`, `modelstudio_image_timeout_seconds`, `modelstudio_image_allowed_extra_params`.
- Qwen region-based endpoint presets for native HTTP chat routing (`sg`, `us`, `cn`) plus `qwen_api_region` config support.
- Curated Qwen model entries (`qwen-max`, `qwen-plus`, `qwen-turbo`) in model pricing/catalog metadata.
- Qwen provider mapping in LLM provider metadata endpoint wiring so Qwen models appear correctly.
- Regression coverage for Model Studio adapter behavior, config defaults, image allowlist behavior, image model listing, and Qwen base URL precedence/region routing.
- Workspace banners
  - Per-workspace custom header banner support in Research Workspace (`/workspace-playground`) with title, subtitle, and image.
  - New banner rendering surface in Workspace UI (`WorkspaceBanner`) with graceful no-image fallback styling.
  - “Customize banner” modal in Workspace header menu with upload, preview, save, remove-image, and reset flows.
  - Banner image normalization utility for local uploads (JPEG/PNG/WebP validation, resize, encoding, and byte-cap enforcement).
  - Extension parity route support for `/workspace-playground`.
  - Regression coverage for banner defaults, lifecycle persistence, bundle round-trip, header modal behavior, quota eviction, conflict labeling, and extension route parity.
- Skills authoring + seed UX
  - Added built-in `feynman-technique` skill under `tldw_Server_API/app/core/Skills/builtin/`.
  - Added importable `feynman-technique-template` skill under `Docs/Prompts/Skills/`.
  - Added Feynman prompt template at `Docs/Prompts/Academic-or-Studying/Feynman_Technique.md`.
  - Added Skills Manager built-ins seeding dropdown actions for both `Seed Missing Only` (`overwrite=false`) and `Seed and Overwrite Existing` (`overwrite=true`).
  - Added protocol-sync regression coverage for Feynman skill/prompt assets in `tldw_Server_API/tests/Skills/unit/test_feynman_assets_sync.py`.
- Added regression coverage ensuring Watchlists pipeline setup propagates HTML template format into generated job and output payloads.
- Watchlists guardrails and release-gate coverage:
  - Added static duplicate guard coverage for Watchlists source files (`useWatchlistsStore` selector reuse, duplicate top-level identifiers, duplicate interface keys).
  - Added `test:watchlists:typecheck` package script and wired it into the Watchlists scale gate workflow to prevent silent duplicate/type-regression drift.
  - Added/updated regression coverage for quick-setup candidate preview mocking, accessibility toggle labeling contracts, and run-notification polling harness consistency.

### Changed
- Workspace snapshot lifecycle now fully persists banner state across create/switch/duplicate/archive/restore/import/export pathways.
- Workspace bundle schema now includes `workspaceBanner` and preserves banner state on zip/json import/export.
- Cross-tab conflict detection now tracks `workspaceBanner` as an explicit conflict field.
- Storage recovery logic now evicts archived banner images before more destructive workspace eviction steps.
- Persistence diagnostics now surface a dedicated `workspaceBanner` byte section.
- ZIP import parsing now supports environments without `File.arrayBuffer()` via a safe fallback reader path.
- Qwen base URL resolution precedence is now explicitly ordered as:
  request `base_url` -> `QWEN_BASE_URL` -> config `qwen_api.api_base_url` -> region preset.
- Model Studio base URL resolution now uses region presets when explicit base URL overrides are unset.
- Model Studio payload construction was refactored to remove duplicate model/extra-parameter logic across sync and async builders.
- Env-var and image setup docs were updated for Model Studio and Qwen routing, including grouped readability improvements for `[Image-Generation]` key listings.
- Feynman skill/prompt assets now use a shared `protocol_version` marker key (replacing mixed legacy markers).
- Importable `feynman-technique-template` now defaults to `disable-model-invocation: true` to avoid duplicate auto-invocable behavior after import.
- Watchlists pipeline contract now carries selected template format (`md` or `html`) through job defaults and output-create payload construction instead of forcing Markdown.
- Watchlists source delete confirmation copy now reuses a single locale key across standard and in-use delete flows to reduce translation-key duplication.
- Watchlists guided quick setup now uses a single audio preference field (`includeAudioBriefing`) across telemetry, preview copy, and submission flow instead of dual field state.

### Removed
- No removals in this session.

### Fixed
- Fixed `modelstudio_image_mode=auto` to actually do sync-first fallback to async.
- Fixed validation so `payload.extra_params.mode` is accepted for Model Studio control flow without requiring passthrough allowlisting.
- Fixed user-facing error hygiene by sanitizing Model Studio transport exception details while logging internals.
- Fixed potential SSRF path by validating response-provided remote image URLs against egress policy/allowlist before fetch.
- Fixed `modelstudio_image_region` no-op behavior by wiring it into endpoint selection.
- Fixed missing docstring on `_coerce_choice` in image generation config helpers.
- Fixed bundle import compatibility in environments lacking `File.arrayBuffer()`.
- Fixed invalid imported banner image payload handling to fail soft (drop bad image, preserve banner text fields).
- Fixed a Watchlists UC2 mismatch where selecting an HTML template could still generate Markdown outputs due to hardcoded `default_format`/`format`.
- Fixed duplicate English locale maintenance drift for source delete undo-window messaging by consolidating copy to `sources.deleteConfirmDescription`.
- Fixed newly added Watchlists API audio-briefing tests to comply with typing/docstring standards by adding explicit fixture type hints, return annotations, and test docstrings.
- Fixed Watchlists static-guard false positives by distinguishing type/value namespaces and limiting interface-property scans to top-level declarations.
- Fixed Watchlists quick-setup review/test-flow regressions caused by stale CTA label assumptions and missing source-preview service mocks in the Overview test suite.
- Fixed Watchlists a11y/load-retry test drift for Sources/Monitors toggles by aligning assertions with row-context ARIA labels and current table-render behavior.


## [0.1.24] 2026-02-22

### Added

- Persona memory namespace resilience improvements:
  - Added deterministic persistent fallback namespace keying when `scope_snapshot_id` is missing:
    - `persistent_fallback_sid_<sha256(session_id)>` in persona memory integration.
  - Added deterministic legacy persistent namespace mapping for older null-scope entries:
    - `persistent_legacy_pid_<sha256(user_id:persona_id)>`.
  - Added DB-level namespace backfill helper:
    - `backfill_persona_memory_scope_namespace(...)` on `CharactersRAGDB`.
- Persona regression coverage additions:
  - Added persistent fallback namespace isolation test for missing-scope persistent sessions.
  - Added retrieval-triggered legacy null-scope backfill test for persistent persona memory entries.
  - Added DB unit test verifying selective backfill behavior (only missing-scope rows, optional missing-session gate).
- Locale rollout completion for persona unsaved-draft prompts:
  - Added localized `persona.unsavedState*` prompt copy for remaining non-English sidepanel locales:
    - `ar`, `da`, `fa`, `it`, `ko`, `ml`, `no`, `pt-BR`, `ru`, `sv`, `uk`, `zh-TW`.
- Added implementation-plan docs for this session’s persona slices:
  - `Docs/Plans/IMPLEMENTATION_PLAN_persona_unsaved_draft_locale_rollout_stage23_2026_02_22.md`
  - `Docs/Plans/IMPLEMENTATION_PLAN_persona_memory_namespace_fallback_stage24_2026_02_22.md`
  - `Docs/Plans/IMPLEMENTATION_PLAN_persona_namespace_legacy_backfill_stage25_2026_02_22.md`
- Watchlists UX IA/onboarding improvements:
  - Aligned user-facing Watchlists terminology for Activity/Reports across tabs, overview cards, and help labels.
  - Added always-visible Watchlists task shortcuts (`Set up feeds`, `Configure monitors`, `Check activity`, `Review articles`, `View reports`) for direct navigation.
  - Expanded guided quick setup with goal selection (`Generate briefing reports` vs `Feed review only`) and destination routing to Reports when briefing setup completes without run-now.
  - Refreshed guided-tour copy to explicitly explain feed -> monitor -> activity -> articles -> reports pipeline relationships.
  - Added onboarding telemetry capture for quick setup and guided tour funnels to measure step completion and drop-off.
- Watchlists briefing/audio delivery UX improvements:
  - Added audio briefing controls in monitor configuration for voice, speed, and target duration with safe range normalization.
  - Added monitor authoring modes (`Basic` vs `Advanced`) to reduce first-run form complexity while preserving advanced state in payloads.
  - Added template editor authoring modes (`Basic` vs `Advanced`) to separate focused editing from expert tools (snippets/docs/version tools).
  - Added Basic-mode template recipe builder with structured presets (`briefing_md`, `newsletter_html`, `mece_md`) and one-click recipe application.
  - Added explicit warning when advanced monitor settings are hidden by switching back to Basic mode.
  - Added advanced filter scaffolding with per-rule plain-language summaries, regex examples/flags, and inline regex validation feedback.
  - Added early `Preview impact` action in filter authoring to expose sample ingestion outcomes sooner in the workflow.
  - Added advanced cron scaffolding with five-field guidance, invalid-format hints, and one-click schedule examples (`Daily 09:00`, `Weekdays 08:00`, `Every 6 hours`).
  - Added monitor/template authoring telemetry for start, mode-switch, save, Basic-step completion, and recipe-application adoption tracking.
  - Added a unified Watchlists overview health model with cross-tab attention badges (Feeds/Activity/Reports) and direct "attention needed" deep links from Overview.
  - Extended watchlists output prefs typing to include audio briefing fields used by backend workflow orchestration.
  - Improved Outputs artifact visibility with explicit Markdown/HTML/Audio badges in table rows.
  - Added binary-safe audio output download support to prevent corrupted MP3 delivery.
  - Added in-drawer audio playback for generated audio outputs alongside existing text/HTML preview flows.
  - Hardened live RSS E2E briefing tests to current Watchlists response contracts (`run.stats.*`, source-preview `total/items`) and validated UC2 real-feed flow end-to-end.
  - Added regression coverage for audio monitor payload behavior, output artifact metadata classification, and drawer audio preview rendering.
- Watchlists reliability/remediation UX improvements:
  - Standardized monitor/source/run error remediation copy via shared `mapWatchlistsError` usage in source test preflight, run detail load failures, and monitor save fallback handling.
  - Added DNS/TLS-specific remediation mapping and locale keys to reduce ambiguous failure handling.
  - Added direct retry affordances on source preflight and run-detail load failure surfaces with regression coverage.
  - Added grouped run notification fan-in with dedupe and deep-link payloads to prevent repeated toast spam during multi-run failure bursts.
  - Added stalled-run detection in notification polling and a persistent Runs-tab reliability attention banner with direct run/filter actions.
- Watchlists article workflow and scale guardrail improvements:
  - Added explicit route query handoff for Watchlists tab/filter deep links (`tab`, source/status/smart/search, job/run/output IDs) so cross-tab context is restorable and testable.
  - Added regression coverage for article-to-monitor/run/reports handoff and include-in-next-briefing action paths.
  - Added shared watchlists scale guardrail metadata (`WATCHLISTS_SCALE_GUARDRAILS`, `WATCHLISTS_SCALE_SCENARIOS`) and wired perf/load tests to those constants for repeatable threshold tracking.
- Watchlists accessibility and inclusivity hardening (Plan 06 closeout):
  - Completed staged accessibility delivery for keyboard focus restoration, screen-reader live announcements, non-color status encoding, and plain-language onboarding/scheduling/template guidance.
  - Added release-gate checklist pass-rate tracking for Watchlists accessibility categories and recorded residual non-critical/manual review items.
  - Confirmed accessibility regression matrix remains green in touched flows with no critical keyboard/SR defects.
- Watchlists coordinated UX program closeout:
  - Added cross-stream closeout report with verification summary and owned deferred backlog:
    - `Docs/Plans/WATCHLISTS_UX_PROGRAM_CLOSEOUT_2026_02_22.md`
- Chat rich-text regression coverage additions:
  - Added `st_compat` LaTeX rendering regression test for inline and block math in:
    - `apps/packages/ui/src/utils/__tests__/chat-rich-text.test.ts`

### Changed

- Persona locale parity test enforcement:
  - Updated sidepanel persona locale test to require non-English localized copy for all non-English locale bundles (not only priority locales).
- Persona WS auth test harness/runtime stability:
  - Updated Persona WS auth tests to mount a local `FastAPI` app with persona router instead of importing `app.main`.
  - Updated API key manager test doubles to align with current auth validation call signature (`required_scope` support).
- Persona persistent-memory retrieval behavior:
  - Retrieval path now performs legacy namespace reconciliation/backfill for persistent mode when runtime scope is missing, while preserving explicit scope/session namespace behavior.
- Chat rich-text rendering pipeline:
  - Updated `st_compat` rendering to use a dedicated `Marked` instance with KaTeX extension wiring (matching existing markdown math support expectations).

### Removed

- No removals in this session.

### Fixed

- Fixed persistent-scoped persona memory retrieval blackhole cases when `scope_snapshot_id` is absent by introducing deterministic fallback namespace keying.
- Fixed backward compatibility for older persistent persona memory rows with null `scope_snapshot_id` by adding deterministic legacy namespace mapping and scoped backfill.
- Fixed Persona full-suite runtime instability caused by heavy app import side effects in auth tests.
- Fixed Persona auth test contract drift with API key validation scope handling.
- Fixed Watchlists OPML bulk import preflight handling for wrapped upload objects (`originFileObj`), restoring `SourcesBulkImport.preflight-commit` test coverage.
- Fixed Watchlists admin runs wrapper route contract by restoring redirect behavior to `/admin/server`.
- Fixed Watchlists suite runtime abort path in constrained environments by stubbing heavy STT imports (`torch`/`faster_whisper`/`transformers`) in Watchlists test setup.
- Fixed missing LaTeX rendering in `st_compat` chat rich-text mode by enabling KaTeX processing for the `marked`-based render path.

## [0.1.23] 2026-02-22

### Added

- OpenAI OAuth BYOK account-linking support (opencode-style) under existing user key routes:
  - Added `POST /api/v1/users/keys/openai/oauth/authorize`.
  - Added `GET /api/v1/users/keys/openai/oauth/callback`.
  - Added `GET /api/v1/users/keys/openai/oauth/status`.
  - Added `POST /api/v1/users/keys/openai/oauth/refresh`.
  - Added `DELETE /api/v1/users/keys/openai/oauth`.
  - Added `POST /api/v1/users/keys/openai/source` for active credential source switching.
- OpenAI OAuth UI linkage in settings:
  - Added OpenAI account-linking card actions for `Connect OpenAI`, `Check status`, `Refresh`, `Disconnect`, and `Use API Key Instead`.
  - Added frontend API client methods/types and OpenAPI guard entries for the new OpenAI OAuth routes.
- OAuth/credential lifecycle coverage additions:
  - Added SQLite state-repository cap enforcement coverage for outstanding OAuth state rows.
  - Added frontend service-level regression coverage for OpenAI OAuth endpoint contracts.
- Workspace account storage wiring in `/workspace-playground`:
  - Added authenticated client support for `GET /api/v1/users/storage`.
  - Added account quota fallback via `GET /api/v1/users/me/profile?sections=quotas`.
  - Added workspace header support for account usage/quota alongside local payload usage.
- Quick Chat pop-out context state support:
  - Added source-route serialization/restore for pop-out sessions so docs-mode retrieval and guide routing remain page-aware.
  - Added dedicated pop-out state normalization/validation helper for safer session payload parsing.
- Workspace persistence architecture upgrades:
  - Added split-key persistence (`index` + per-workspace `snapshot`/`chat`) with legacy monolith migration.
  - Added IndexedDB offload path for heavy chat/artifact payloads with localStorage pointer metadata.
  - Added rollout controls for split-key and IndexedDB offload (env + localStorage feature flags).
  - Added development diagnostics for workspace persistence payload size/write-count tracking.
  - Added design documentation: `Docs/Design/Workspace_Persistence_Architecture.md`.
- Expanded regression coverage:
  - Added API client tests for `/api/v1/users/storage`.
  - Added workspace persistence tests for split-key migration/fallback, IndexedDB flag-off behavior, chat-retention bounds, and server-backed artifact truncation.
  - Added backend user-profile quota tests for live storage override and fallback behavior.
  - Added Quick Chat regression tests for pop-out state parsing, sidepanel tutorial resolution behavior, and workflow-card parsing without explicit `routeLabel`.
- Added and completed implementation plans for workspace UI refresh and workspace storage efficiency rollout.
- Request-core security regression coverage:
  - Added tests for default-deny absolute URL behavior, explicit absolute-origin allowlist behavior, and no-auth-header behavior for allowlisted absolute requests.
- HTTP egress DNS pinning regression coverage:
  - Added tests for egress resolved-IP override behavior and resolved-IP propagation in policy evaluation.
  - Added HTTP client tests ensuring per-request host resolution is pinned across repeated egress checks and redirect hops.
- Watchlists selector safety hardening:
  - Added guardrails for user-controlled selector expressions so overly complex XPath/CSS rules are rejected during both selector validation and runtime selection.
  - Added environment-configurable selector limits:
    - `WATCHLIST_SELECTOR_MAX_EXPR_LEN`
    - `WATCHLIST_SELECTOR_MAX_XPATH_DESCENDANT_STEPS`
    - `WATCHLIST_SELECTOR_MAX_XPATH_PREDICATES`
    - `WATCHLIST_SELECTOR_MAX_XPATH_FUNCTION_CALLS`
  - Added regression coverage for complex-selector rejection and environment override behavior.
- Extension bundle compatibility hardening:
  - Added a bundle-contract test to ensure `TemplateCodeEditor` does not import `next/dynamic`, preventing extension build regressions in non-Next runtimes.
- Media search remediation regression coverage:
  - Added backend search-contract tests verifying `/api/v1/media/search` forwards `boost_fields` and relevance ordering changes under field-weight differences.
  - Added frontend integration coverage for metadata-mode constrained search path serialization and metadata-result snippet rendering.
  - Added frontend integration coverage for `ViewMediaPage` no-results recovery wiring (`clear search`, `clear filters`, `quick ingest` event dispatch).
  - Added/confirmed request-churn guard coverage for debounced rapid typing with active filters.

### Changed

- OpenAI OAuth runtime retry semantics in provider call paths:
  - Chat, embeddings, and audio OpenAI OAuth `401` handling now force-refreshes once and retries once.
  - If refresh/retry fails, handlers now propagate the original auth-class error (strict plan) instead of converting to reconnect-required payloads.
- OpenAI OAuth observability:
  - Added `byok_oauth_401_retry_total{provider,outcome}` outcome instrumentation for chat, embeddings, and audio retry flows.
- OpenAI OAuth endpoint contract hardening:
  - OAuth authorize tests now require and verify configured redirect URI propagation in the generated authorization URL.
- Workspace Playground layout and interaction model:
  - Refined shell hierarchy and status signaling.
  - Converted empty-state examples into actionable prompt chips that seed composer input.
  - Reduced composer control clutter while preserving mode/model/advanced controls.
  - Kept composer anchored at the viewport bottom with transcript scroll region above it.
  - Improved center-pane width reflow as sidebars collapse (`comfortable`/`expanded`/`full` behavior).
  - Removed residual max-width caps that left visible unused right-side space.
- Storage indicator clarity and policy:
  - Updated header copy to `Capacity Payload ... | Account ... | Browser ...` with clearer tooltip wording.
  - Replaced hardcoded 5 MB payload budget with env-configurable workspace payload budget:
    - `VITE_WORKSPACE_STORAGE_PAYLOAD_BUDGET_MB`
    - `NEXT_PUBLIC_WORKSPACE_STORAGE_PAYLOAD_BUDGET_MB`
  - Updated payload estimation to include both monolithic and split-key workspace storage entries.
- Workspace persistence efficiency/safety:
  - Persisted chat sessions now retain the most recent 250 messages per workspace.
  - Oversized server-backed artifact payloads are truncated/stripped in local persistence while preserving server-backed references.
- Characters manager table density styling:
  - Refactored Ant Design table density selectors to shared `.ant-table-cell` targeting and centralized common vertical alignment for easier maintenance.
- Backend quota sourcing:
  - User profile quota assembly now prefers live storage metrics from `calculate_user_storage(...)` for `storage_used_mb` and `storage_quota_mb`, with fallback to stored user values on failure.
- Quick Chat guide/tutorial behavior:
  - Tutorial registry lookups now support an explicit suppression bypass for call sites that need route-scoped tutorial discovery outside options-runtime defaults.
  - Browse Guides per-page tutorial lookup now opts into this explicit bypass for sidepanel-hosted Quick Chat.
  - Workflow-card parsing now treats `routeLabel` as optional and derives fallback labels from route paths when omitted.
  - Quick Chat workflow-card settings hint text now matches validation semantics (`title/question/answer/route` required; `id/routeLabel/tags` optional).
- Structured-output parser documentation:
  - Added module/function docstrings in `tldw_Server_API/app/core/LLM_Calls/structured_output.py` clarifying candidate parsing order and strict/lenient semantics for shared endpoint and claims parsing paths.
- Request core transport hardening:
  - Absolute `http(s)` request targets are now blocked by default unless their origin is explicitly included in `absoluteUrlAllowlist`.
  - Absolute URL requests now always skip auth injection at the core helper level (not only in background-proxy fallback paths).
  - Multi-user token refresh retry logic is now bypassed for forced no-auth absolute URL requests.
- HTTP client egress hardening:
  - Egress policy evaluation now supports passing pre-resolved IPs and returning resolved IPs for callers that need consistent host checks.
  - HTTP client retry/redirect loops now maintain a per-request DNS pin cache so subsequent checks for the same host reuse the initial resolved IP set.
- Media search backend relevance/scoping behavior:
  - `/api/v1/media/search` now threads `boost_fields` into DB search execution instead of silently ignoring weights.
  - SQLite relevance sort now applies weighted BM25 scoring when `boost_fields` are supplied.
  - PostgreSQL relevance sort now applies explicit weighted `ts_rank(...)` scoring when `boost_fields` are supplied.
  - Metadata search (`/api/v1/media/metadata-search`) now applies optional standard constraints server-side before pagination (`q`, `media_types`, include/exclude keywords, date range, sort).

### Removed

- No removals in this session.

### Fixed

- Fixed OpenAI OAuth retry behavior drift from design by enforcing strict original-auth-error propagation after failed refresh+retry in chat, embeddings, and audio paths.
- Fixed OpenAI OAuth endpoint test contract drift by aligning redirect URI requirements and assertions for both SQLite and PostgreSQL endpoint suites.
- Fixed missing frontend linkage for OpenAI OAuth account controls in model settings by wiring API client methods, route guards, and action buttons.
- Fixed workspace chat pane width reclaim issues when side panes were collapsed.
- Fixed storage usage ambiguity by separating workspace payload budget, account quota usage, and browser-origin storage usage in the UI.
- Fixed Quick Chat pop-out context loss where docs-mode and Browse Guides used `/quick-chat-popout` instead of the originating page route.
- Fixed Browse Guides `Tutorials for this page` empties in sidepanel-hosted Quick Chat by enabling targeted route lookup for tutorial cards.
- Fixed workflow-card validation/documentation mismatch by accepting valid cards that omit `routeLabel`.
- Fixed an SSRF-adjacent request flow in shared request-core by enforcing default-deny absolute URL policy and explicit allowlist gating.
- Fixed DNS rebinding exposure in server-side outbound HTTP by enforcing single-resolution IP pinning per host within a request lifecycle.
- Fixed a watchlists XPath selector DoS risk by enforcing complexity limits on user-controlled selectors before compile/evaluation.
- Fixed extension build/runtime compatibility for watchlist template editing by replacing `next/dynamic` usage in `TemplateCodeEditor` with `React.lazy` + `Suspense`, unblocking `quick-chat-guides-tutorials.spec.ts` Playwright runs.
- Fixed media-search advanced controls drift where `boost_fields` UI controls had no backend relevance effect.
- Fixed metadata-mode pagination/total-authority drift by enforcing server-side standard constraints before result pagination.
- Fixed `ViewMediaPage` no-results recovery contract by wiring clear-search, clear-filters, and quick-ingest action dispatch through the page-level flow.

## [0.1.22] 2026-02-22

### Added

- Quick Chat helper documentation-assistant expansion:
  - Added a docs-focused Q&A workflow path for project-documentation guidance.
  - Added/expanded pre-written workflow Q&A cards for guided “how do I do X?” discovery.
  - Added per-page `Tutorials for this page` section in Quick Chat Browse Guides (distinct from Q&A cards) with start/replay/locked states.
  - Added strict-scope docs profile defaults for RAG Q&A (`media_db` + `project_docs`) with scope controls in Settings (`quickChatStrictDocsOnly`, `quickChatDocsIndexNamespace`, `quickChatDocsProjectMediaIds`).
- Guided tutorial rollout (P1 routes) available from Help modal + Quick Chat Browse Guides:
  - `/prompts` (`prompts-basics`)
  - `/evaluations` (`evaluations-basics`)
  - `/notes` (`notes-basics`)
  - `/flashcards` (`flashcards-basics`)
  - `/world-books` (`world-books-basics`)
  - Legacy alias routing support for `/options/*` tutorial entry paths.
- New tutorial selector/test contracts:
  - Evaluations: stable tutorial target anchors for page title, tabs, create button, list/detail cards.
  - World Books: stable tutorial target anchors for shell, search/filters, table, new/import actions.
- Workspace Playground context controls:
  - Added option to include full file contents in chat context for tasks like synopsis/summarization questions.
- Validation/test assets:
  - Added dedicated Quick Chat tutorials validation spec and expanded tutorial/registry/unit coverage.
  - Added manual QA checklist and PR/release notes for the P1 tutorials rollout.
- Published docs IA and release-notes additions:
  - Added curated User Guides taxonomy under published docs (`Server`, `WebUI_Extension`, `Integrations_Experiments`) with updated guide index routing.
  - Added published release notes page (`Docs/Published/RELEASE_NOTES.md`) and wired it into docs nav.
  - Added targeted Playwright validation coverage updates for character selection/default bootstrap and options first-run onboarding contracts.

### Changed

- Workspace Playground conversation surface behavior:
  - Page now extends downward with conversation growth up to a max threshold, then switches to scrollable conversation behavior.
- Character preview UX:
  - Character preview modal now shows full description and full tag set rather than obscured/truncated content.
- Options first-run UX test contracts:
  - Updated Playwright coverage to align with onboarding-first shell and current landing-hub “Start Chatting” flows.
- Documentation/user-guide coverage:
  - Added/updated guidance on Quick Chat docs assistant usage, tutorial discovery, and editing pre-written workflow/Q&A cards.
- Documentation cross-link normalization for published docs:
  - Repointed published guide/API/code-documentation links from non-published paths to published equivalents.
  - Replaced source-file local path links that do not publish in MkDocs with stable GitHub source links where appropriate.
- MkDocs nav completeness updates:
  - Added previously orphaned published pages to nav (`Watchlists API`, `VoiceAssistant Module`, `Doc Researcher Features`, `Generated Files Storage Code Guide`, `Sidecar Workers.template`, `Firecracker Host Checklist`).
  - Added explicit “how to add/edit tutorials” developer workflow and “how to edit pre-written workflow cards” user workflow documentation.

### Removed

- No removals in this session.

### Fixed

- Fixed free-floating notes modal open behavior in WebUI/extension where the modal would open then shrink to minimum size.
- Fixed character-page pagination instability that could jump/skip back to page 1.
- Fixed character image rendering in both character grid cards and selected character detail views.
- Fixed character list response handling by normalizing list envelopes (`items`, `characters`, `results`, `data`) to prevent missing-character selector states.
- Fixed default-character bootstrap behavior in Options Playground so server defaults preselect correctly and manual override persists across reload.
- Fixed Playwright flow instability around modern onboarding/tutorial overlays and drawer interception in character-selection scenarios.
- Playwright validation hardening completed with targeted suite passing:
  - `playground-character-selection.spec.ts` (green)
  - `options-first-run.spec.ts` (green)
  - `quick-chat-guides-tutorials.spec.ts` + `page-review.spec.ts` + `options-first-run.spec.ts` combined run (`68 passed`)
- Media ingestion batch-processor shim resolution: `process_batch_media` now detects stale endpoint wrapper caches and prefers the live core audio/video processor callable when wrappers are out of sync.
- Restored order-independent behavior for MediaIngestion_NEW regression tests that monkeypatch core processors (claims toggle integration and metadata/pre-check contract paths) by preventing fallback to real network/file audio processing during those tests.
- Dictation reliability and diagnostics across WebUI `/chat` and extension sidepanel:
  - Hardened extension dictation fallback E2E by forcing taxonomy-classified server STT failures through the extension upload transport path.
  - Added `/chat` integration coverage for dictation mode routing (`server` vs `browser`) and transcript insertion behavior.
  - Added sanitized dictation diagnostics event schema (`tldw:dictation:diagnostics`) with explicit privacy guarantees (no transcript/prompt/audio payload content).
  - Fixed STT health false-negatives for non-Whisper providers by making model-status checks provider-aware (`parakeet`, `canary`, `external`, `qwen2audio`, `qwen3-asr`, `vibevoice` vs `whisper` local-model preflight).
  - Changed STT health payload semantics to include `usable` and `on_demand`, and updated Whisper `warm=true` behavior to mark warmed models as ready.
  - Fixed dictation gating in WebUI/extension (`useTldwAudioStatus`) to fail-open for non-Whisper provider readiness probes so dictation is not disabled when server transcription remains usable.
  - Added targeted regression coverage for STT health `usable` semantics and non-Whisper dictation health fail-open behavior (backend pytest + UI Vitest).
- MkDocs strict-build blockers for published documentation:
  - Fixed missing-nav-entry blockers by including all published pages reported as out-of-nav.
  - Fixed broken published links to removed/non-published `User_Guides` and `Development` paths.
  - Fixed stale table-of-contents anchors (`#...--...`) that no longer matched generated heading IDs.
  - Strict build now reports zero missing-nav and zero broken-anchor info warnings in the docs scope.

## [0.1.21] 2026-02-21

### Added

- New security and regression tests for:
  - Scheduler payload format/ref validation and legacy compatibility behavior.
  - Web dedupe JSON persistence and controlled legacy migration.
  - Placeholder-service guardrails and route isolation.
  - Loguru formatting guardrail.
- Operations runbook documenting secure defaults, compatibility flags, and migration steps.
- Added a startup/CI route guard that fails fast when duplicate `(path, method)` routes are registered.
- Added regression tests for duplicate-route detection, CORS guardrails, ULTRA_MINIMAL health routing, and OpenAPI CORS behavior.
- Skills
  - End-to-end Skills API workflow tests covering create, list/get, versioned update with supporting-file add/remove, execute preview, context payload, export, zip re-import, delete, and seed flows.
  - Seed endpoint integration test coverage for idempotency (`overwrite=false`) and overwrite restoration (`overwrite=true`).
  - Deterministic unit tests for built-in skill seeding: recursive directory copy (including nested files), no-overwrite preservation, and overwrite replacement behavior.
- Admin Backup Bundles
  - Added API contract coverage for admin bundle import error detail shapes:
  - `restore_failed` responses must return structured `detail` objects (`error_code`, `message`, optional `rollback_failures`).
  - Standard import validation failures (for example checksum mismatches) must continue returning string `detail`.
- Web UI/Extension UX audit gating and regression coverage:
  - Added Stage 2 route-contract smoke spec for audited navigation destinations.
  - Added Stage 3 rendering-resilience smoke spec for max-depth, template-leak, and retry/timeout assertions.
  - Added Stage 4 mobile-sidebar and accessibility smoke specs, plus Axe high-risk route matrix coverage.
  - Added Stage 5 audited-route release gate smoke spec and `e2e:smoke:stage5` script.
  - Added deterministic admin smoke fixture profile/route mocks to remove skip behavior and backend-state dependency.
- UX gate process updates:
  - Added PR checklist items for UX smoke gate, console-budget checks, and WebUI/extension parity validation.
  - Added shared sanitized server-error message utility with correlation-ID log-hint support for user-facing error states.
  - Added dedicated core route identity regression tests for `/`, `/setup`, and `/onboarding-test`.
  - Added media route guard/boundary coverage for `media-multi` and `media-trash` paths.
  - Added knowledge QA golden-layout and interaction guardrails to preserve high-quality search/history UX.
  - Added workspace/playground positive-pattern guardrail tests (Data Tables, Evaluations, Chunking, Workspace desktop layout).
  - Added explicit home theme-toggle control and associated unit/E2E coverage.
- Claims extraction portability hardening (LangExtract-aligned):
  - Centralized claims output parsing and response coercion with strict/lenient modes, fenced-JSON handling, wrapper-key normalization, and structured parse errors.
  - Shared claims runtime configuration and analyze-callback typing modules reused across extraction, ingestion, adjudication, and service paths.
  - New claims telemetry counters for structured output, parsing quality, and fallback/degradation:
    - `claims_response_format_selected_total`
    - `claims_output_parse_events_total`
    - `claims_fallback_total`
  - New claims monitoring dashboard JSON with parse/fallback ratio panels and response-format selection visibility.
  - New claims regression coverage for response-format contracts, strict/lenient API behavior, fallback resilience, parse-failure telemetry, and config precedence.

### Changed

- Normalized Loguru formatting across tldw_Server_API/app from %-style placeholders to {} style.
- Added CI/test guard to prevent reintroduction of %-style Loguru placeholders.
- Sync client defaults now align with server routes (`/api/v1/sync/send` and `/api/v1/sync/get`) and support configurable auth headers (`Authorization` bearer and `X-API-KEY`).
- Moved local LLM manager initialization out of import-time setup into lifespan startup, with lazy initialization behavior where applicable.
- ULTRA_MINIMAL mode now uses control-plane health endpoints only (`/health`, `/ready`, `/health/ready`) to avoid duplicate route ownership.
- Skills
  - `SkillsService.seed_builtin_skills()` now copies full built-in skill directories recursively instead of recreating skills from `SKILL.md` only.
  - Seed overwrite flow now force-syncs registry state and handles pre-existing soft-deleted rows before copy.
- Admin Backup Bundles
  - Admin bundle create/import concurrency control now uses an atomic non-blocking lock path to fail fast with `409 bundle_operation_in_progress` instead of race-prone check-then-acquire behavior.
  - Bundle import disk-space preflight now checks all real write targets (system temp, upload temp location, and live DB target directories from manifest datasets).
  - `retention_hours` is now enforced for bundle creation: expired bundles are pruned after create within the same bundle scope (`user_id` scoped, including global `None` scope).
  - Bundle import success/dry-run payloads now consistently include `rollback_failures` for schema stability.
- Circuit Breaker
  - Unified admin circuit breaker endpoint: `GET /api/v1/admin/circuit-breakers` with RBAC protection (`admin` role + `system.logs` permission), deterministic sorting, and filters (`state`, `category`, `service`, `name_prefix`).
  - Unified admin circuit breaker response contract with explicit `source` values: `memory`, `persistent`, and `mixed`.
  - Cross-worker HALF_OPEN probe lease coordination in shared registry storage, including lease TTL, cleanup, and release-on-completion behavior.
  - Optimistic-lock conflict observability metric: `circuit_breaker_persist_conflicts_total{category,service,operation,mutation}`.
  - New endpoint test coverage for admin circuit breaker listing, filtering, and authorization behavior.
  - Circuit breaker shared-state persistence now uses bounded merge/retry semantics on optimistic-lock conflicts to avoid dropping local mutations under contention.
  - Circuit breaker operator documentation now includes new env knobs and tuning guidance:
    - `CIRCUIT_BREAKER_REGISTRY_MODE`
    - `CIRCUIT_BREAKER_REGISTRY_DB_PATH`
    - `CIRCUIT_BREAKER_PERSIST_MAX_RETRIES`
    - `CIRCUIT_BREAKER_HALF_OPEN_LEASE_TTL_SECONDS`
  - Monitoring/admin docs now explicitly describe `source="mixed"` as expected when persistence is enabled for active in-process breakers.
  - Circuit breaker unification PRD status updated to reflect implemented state and delivered hardening follow-on work.
- Web UI/Extension parity:
  - Shared `WebLayout` now defaults to collapsed rail on mobile (`<768px`) and opens navigation via header drawer toggle.
  - Shared media-query initialization now reads `matchMedia` on first client render to prevent desktop-rail flash on mobile.
  - Section 2 audited wrong-content routes now resolve to intended content or explicit “Coming Soon” placeholders instead of silent misrouting.
  - Changed settings information architecture to be more navigable, searchable, and less badge-saturated, with tighter route-to-page mapping.
  - Changed settings routing to restore/cover `/settings/ui`, `/settings/image-generation`, and `/settings/image-gen` behavior via proper wrappers/alias handling.
  - Changed guardian settings behavior to show explicit unsupported-endpoint guidance instead of noisy repeated backend failures.
  - Changed admin route behavior so admin sub-routes render route-specific content/placeholder contracts instead of collapsing to Server Admin.
  - Changed admin diagnostics presentation to human-readable units for memory/byte and retry-window values.
  - Changed admin error handling to sanitize implementation details and gate controls when prerequisites are missing.
  - Changed chat disconnected-state messaging to remove redundancy and provide one clear user path.
  - Changed chat agent empty-state/workspace affordances to clarify prerequisites and next steps.
  - Changed chat mobile composer/toolbars to enforce 44x44 touch targets and improve control discoverability.
  - Changed chat/persona language from jargon (`k=n`) to user-facing memory-result wording.
  - Changed `/chat/settings` behavior to canonical redirect (`/chat/settings` -> `/settings/chat`) and aligned strict release-gate expectations.
  - Changed audio route identity so `/tts`, `/stt`, and `/speech` have distinct intended surfaces.
  - Changed TTS/STT/Speech loading lifecycle to include explicit timeout, actionable error states, and retry UX.
  - Changed workspace/playground mobile copy and layout behavior, including Sources tab wording, chunking mobile order, and workflow-editor responsive drawer behavior.
  - Changed workflow editor control semantics with improved labeling/aria clarity and consistent LLM casing.
  - Changed flashcards/quiz/kanban/watchlists/documentation empty/content states for intent clarity and first-use correctness.
  - Changed media/knowledge/characters/chatbooks error states to be recoverable, actionable, and sanitized.
  - Changed core onboarding/layout behavior to improve mobile readability, hide sidebar where appropriate, and clarify ambiguous connection-status wording.
- Accessibility and UX consistency:
  - Standardized dismissible beta-badge behavior in shared settings navigation with persisted hide state (`tldw:settings:hide-beta-badges`).
  - Added explicit labels/tooltips for previously icon-only controls in Document Workspace and Workflow Editor.
- AntD/Markdown modernization:
  - Migrated deprecated AntD usage in shared UI (`Drawer.width`, `Space.direction`, `Alert.message`, `Dropdown.Button`, and notification `message`) to current APIs.
  - Aligned shared markdown dependency stack to ReactMarkdown v10 parity across WebUI and extension (`react-markdown`, `remark-gfm`, `remark-math`, `rehype-katex`).
  - Updated shared markdown wrappers for ReactMarkdown v10 API compatibility (styling moved off direct `ReactMarkdown` `className` prop).
- CI gating:
  - Frontend UX gates workflow now runs the Stage 5 audited-route smoke gate before the broad all-pages smoke job.
- Claims extraction/verification internals:
  - Refactored claims engine, ingestion claims, adjudicator, and claims service to use shared runtime config and shared LLM response coercion helpers.
  - Standardized provider `response_format` selection (`json_schema` when supported, `json_object` fallback) with graceful downgrade when unsupported.
  - Extended claims monitoring docs and operations guidance (metrics catalog, parse/fallback alerts, runbook triage and tuning guidance).
  - Tuned parse/fallback alert rules to use ratio + minimum-volume gates for mixed traffic profiles.
  - Updated code documentation and published mirrors for claims parse mode, alignment mode, adaptive throttling, and monitoring behavior.

### Removed

- UI
  - Removed `apps/tldw-frontend/pages/chat/settings.tsx` after replacing with server-side route redirect strategy.
  - Removed duplicate chat disconnected guidance surfaces that previously showed overlapping connection messages.
  - Removed user-visible unresolved template placeholder rendering across audited chat/audio/documentation surfaces.

### Fixed

- Auth/API: deprecated `PUT /api/v1/users/me` now returns `404 User not found` when the backing `users` row is missing, instead of returning a false-success profile payload.
- Test isolation: hardened MediaDB2 `torch` stubs with minimal `Tensor`/`nn.Module` attributes so cross-suite pytest runs no longer fail during SciPy/NLTK import checks.
- fix(audio-ws): make transcribe startup resilient to Nemo probe failures
- Treat Nemo availability probe import errors as non-fatal in `websocket_transcribe`
- Default to Whisper when Nemo probing cannot be resolved at runtime
- Prevent WS startup aborts that caused downstream quota/metrics/concurrency test failures
- Document the fail-safe fallback behavior in the audio streaming protocol docs
- Hardening: Prompts/Sync/Workflows/Services
  - Improved production safety and reliability across prompt collections, sync, workflow placeholders, and ephemeral processing.
  - Documented /api/v1/prompts/collections/* as production-backed, user-scoped endpoints.
  - Enforced and documented strict /api/v1/sync/send entity validation (Media, Keywords, MediaKeywords).
  - Hardened sync error handling: internal failures stay 500; /api/v1/sync/get now fails closed on invalid sync rows instead of silently skipping.
  - Confirmed workflow process_media placeholder kinds (ebook, xml, podcast) return explicit not_implemented.
  - Added and documented ephemeral store controls (EPHEMERAL_STORE_TTL_SECONDS, EPHEMERAL_STORE_MAX_ENTRIES, EPHEMERAL_STORE_MAX_BYTES).
  - Fixed XML placeholder temp-file lifecycle (always cleaned up) and preserved intended HTTP status behavior.
  - Added regression tests for XML cleanup/error paths and rate-limiter type-hint/datetime integrity.
- Fixed several backend reliability and API-behavior issues across Prompt DB lifecycle, sync processing, and service cleanup.
  - Removed import-time async worker startup in prompts DB dependencies; worker lifecycle now starts safely under app runtime.
  - Hardened /sync/send and /sync/get error handling:
    - preserved HTTP exceptions instead of wrapping them into generic 500s,
    - restored correct 400 classification for client validation errors (including disallowed sync entities),
    - prevented silent partial /sync/get responses when invalid sync rows are encountered.
  - Expanded sync conflict timestamp parsing to support ISO-8601 Z, fractional Z, +00 (line 0), and non-UTC offsets (normalized to UTC before LWW comparison).
  - Fixed XML processing temp-file leak by ensuring cleanup on both success and failure paths.
  - Removed deprecated FastAPI 422 fallback usage to eliminate import-time deprecation warnings in exception handling.
  - Added regression coverage for all fixes, with targeted suite passing (69 passed).
- Auth/API: deprecated `PUT /api/v1/users/me` no longer returns a false-success payload when the backing `users` row is missing; it now returns `404 User not found`.
- Regression coverage: added legacy `/users/me` update tests for both missing-row (`404`) and successful update (`200`) paths.
- Test stability: hardened MediaDB2 test `torch` stubs with minimal `Tensor`/`nn.Module` attributes to prevent cross-suite import failures during SciPy/NLTK initialization.
- Security
  - Hardened API key exposure paths:
    - /api/v1/config/docs-info now always returns a safe placeholder key and api_key_configured status.
    - Startup API key logging is masked by default (full key only when explicitly enabled).
  - Hardened scheduler payload handling:
    - External payload storage now uses safe JSON serialization by default.
    - Added strict payload reference validation and payload header bounds checks.
    - Disabled legacy pickle payload deserialization by default.
  - Hardened web scraping dedupe persistence:
    - Dedupe hashes now persist as JSON instead of pickle by default.
    - Legacy pickle hash loading is disabled by default.
  - Isolated placeholder processing services:
    - Placeholder document/ebook/podcast/xml services are now blocked in production-like environments even if enabled.
- Hardened deprecated `GET /api/v1/users/me` so missing-user fallback is only allowed in single-user mode; multi-user now correctly rejects missing backing users.
- Prevented ephemeral-store “unusable key” behavior by rejecting payloads that exceed configured max-bytes before insertion.
- Improved `/api/v1/sync/get` resilience: malformed sync rows are now logged and skipped while valid rows are still returned (partial success instead of full failure).
- Added regression coverage for user fallback rules, sync client route/auth behavior, sync malformed-row handling, and ephemeral-store size-limit enforcement.
- CORS now fails closed when enabled and `ALLOWED_ORIGINS` resolves to an explicit empty list (`[]`); a non-empty explicit origin list is required unless CORS is disabled.
- Startup now rejects invalid CORS configuration when `ALLOWED_ORIGINS` includes `"*"` while credentials are enabled.
- OpenAPI CORS handling no longer reflects disallowed origins.
- `ALLOWED_ORIGINS=""` (empty string) now logs a warning and falls back to local default origins for backward compatibility.
- Security hardening (Scheduler): fixed symlink-path validation bypass so base_path now rejects symlink ancestors (including symlink/child) instead of only direct symlink paths.
- Regression coverage (Scheduler): updated test_security_fixes.py to match current backend detection (pool-based Postgres detection) and async DB mocks (AsyncMock + awaited call assertions).
- Deprecation headers: replaced hardcoded fallback sunset dates with a shared UTC helper (build_deprecation_headers) used by auth, users, and legacy character-chat endpoints, with DEPRECATION_SUNSET_DAYS support and dynamic fallback computation.
- WebSearch Module: improved reliability and diagnostics across aggregation, provider dispatch, and parsing. Aggregate mode now validates LLM configuration (returns `422` when missing and reuses `final_answer_llm` for relevance analysis when provided), Google now correctly handles `google_domain`/`googlehost`, result-language parsing (`lr` with `hl` fallback), and multi-domain blacklist behavior, Kagi endpoint construction and Searx safesearch mapping were corrected, subquery generation/parsing now sanitizes and deduplicates model output, and provider `processing_error` values are surfaced in response `error`/`warnings` instead of being silently dropped. Added regression coverage across unit and integration WebSearch paths.
- Hardened chunked image handling to reject unsupported MIME types and invalid image payloads in large `data:` image paths.
- Changed chunked image processing failure behavior from fail-open to fail-closed, preventing invalid bytes from being treated as valid images.
- Fixed `run_cpu_bound_thread()` so keyword arguments are supported correctly via `functools.partial`.
- Corrected `load_prompt()` semantics for markdown prompts: missing keys now return `None` instead of falling back to the first fenced block.
- Removed `shell=True` usage in CUDA detection (`nvidia-smi` now called with direct subprocess args).
- Added backward-compatible chat dictionary endpoint re-exports for legacy imports/tests.
- Updated telemetry dummy span compatibility (`set_attributes`, broader `record_exception` signature).
- Skills
  - Fixed built-in seed behavior so supporting and nested files are preserved during seeding.
  - Fixed overwrite seeding edge cases where soft-deleted registry rows could prevent seeded skills from being visible after overwrite.
- Admin Backup Bundles
  - Fixed restore failure error reporting so rollback diagnostics are no longer collapsed to generic `import_error` behavior.
  - `restore_failed` import errors now preserve structured rollback context for API consumers.
  - Endpoint import response now properly propagates `rollback_failures` from service results.
  - Retention cleanup now safely skips unreadable/corrupt manifests without crashing bundle creation and keeps ZIP/sidecar cleanup consistent.
- Circuit Breaker
  - AuthNZ integration assertion for circuit breaker `source` is now environment-safe by accepting both `memory` and `mixed` (persistent mode).
- Resolved web-mode extension API runtime failures by guarding `chrome.storage` access and preventing `chrome is not defined`/`chrome.storage` uncaught exceptions.
- Removed unresolved `{{...}}` template leaks from shared UI labels/tooltips on audited routes.
- Hardened shared timeout/retry flows for admin stats and STT/TTS catalog discovery to prevent permanent-loading states.
- Removed temporary Stage 5 warning allowlist (`m5-react-defaultprops-warning`) after root-cause remediation.
- Revalidated audited smoke quality gates after remediation:
  - Stage 5 gate: `11 passed`
  - Full all-pages smoke: `165 expected, 0 unexpected, 0 flaky`
- UI
  - Fixed catastrophic extension-shim/runtime overlay impact on audited routes by driving closeout to `withErrorOverlay: 0` and `withChromeRuntimeErrors: 0` in final smoke artifact.
  - Fixed wrong-content navigation defects by closing route-contract expectations across audited settings/admin/connectors/profile/config destinations.
  - Fixed audited navigation 404 regressions (Section 2 list) to zero for in-scope UX routes.
  - Fixed unresolved template-variable leaks (`{{...}}`) across previously affected chat, audio, and documentation surfaces (`templateLeakRoutes: 0` at closeout).
  - Fixed max-update-depth/infinite-rerender class regressions on critical routes (`maxDepthRoutes: 0`, `maxDepthEvents: 0` in closeout artifact).
  - Fixed permanently-loading skeleton experiences on key admin/audio surfaces via timeout + error + retry state transitions.
  - Fixed mobile interaction issues across prioritized flows (touch-target sizing, toolbar discoverability, responsive parity gaps).
  - Fixed core route identity duplication so home/setup/onboarding-test have distinct purpose and route contracts.
  - Fixed release-readiness reliability with passing gate suite reruns at closeout: Stage 5 (`12 passed`), Stage 6 (`6 passed`), Stage 7 (`4 passed`).
  - Fixed program-level UX closure criteria by completing all nine UX implementation plans and finalizing the overarching oversight plan status to complete.
- Restored `Docs/Design/rich_text_chat_rendering_v1_2026_02_15.md` after an unintended deletion in a prior docs commit.

## [0.1.20] 2026-02-07

### Added

- webui/extension fixes+improvements
  - New Guardian settings page
- **FVA Pipeline (Falsification-Verification Alignment)**: New claim verification enhancement that actively searches for contradicting evidence to provide more robust verification results. Implements the FVA-RAG paper (arXiv:2512.07015).
  - New `CONTESTED` verification status for claims with significant evidence both supporting and contradicting
  - Anti-context retrieval generates counter-queries (negation, contrary, alternative) to find contradicting evidence
  - Adjudication weighs supporting vs contradicting evidence using NLI and LLM-based stance assessment
  - API endpoints: `POST /api/v1/claims/verify/fva` and `GET /api/v1/claims/verify/fva/settings`
  - Configurable via config.txt: FVA_ENABLED, FVA_CONFIDENCE_THRESHOLD, FVA_CONTESTED_THRESHOLD, etc.
  - 9 new Prometheus metrics for observability (falsification triggers, status changes, adjudication scores, timeouts)
  - Budget management to prevent runaway costs on large claim sets
- Speech Playground history now shows metadata (duration, model/voice/provider, params summary) with a detail tooltip.
- History entries now persist STT/TTS params (task, temp, response format, segmentation, speed, split, streaming, mode) so metadata reflects actual runs.
- Global TS typecheck fixed across UI (EPUB viewer/search typings, document chat/store shapes, KnowledgeQA response normalization, MCP path typing, chunking options, safe config typing, xterm ambient types, SpeechPlayground ordering/import issues).
- Implemented TTS history end-to-end:
	- Write path (non-streaming, streaming, jobs) with status, metadata, artifacts, and error handling.
	- Read path: list/detail/favorite/delete endpoints with filters, cursor pagination, total count.
	- Retention: scheduled purge by days and max rows; artifact reference cleanup.
	- Observability: read/write counters and latency histograms (no text logging).
	- Added schema + migrations for tts_history and supporting indexes.
- Added tests:
	- Unit: schema and API list/favorite/delete, q/text_exact behavior.
	- Integration: streaming failure writes history, artifact purge updates history, cursor pagination sanity.
	- Fixed test infrastructure shims for audio/tokenizer/transcription helpers.
- Server/API
  - RAG upgrades: Doc-Researcher features (granularity router, evidence accumulator, evidence chains), batch + resume endpoints, web fallback with query rewrite, retrieval metrics, FlashRank model support.
  - Character chat: per‑chat settings + prompt preview endpoint, greeting picker/inclusion toggle, generation presets, multi‑character turn‑taking, message steering controls, pinned messages pathing.
  - Watchlists: dedup/seen inspect & reset tools; scheduler controls; performance/limits docs.
  - Guardian/Self‑monitoring: new Guardian_DB and API surfaces.
  - ACP sandbox: SSH-enabled runner and bridge; new Dockerfile + entrypoint.
  - New “Skills” framework and Kanban endpoints/modules.

### Changed

- DBs modified
	- Media DB v2: per-user SQLite DB at Media_DB_v2.db (and Postgres equivalent when configured).
- MCP Unified hardening:
  - `/api/v1/mcp/auth/refresh` now requires body-based `refresh_token` payloads (query-token transport rejected).
  - Write-tool idempotency now binds each `idempotencyKey` to the initial argument fingerprint and returns `INVALID_PARAMS` on mismatched replays.
  - Module registry lookups now use concurrency-safe snapshots to prevent `dictionary changed size during iteration` under concurrent module registration churn.
  - Sandbox stream Redis fanout now requires explicit `SANDBOX_WS_REDIS_FANOUT` opt-in (no implicit enablement from global Redis settings).
- Evaluations module hardening:
  - Parallel batch mode now enforces strict fail-fast when `continue_on_error=false` by canceling remaining tasks and stopping new scheduling.
  - Evaluation runner now safely normalizes `metrics` values, including `metrics=None`, across execution and aggregate/stat calculations.
  - RAG pipeline eval runs now use per-run user context for ephemeral vector index creation/cleanup and pipeline calls.
  - OCR-PDF usage accounting now records against the correct limiter namespace (`evals:ocr_pdf`).
  - Access policy aligned: `/api/v1/evaluations/health` remains public, `/api/v1/evaluations/metrics` is authenticated (`EVALS_READ`), and dataset endpoints enforce `EVALS_READ`/`EVALS_MANAGE` consistently.
- Server/API
  - Admin endpoints modularized: tldw_Server_API/app/api/v1/endpoints/admin/* (replaces single admin.py).
  - Audio split: new audio submodule endpoints (tts, tokenizer, streaming, history).
- Web UI/Extension
  - Document Workspace: PDF/EPUB viewers overhauled (virtualized PDF single-page mode, thumbnails, TOC keyboard nav), DocumentPicker modal, richer metadata, TTS panel improvements, retry logic.
  - Knowledge QA: web-search fallback settings, local/server threads, richer history filtering; new “All options” settings section.
  - Playground/Chat UX: composer extracted into components, Notes Dock, greeting picker, pin/steering controls, MCP tool catalog/filter UX.
  - Workflow Editor: dynamic step registry + schema-driven fields, icons, dynamic options; new tests.
  - TTS Playground: multi-voice roles, background job progress UI, presets.
  - ACP Playground: Workspace terminal tab (xterm.js).
  - Extension e2e hardening; pdf.worker exposed via web_accessible_resources.
- Tooling/ops/docs
  - Lint only-changed target and script; large doc set added/updated (PRDs, guides).
  - FlashRank reranker model vendored under models/flashrank with unignore rules.
  - New env vars for ACP sandbox, TTS history, and RAG FlashRank cache/model selection.
- Web Scraping Module
  - Hardened legacy fallback contracts in web_scraping_service.py (line 46) and web_scraping_service.py (line 276).
  - Added explicit fallback metadata (engine, fallback_context) in web_scraping_service.py (line 392) and web_scraping_service.py (line 497).
  - Added predictable fallback max_pages cap for legacy URL Level/Sitemap in web_scraping_service.py (line 340).
  - Preserved request max_pages pass-through in ingest orchestration in web_scraping_service.py (line 721) and web_scraping_service.py (line 772).
  - Added fallback-focused tests in test_legacy_fallback_behavior.py (line 44).
  - Fixed auth header fixture for friendly ingest crawl-flag tests in test_friendly_ingest_crawl_flags.py (line 19) by merging default headers and adding X-API-KEY.

### Removed

### Fixed

- Workspace selector remove handler now uses the imported MouseEvent type instead of the React namespace.
- Audit read paths no longer return empty results on DB failures; `/api/v1/audit/export` and `/api/v1/audit/count` now surface server errors when reads fail.
- Audit fallback replay now quarantines malformed JSONL lines into `audit_fallback_queue.bad.jsonl` instead of silently dropping them.
- Audit export now rejects non-positive `max_rows`, `audit_operation` ignores reserved kwarg collisions safely, and shared-audit migration stats counters now track read/inserted/skipped events correctly.
- CodeQL Bugfixes
- ruff and mypy fixes

## [0.1.19] 2026-01-31

### Added

- Soft delete support for notes/character cards
- Qwen3-STT
- JSON validation utilities with detailed error positioning (line/column information)
- [WebUI] Character generation prompt templates for full and single-field generation 
- [WebUI] Flashcard undo functionality with Ctrl/Cmd+Z shortcut
- [WebUI] Media review selection and focus settings
- [WebUI] TldwApiClient methods for character export, restore, and bulk world book operations
- Comprehensive test coverage for Qwen3-ASR, Gemini tools, and character generation
- [WebUI] Documentation updates including PRD for Characters Playground UX improvements, healthcare-focused UX review prompts, and Qwen3-ASR setup guide
- README restructuring with improved formatting and version 0.1.18 release notes
- 70+ new adapters for workflows module
- [WebUI] Added Document Workspace
- [WebUI] Added Writing Playground

### Changed

- Implemented httpx/aiohttp transport adapters with centralized policy enforcement in http_client.
- Added httpx client caching and shutdown cleanup to align with aiohttp lifecycle handling.
- Formalized streaming behavior with first‑byte/idle timeouts and mid‑stream retry support.
- Expanded http_client tests for adapters, cache reuse, and streaming timeout coverage.
- [WebUI] e2e test work

### Removed

### Fixed

- Workspace selector remove handler now uses the imported MouseEvent type instead of the React namespace.

## [0.1.18] 2026-01-29

### Added

- Slides Module
- TTS:
  - Added NeuTTS, PocketTTS (ONNX), EchoTTS, Qwen3-TTS, LuxTTS, VibeVoice-ASR docs; updated streaming/format rules, default voice behavior, and setup guides.
- Moved the tldw_Browser_Assistant project and the tldw-frontent folder into the '/apps/' folder, as moving forward they will share the same base.
  - As a result, new frontend!
- New monorepo development guide, shared UI package scaffold, ambient typings, and testing guide for extension/web UI.
- Image creation API via files 

### Changed

- Workflows Module
  - New "llm" step type (distinct from "prompt")
  - MCP tool allowlist and scope validation
  - Stricter approve/reject permission checks
  - Configurable LLM retry cap
- Admin-UI Updates
- New frontend, tldw-frontend
- New Storage API guide, Voice Assistant API (REST & WebSocket), Watchlists API docs, Anthropic Messages API docs, and expanded /llm/models metadata (image backends & filters).
- Wide-ranging documentation additions and edits (OCR backends, image generation, storage, benchmarks, guides, link dumps, examples).
- Kanban: vector search integration, activity logging with filtering, rate limiting on endpoints
- Reading Collections: async import jobs workflow with job monitoring endpoints
- Workflows: LLM step type with MCP tool allowlist and scope validation

### Removed

- Legacy webui

### Fixed

## [0.1.17] 2026-01-19

### Added

- File Artifacts System: Comprehensive implementation of file artifact management with support for multiple export formats (iCalendar, Markdown tables, HTML tables, XLSX, data tables) including export lifecycle management, garbage collection, and validation
- Data Tables Module: Complete backend implementation with LLM-based table generation, async job workers, database schema (tables, columns, rows, sources), REST API endpoints, and export functionality
- Media Ingestion Cancellation: Added cancellation support across audio and video processing pipelines with subprocess monitoring and graceful error handling
- Content Import Preservation: Enhanced database layer to preserve existing metadata during reimport operations with preserve_existing_on_null parameter and improved full-text search with fallback candidates
- File Adapter Registry: Dynamic adapter management system supporting multiple file types with validation, normalization, and export capabilities
- Presentation Templates: New Reveal.js slide templates and CSS styling for presentation generation with bundle export support
- API Enhancements: New endpoints for file artifacts management, data table generation/export/management, and media ingest job listing with async job tracking
- Comprehensive Test Coverage: Integration and unit tests for file artifacts, data tables, media ingestion cancellation, and database operations
- NeuTTS Support
- TTS voice registry

### Changed

### Removed

### Fixed

## [0.1.16] - 2026-01-17 / Broken Bugs

### Added

- Jobs Postgres RLS policy setup now supports `JOBS_PG_RLS_DEBUG` for policy output and `JOBS_PG_RLS_ROLE` role overrides.
- Jobs prune scheduler for retention-based cleanup (env-gated, internal scheduler).
- `CHAT_COMMANDS_ASYNC_ONLY` flag to force async chat orchestration (`achat`) and block sync `chat(...)`.
- Chat command concurrency integration test and PERF-gated p50 latency smoke test.

### Changed

- Jobs Postgres tests now default to the shared per-test Postgres fixture by wiring `JOBS_DB_URL` and ensuring Jobs tables/counters.
- Jobs RLS policy setup uses negotiated Postgres DSNs for compatibility across server versions.
- Sync `chat(...)` now offloads to a worker when invoked from a running event loop (non-streaming).

### Removed

- Legacy `command_router.dispatch_command` path (now raises with migration hint).

### Fixed

- Jobs RLS debug output now reports distinct settings fields without clobbering values.
- Fixing of 200+ bugs

## [0.1.15] - 2026-01-10

### Added

### Changed

- Jobs adapters now ignore legacy read-backend flags; Chatbooks/Prompt Studio are core Jobs only, embeddings read fallback is disabled.
- Documentation updated to reflect core Jobs defaults and the current embeddings execution modes.

### Removed

### Fixed

- Legacy AuthNZ rate limiting now bypasses only when an RG policy is attached, and cancellations propagate correctly in rate limit fallbacks.
- ChaChaNotes shutdown now drains default-character tasks and waits for the executor to prevent SQLite close races (fixes Jobs web UI TTL test segfaults).

## [0.1.14] - 2026-01-06

### Added

- Added tldw-admin react frontend for admin Mgmt of the server. Very much WIP. 
- Extended feedback system/schema - Added a unified feedback system (explicit/implicit) across chat and search, integrates message IDs into chat history and streaming, 
- introduced API key KDF/key_id, 
- added admin effective-config endpoint/UI,

### Changed

- Centralized per-user path utilities for storage safety and consistency
- Migrated ingress rate limiting to Resource Governance (RG), removed SlowAPI decorators
- Enhanced feedback system with explicit endpoint, schemas, and idempotent merge rules
- Expanded chat streaming metadata to include system and assistant message IDs
- Integrated UI feedback across chat and search (rating, source feedback, implicit events)
- Updated documentation and configuration for feedback system and config management
- Comprehensive test coverage for feedback, chat metadata, and UI integration

### Removed

- slowapi usage

### Fixed

- Lots of Bugs

## [0.1.13] - 2025-12-29

### Added

- Next.js WebUI (apps/tldw-frontend)
- admin-ui - Full Admin UI: dashboard, users/orgs/teams, roles & permissions, API keys, jobs, usage analytics, budgets, BYOK, flags, incidents, logs, monitoring panels.
- Content Review: draft editor, sidebar, reattach-source flow, commit/review workflows.
- BYOK improvements: scoped resolution, validation, dashboard and key management.
- Option for review of media prior to ingestion.

### Changed

- Claims module expanded

### Removed

- N/A

### Fixed

- Improved frontend/backend error handling and type safety; more robust API interactions.

## [0.1.12] - 2025-12-20

### Added

- Full Kanban API (boards, lists, cards, labels, checklists, comments, import/export, bulk ops, card linking) with hybrid search (FTS vector).
- Self‑service Organizations & Teams (invites preview/redeem) and org admin flows.
- Billing & subscriptions (plans, checkout/portal, invoices, usage) and Stripe webhook handling.
- BYOK (per‑user and shared provider keys) with admin management and testing.
- TTS providers onboarding and user TTS guide.

### Changed

- Adds a full billing/subscription system (plans, limits, Stripe integration, webhooks), BYOK (per‑user and shared provider keys) with admin tooling, invitations/org/team RBAC, a Kanban module with per‑user DB FTS/vector search, many new endpoints/schemas/repos, DB migrations, audit/auth dependency changes, media visibility, and extensive docs/config updates.

### Removed

- A sense of failure.

### Fixed

- 500bugs

## [0.1.11] - 2025-11-27

### Added

- Guidance on stress testing chat server

### Changed

- RAG Documentation

### Removed

### Fixed

## [0.1.10] - 2025-11-27

### Added

- ChaChaNotes health snapshot surfaced in `/api/v1/health` to monitor init attempts/failures and cache state.
- MLX local provider scaffolding (Apple Silicon): adapters admin lifecycle endpoints, metrics parity, and config keys/tests with non-Apple skips.
- `LLM_MLX` extra in `pyproject.toml` to install `mlx-lm`/`mlx` for Apple Silicon users.
- Config-driven llama.cpp handler: `LLMInferenceManager` now constructs `LlamaCppHandler` when `[LlamaCpp]` is enabled in `config.txt` or via env, and `/llamacpp` endpoints are wired to the managed handler.
- ChaChaNotes schema v10 adds conversation metadata (state with `in-progress` default/backfill, topic labels, clusters) plus backlinks on notes (`conversation_id`, `message_id`) with covering indexes and SQLite/Postgres migrations.
- Templated hierarchical chunking for incoming documents/emails across `/api/v1/media/process_*` endpoints, including TemplateClassifier-based auto-selection of chunking templates and optional section trees.
- Streaming chunker/runtime helpers now honor shared chunking options via `prepare_chunking_options_dict`/`apply_chunking_template_if_any` for consistent behavior across document, PDF, video, audio, ebook, and email processing.
- User-facing documentation for templated chunking (`Templated_Chunking_Incoming_Documents_HowTo.md`) and the Project 2025 RAG workflow guide for policy/document ingestion.
- Chat diagnostics endpoints: `GET /api/v1/chat/queue/status` and `GET /api/v1/chat/queue/activity` exposing queue metrics and recent job activity, RBAC-gated to `system.logs` in multi-user mode.

### Changed

- Conversation title search now applies global BM25 normalization so pagination returns stable, deterministic ordering across the entire result set.
- Chunking engine improvements for streaming text and Markdown: better whitespace handling for word/semantic/token chunking and promotion of bold-only headings into hierarchical subsections under their parent section.
- ChaChaNotes dependency now ensures per-user DB directories are created, optional `message_metadata` is initialized, and default-character warmup tasks are tracked so the health snapshot accurately reflects warm starts.
- Llama.cpp integration: `LLMInferenceManager` logs model-directory creation failures instead of silently swallowing them, and `/llamacpp` endpoints resolve the manager from `app.state.llm_manager` (falling back to the module-level instance) with a clear 503 when not configured.
- Workflows and scheduler workflow routers are always mounted (without an `/api/v1` prefix) inside minimal/test apps so tests and tooling can call them consistently.

### Fixed

- ChaChaNotes warmup no longer leaves orphaned default-character tasks; background tasks are tracked and cleaned up when complete, improving shutdown and health reporting.
- Visual document ingestion from audio/video analysis now persists slide/visual artifacts via a thread executor, avoiding event-loop blocking during heavy analysis.
- MLX local provider concurrency: `MLXSessionRegistry.session_scope` snapshots the semaphore per context so dynamic concurrency updates cannot corrupt in-flight sessions.
- Media re-chunking for documents and emails remains best-effort but now logs failures at debug level instead of silently swallowing errors, making template issues easier to diagnose.
- Async chunker and template processor now handle multi-operation stages safely and preserve whitespace between overlapping chunks for all space-delimited methods.
- `/api/v1/health` now logs ChaChaNotes snapshot failures and resource-governance policy file read errors while still reporting a degraded health state instead of failing the endpoint.
- Chat queue status/activity endpoints avoid shadowing FastAPI's `status` module and enforce RBAC correctly, so authentication/authorization failures return the intended HTTP codes instead of spurious 500s.

## [0.1.9]

### Added

- ChaChaNotes health snapshot surfaced in `/api/v1/health` to monitor init attempts/failures and cache state.

### Changed

- ChaChaNotes dependency now initializes in a dedicated executor with WAL/busy-timeout tuning and background default-character creation; request path reduced to cache lookup health probe.
- Startup warms the single-user ChaChaNotes instance to avoid first-request blocking; shutdown now closes cached instances and stops the ChaChaNotes executor to prevent lingering threads.

### Removed

### Fixed

## [0.1.8] - 2025-11-22

### Added

- Auto-streaming for large audit exports exceeding configured threshold
- CSV streaming support for audit exports
- Model discovery for local LLM endpoints
- Audit event replay mechanism for failed exports
- Enhanced HTTP error handling for DNS resolution failures
- SuperSonicTTS support setup script
- STT:
  - `get_stt_config()` helper in `config.py` to centralize resolution of `[STT-Settings]` for all STT modules.
  - Documentation for `speech_to_text(...)` (segment-based) and `transcribe_audio(...)` (waveform-based) as the two canonical STT entrypoints, including guidance on error sentinel handling.

### Changed

- Audio:
  - Replace Parakeet-specific transcriber/config usage with unified UnifiedStreamingTranscriber/UnifiedStreamingConfig; add _LegacyWebSocketAdapter to adapt legacy WS to unified handler; defer imports and update tests to use unified stubs.
  - Move desktop/live audio helpers (LiveAudioStreamer, system-audio utilities) into `Audio/ARCHIVE/Desktop_Live_Audio_Samples.py` so core STT modules no longer depend on optional PyAudio/sounddevice at import time.
- Audit:
  - Add config-driven auto-stream threshold, support streaming for json/jsonl/csv, force streaming when max_rows exceeds threshold; CSV streaming generator; non-stream export caps; API-key hashing; fallback JSONL queue with background replay task; tests for streaming and replay.
- LLM:
  - Add local model discovery (short timeouts, TTL cache, candidate endpoints), get_configured_providers_async and integrate async provider loading into startup and web UI config; provider payloads include is_configured and endpoint_only.
- TTS
  - WAV output now buffered and deferred until finalize with in-memory threshold and disk spill; StreamingAudioWriter.__init__ adds max_in_memory_bytes; tests validate spill and finalize behavior.
- Web Scraping
  - Use defusedxml, broaden sitemap parse error handling, add test-mode egress bypass, add conditional process_web_scraping_task import/export, and preserve HTTPException semantics in ingestion endpoint.
- Tests
  - Extensive test updates (unified WS stub, fake HTTP client for RSS, env snapshot/restore, admin override fixtures, watchlists full-app fixture, connectors pre-mounting); CI embedding cache key changed to a static key.
  - STT unit tests for Parakeet/Qwen2Audio `return_language` branches now exercise the provider branches directly and avoid unintended Whisper fallbacks by normalizing file-path arguments.

### Removed

- Hopes, Dreams.

### Deprecated

- Efficiency.

### Fixed

- Improved WebSocket disconnect handling
- Consistent error handling in session cleanup and web ingestion
- Better network error resilience with graceful fallbacks
- Add _is_dns_resolution_error detection and mark DNS resolution errors non-retriable (DNSResolutionError signal); tests verify DNS errors are not retried while other network errors follow retry policy.
- My life.

## [0.1.6] - 2025-11-14

### Fixed

- HTTP-redirect loop
- test bugs

### Added

- Option for HTTP redirect adherence in media ingestion endpoints added in config.txt

## [0.1.5] - 2025-11-13

### Fixed

- Ollama API system_prompt
- Other stuff

### Added

- Updated WebUI
- Added PRD/initial work for cli installer/setup wizard
  - Auto-title notes
- Notes Graph CRUD
- Documentation/PRDs
- (From Gemini) New Chatbook Tools: Implemented a suite of new tools for Chatbooks, including sandboxed template variables for dynamic content in chat dictionary replacements, user-invoked slash commands (e.g., /time, /weather) for pre-LLM context enrichment, and a comprehensive dictionary validation tool (CLI and API) to lint schemas, regexes, and template syntax.

## [0.1.4] - 2025-11-9

### Fixed

- Numpy requirement in base install
- Default API now respected via config/not just ENV var.
- Too many issues to count.

### Added

- Unified requests module
- Added Resource governance module
- Moved all streaming requests to a unified pipeline (will need to revisit)
- WebUI CSP-related stuff
- Available models loaded/checked from `model_pricing.json`
- Rewrote TTS install/setup scripts (all TTS modules are likely currently broken)

## [0.1.3.0] - 2025-X

### Fixed

- Bugfixes
-

## [0.1.2.0] - 2025-X

### Fixed

- Bugfixes

## [0.1.1.0] - 2025-X

### Breaking

- Prometheus scraping for MCP metrics now requires authentication with the `system.logs` permission; `MCP_PROMETHEUS_PUBLIC` no longer enables public access, is deprecated, and will be removed. Migration: update Prometheus scrape configs to send a Bearer token (API key or JWT) that includes `system.logs` (see `Docs/Deployment/Monitoring/Metrics_Cheatsheet.md` migration note and scrape_config example).

### Features

- Version 0.1

### Fixed

- Use of gradio
