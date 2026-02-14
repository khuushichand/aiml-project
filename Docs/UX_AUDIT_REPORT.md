# tldw_server WebUI - Comprehensive UX Audit Report

**Date**: 2026-02-14
**Auditor**: Senior UX Review (automated CDP + Chromium walkthrough)
**Target**: http://localhost:3000 (Next.js 16.1.4 + Turbopack, dev mode)
**Routes tested**: 79 | **Screenshots captured**: 161 (desktop 1440x900 + mobile 375x812)
**Screenshots directory**: `ux-audit/screenshots/`

---

## 1. Executive Summary

The tldw_server WebUI is an ambitious, feature-rich application with **88 registered routes** spanning chat, media management, knowledge tools, audio processing, workflow editing, and admin functions. However, the application is currently **critically impaired in web browser mode** by a single blocking runtime error (`chrome.storage.local` is undefined) that fires on every page load, rendering an opaque Next.js error overlay that obscures the actual UI. Behind this overlay, the underlying pages reveal a well-structured dark-themed interface with a consistent sidebar + header layout, a thoughtful settings architecture, and some genuinely well-designed tool pages (Chunking Playground, Workflow Editor, Knowledge QA). The **three most impactful issues** are: (1) the `chrome.storage.local` crash blocking all pages, (2) 6+ routes returning 404, and (3) the navigation sidebar relying on icon-only buttons with no labels or tooltips on desktop.

---

## 2. Sitemap & Flow Inventory

### 2.1 Route Status Summary

| Status | Count | Percentage |
|--------|-------|------------|
| 200 OK (rendered) | 62 | 78% |
| 200 OK (with error text) | 3 | 4% |
| 404 Not Found | 6 | 8% |
| Redirected to another route | 9 | 11% |
| Timeout (navigation hung) | 1 | 1% |

### 2.2 All Routes Tested

| # | Route | Name | Status | Notes | Screenshot Ref |
|---|-------|------|--------|-------|----------------|
| 1 | `/` | Home/Dashboard | 200 | Blocked by chrome.storage error overlay | home_desktop.png |
| 2 | `/login` | Login/Setup | 200 | Shows server configuration form; functional | login_desktop.png |
| 3 | `/setup` | Setup Wizard | 200 | Blocked by error overlay | setup_desktop.png |
| 4 | `/media` | Media Library | 200 | Error overlay, 2 issues reported; sidebar partially visible | media_desktop.png |
| 5 | `/media-multi` | Multi-Item Library | 200 | Error overlay | media-multi_desktop.png |
| 6 | `/media-trash` | Deleted Media | 200 | Error overlay | media-trash_desktop.png |
| 7 | `/items` | Items Listing | 200 | Error overlay | items_desktop.png |
| 8 | `/reading` | Reading List | 200 | Error overlay | reading_desktop.png |
| 9 | `/watchlists` | Watchlists | 200 | Error overlay | watchlists_desktop.png |
| 10 | `/chat` | Chat Interface | 200 | Error overlay; header visible ("tldw Assistant"); sidebar beneath | chat_desktop.png |
| 11 | `/chat/settings` | Chat Settings | 200 | Error overlay | chat-settings_desktop.png |
| 12 | `/chat/agent` | Agent Chat | 200 | Error overlay | chat-agent_desktop.png |
| 13 | `/search` | Knowledge QA | 200 | **Well-rendered** after error dismissal; hero icon, search bar, history sidebar | search-results_desktop.png |
| 14 | `/audio` | Audio Tools | 200 | Error overlay; TTS controls partially visible beneath (Play/Stop/Download, Advanced controls, Voice cloning) | audio_desktop.png |
| 15 | `/tts` | Text-to-Speech | 200 | Error overlay | tts_desktop.png |
| 16 | `/stt` | Speech-to-Text | 200 | Error overlay | stt_desktop.png |
| 17 | `/speech` | Speech Synthesis | 200 | Error overlay | speech_desktop.png |
| 18 | `/evaluations` | Evaluations | 200 | Error overlay | evaluations_desktop.png |
| 19 | `/claims-review` | Claims Review | 200 | Error overlay | claims-review_desktop.png |
| 20 | `/knowledge` | Knowledge Base | 200 | Error overlay; sidebar + "Advanced Settings" link visible | knowledge_desktop.png |
| 21 | `/notes` | Notes | 200 | Error overlay; two-panel layout partially visible | notes_desktop.png |
| 22 | `/flashcards` | Flashcards | 200 | Error overlay | flashcards_desktop.png |
| 23 | `/quiz` | Quiz (Beta) | 200 | Error overlay | quiz_desktop.png |
| 24 | `/collections` | Collections (Beta) | 200 | Error overlay | collections_desktop.png |
| 25 | `/kanban` | Kanban Board | 200 | Error overlay | kanban_desktop.png |
| 26 | `/characters` | Characters | 200 | Error text detected in page body | characters_desktop.png |
| 27 | `/dictionaries` | Dictionaries | 200 | Error overlay | dictionaries_desktop.png |
| 28 | `/world-books` | World Books | 200 | Error overlay | world-books_desktop.png |
| 29 | `/prompts` | Prompts | 200 | Error overlay | prompts_desktop.png |
| 30 | `/chatbooks` | Chatbooks | 200 | **Content visible**: multi-section export form (Notes, Characters, Media, Embeddings, Prompts, Evaluations, World Books, Dictionaries, Generated docs) with "Unable to load items" errors per section | chatbooks_desktop.png |
| 31 | `/chunking-playground` | Chunking Playground | 200 | **Well-rendered**: text area, settings panel (Method, Max Size, Overlap, Language), tabs (Single/Compare/Templates/Capabilities), Cards/Inline toggle | chunking-playground_desktop.png |
| 32 | `/moderation-playground` | Moderation Playground | 200 | **Partially visible**: "Test Your Rules" section, "Current Policy Status" panel, Save/Reset buttons | moderation-playground_desktop.png |
| 33 | `/workspace-playground` | Research Studio (Beta) | 200 | Error overlay | workspace-playground_desktop.png |
| 34 | `/model-playground` | Model Playground (Beta) | **404** | Page does not exist | model-playground_desktop.png |
| 35 | `/document-workspace` | Document Workspace (Beta) | 200 | Error overlay | document-workspace_desktop.png |
| 36 | `/data-tables` | Data Tables (Beta) | 200 | Error overlay | data-tables_desktop.png |
| 37 | `/audiobook-studio` | Audiobook Studio (Beta) | **404** | Page does not exist | audiobook-studio_desktop.png |
| 38 | `/workflow-editor` | Workflow Editor | 200 | **Well-rendered**: Node Library sidebar (AI & LLM category with 22 nodes: LLM Prompt, Llm, Translate, Moderation, Image Gen, Summarize, Voice Intent, Flashcard Generate, Quiz Generate, Quiz Evaluate), canvas with flow nodes, Save button | workflow-editor_desktop.png |
| 39 | `/acp-playground` | ACP Playground (Beta) | **404** | Page does not exist | acp-playground_desktop.png |
| 40 | `/chatbooks-playground` | Chatbooks Playground | **404** | Page does not exist | chatbooks-playground_desktop.png |
| 41 | `/documentation` | Documentation | 200 | **Well-rendered**: search bar, two tabs (tldw browser extension / tldw_server both showing 0 docs), "No documentation found" empty state with unresolved template vars `{{extensionPath}}` and `{{serverPath}}` | documentation_desktop.png |
| 42 | `/skills` | Skills (Beta) | **404** | Page does not exist | skills_desktop.png |
| 43 | `/settings` | General Settings | 200 | **Content-rich behind overlay**: Theme selector, OCR language, Web Search toggles, System section (UI mode, font size), app frame config, import/export options | settings_desktop.png |
| 44 | `/settings/tldw` | TLDW Server Config | 200 | Error overlay; "Advanced Timeouts" section visible | settings-tldw_desktop.png |
| 45 | `/settings/model` | Model Provider Mgmt | 200 | Settings sidebar fully visible with all nav groups (Server & Auth, Knowledge Tools, Workspace, About) | settings-model_desktop.png |
| 46 | `/settings/chat` | Chat Settings | 200 | Error overlay | settings-chat_desktop.png |
| 47 | `/settings/ui` | UI Customization | **404** | Page does not exist | settings-ui_desktop.png |
| 48 | `/settings/splash` | Splash Screen | 200 | Error overlay | settings-splash_desktop.png |
| 49 | `/settings/quick-ingest` | Quick Ingest | 200 | Error overlay | settings-quick-ingest_desktop.png |
| 50 | `/settings/speech` | Speech Settings | 200 | Error overlay; settings sidebar visible | settings-speech_desktop.png |
| 51 | `/settings/image-generation` | Image Generation | **404** | Page does not exist | settings-image-gen_desktop.png |
| 52 | `/settings/share` | Sharing | 200 | Error overlay | settings-share_desktop.png |
| 53 | `/settings/processed` | Processing Logs | 200 | Error overlay | settings-processed_desktop.png |
| 54 | `/settings/health` | Health Monitor | 200 | **Content visible**: Metrics Health, Chat Metrics sections with HTTP/GRPC/Chat tabs, JSON config editors, MCP section, "Queue diagnostics unavailable" warning | settings-health_desktop.png |
| 55 | `/settings/knowledge` | Knowledge Base Setup | 200 | Error overlay | settings-knowledge_desktop.png |
| 56 | `/settings/chatbooks` | Chatbooks Config | 200 | Error overlay | settings-chatbooks_desktop.png |
| 57 | `/settings/characters` | Character Settings | 200 | Error overlay | settings-characters_desktop.png |
| 58 | `/settings/world-books` | World Book Settings | 200 | Error overlay | settings-world-books_desktop.png |
| 59 | `/settings/chat-dictionaries` | Dictionary Config | 200 | Error overlay | settings-chat-dicts_desktop.png |
| 60 | `/settings/rag` | RAG Settings | 200 | **Partially visible**: RAG context parameters, embedding controls, "Chat RAG context" toggle | settings-rag_desktop.png |
| 61 | `/settings/evaluations` | Evaluation Tools | 200 | Error overlay | settings-evaluations_desktop.png |
| 62 | `/settings/guardian` | Content Safety (Beta) | 200 | Error overlay | settings-guardian_desktop.png |
| 63 | `/settings/about` | About & License | 200 | Settings sidebar visible; same as /settings/model sidebar view | settings-about_desktop.png |
| 64 | `/profile` | Profile | **Redirect** | Redirects to `/settings` | profile_desktop.png |
| 65 | `/config` | Config | **Redirect** | Redirects to `/settings` | config_desktop.png |
| 66 | `/admin` | Admin Dashboard | 200 | **Content visible**: Roles table (Name/Description/System/Actions), "Unable to load roles - Invalid API key" error, "Create role" form, "Media ingestion budget" section | admin_desktop.png |
| 67 | `/admin/data-ops` | Data Operations | **Redirect** | Redirects to `/admin/server` | admin-data-ops_desktop.png |
| 68 | `/admin/server` | Server Admin | 200 | Error overlay | admin-server_desktop.png |
| 69 | `/admin/llamacpp` | Llama.cpp Config | 200 | Error text in body | admin-llamacpp_desktop.png |
| 70 | `/admin/mlx` | MLX Config | 200 | Error text in body | admin-mlx_desktop.png |
| 71 | `/admin/watchlists-runs` | Batch Jobs | **Redirect** | Redirects to `/admin/server` | admin-watchlists-runs_desktop.png |
| 72 | `/admin/watchlists-items` | Watchlist Items | **Redirect** | Redirects to `/admin/server` | admin-watchlists-items_desktop.png |
| 73-76 | `/connectors/*` | Connectors | **Redirect** | All 4 redirect to `/settings` | connectors_desktop.png |
| 77 | `/content-review` | Content Review | **Timeout** | Navigation hung (15s timeout) | N/A |
| 78 | `/onboarding-test` | Onboarding Test | 200 | Error overlay | onboarding-test_desktop.png |
| 79 | `/nonexistent-page-404-test` | 404 Test | 404 | Standard 404 page | 404-test_desktop.png |

---

## 3. Prioritized Issues List

| # | Page/Flow | Issue | Heuristic Violated | Severity (1-4) | Effort (S/M/L) | Recommendation |
|---|-----------|-------|--------------------|----------------|-----------------|----------------|
| 1 | **ALL PAGES** | `chrome.storage.local` Runtime TypeError crashes every page with an error overlay. `PageAssitDatabase` constructor at `packages/ui/src/db/index.ts:172` calls `chrome.storage.local` which doesn't exist in web browser context. | H9 (Error recovery), H1 (System status) | **4 - Catastrophic** | **M** | Add environment detection: `if (typeof chrome !== 'undefined' && chrome.storage)` guard, or provide a web-compatible storage adapter (IndexedDB/localStorage fallback) in `PageAssitDatabase`. |
| 2 | `/model-playground`, `/audiobook-studio`, `/acp-playground`, `/chatbooks-playground`, `/skills`, `/settings/ui`, `/settings/image-generation` | 7 routes registered in navigation/settings-nav but return 404 - pages don't exist | H4 (Consistency), H5 (Error prevention) | **3 - Major** | **S** | Remove these from the route registry and settings nav until implemented. Or add stub pages with "Coming Soon" messaging. |
| 3 | `/content-review` | Navigation timeout - page hangs indefinitely | H1 (System status), H13 (Performance) | **3 - Major** | **M** | Investigate infinite loop or blocking API call in the content-review page component. Add a loading timeout with fallback UI. |
| 4 | **ALL PAGES** | Persistent error toast "We couldn't refresh your chat history. You can retry from Settings." appears on every page with content. Non-dismissible red banner in top-left. | H8 (Aesthetic design), H9 (Error recovery) | **3 - Major** | **S** | Only show this toast on chat-related pages. Provide a dismiss button. Don't block the entire top-left corner. Make it a transient notification. |
| 5 | **Sidebar (all pages)** | Left sidebar uses icon-only navigation (15+ icons) with no labels, no tooltips, and no hover text. Icons are small (~20px) and many are visually similar (document-like icons for Notes, Chatbooks, Prompts, Documentation). Users cannot distinguish between icons. | H6 (Recognition over recall), H2 (Match real world) | **3 - Major** | **M** | Add tooltips on hover for each icon. Consider an expandable sidebar mode that shows icon + label. Group related icons with visual separators (already partially done). |
| 6 | `/documentation` | Template variables `{{extensionPath}}` and `{{serverPath}}` rendered as raw text instead of resolved values | H4 (Consistency), H9 (Error recovery) | **2 - Minor** | **S** | Resolve template variables at render time. The "Sources:" line should show actual paths or be hidden when unavailable. |
| 7 | `/chatbooks` | Every section shows "Unable to load items" with red error badges and "Invalid API key" messages for 10+ data categories | H9 (Error recovery), H1 (System status) | **3 - Major** | **S** | Consolidate error messages into a single banner ("API connection required") rather than showing 10+ identical errors. Provide a one-click "Connect to server" action. |
| 8 | `/admin` | "Unable to load roles - Invalid API key (GET /api/v1/admin/roles)" error shown, but the Roles table still renders with "No data" and an empty form to create roles | H5 (Error prevention), H9 (Error recovery) | **2 - Minor** | **S** | Disable the "Create role" form when the API is unreachable. Show a clear connection-required state instead of an empty table. |
| 9 | **Settings pages** | Settings content loads behind the error overlay. When overlay is dismissed, the settings page is a deeply nested, text-heavy panel with no visual hierarchy for the ~40 sidebar navigation items | H8 (Aesthetic design), H6 (Recognition) | **2 - Minor** | **L** | Add section headers/dividers in the settings content area. Use cards or collapsible sections to group related settings. |
| 10 | `/settings (General)` | "Follow app theme (auto)" preview shows a tiny 6-item app frame mockup that's barely readable at 1440px. Multiple color swatches for Theme are identical-looking. | H8 (Aesthetic design) | **1 - Cosmetic** | **S** | Enlarge the theme preview. Add labels to color swatches. |
| 11 | `/audio` | "Speech history" section shows raw template variable `{{count}}` in the text "Keeps the most recent {{count}} items" | H4 (Consistency) | **2 - Minor** | **S** | Resolve the `{{count}}` template variable or provide a sensible default like "50". |
| 12 | `/search` (Knowledge QA) | Keyboard shortcut hints show unresolved badge text (blue pill next to "Press" and "for new search") - likely icon/key badges not rendering in headless browser, but should verify in real browser | H10 (Help/documentation) | **1 - Cosmetic** | **S** | Ensure keyboard shortcut badges render as text fallbacks when icon fonts aren't loaded. |
| 13 | **Header bar** | Header shows "tldw Assistant" branding with hamburger, bot icon, and arrow - but navigation links visible in the Header.tsx code are hidden. Only Search, compose, settings, and ? icons visible. | H7 (Flexibility), H6 (Recognition) | **2 - Minor** | **M** | Ensure header navigation links (Media, Items, Chat, Search, etc.) are visible on desktop. Currently they're hidden even at 1440px width. |
| 14 | **Mobile (all pages)** | Error overlay consumes entire viewport on mobile (375px). No way to dismiss it. Content beneath is completely inaccessible. | H3 (User control), H12 (Responsive) | **4 - Catastrophic** | **M** | Same fix as #1. Additionally, in dev mode, the Next.js error overlay should be dismissible on mobile. |
| 15 | **Multiple settings routes** | `/profile`, `/config`, `/connectors/*`, `/admin/data-ops`, `/admin/watchlists-runs`, `/admin/watchlists-items` all redirect to generic settings or admin pages. Users following direct links would be disoriented. | H1 (System status), H4 (Consistency) | **2 - Minor** | **M** | Either implement these routes properly, or show a redirect notice ("This feature has moved to Settings"). Remove dead routes from any navigation that links to them. |
| 16 | `/settings/health` | "Queue diagnostics unavailable - Invalid API key" shown alongside detailed JSON config blocks. Raw JSON is displayed without formatting controls. | H2 (Match real world), H8 (Aesthetic) | **2 - Minor** | **S** | Hide JSON blocks behind a "Show raw config" toggle. Display diagnostics in a user-friendly dashboard format. |
| 17 | **Workflow Editor** | The node canvas has orange START and END nodes but no clear instructions for first-time users on how to build a workflow. The "Drag, click, or press Enter to add nodes" hint is at the very bottom of the sidebar. | H10 (Help/documentation) | **2 - Minor** | **M** | Add an empty-state illustration or guided tutorial overlay when the canvas is empty. Move the hint text to a more prominent position. |

---

## 4. Heuristic Scorecard

| # | Heuristic | Score (1-5) | Justification |
|---|-----------|-------------|---------------|
| 1 | Visibility of system status | **2** | Error overlay provides no useful system state. When visible, toast errors don't clearly indicate what's wrong or how to fix it. Loading states not observable due to overlay. |
| 2 | Match between system and real world | **3** | Good use of familiar terminology (Notes, Chat, Media, Search). Template variables leaking (`{{count}}`, `{{path}}`) hurt this. |
| 3 | User control and freedom | **2** | Error overlay cannot be dismissed on many pages. No visible undo/back patterns. Settings navigation is one-way. |
| 4 | Consistency and standards | **3** | Consistent dark theme, sidebar layout, and header across all pages. Inconsistent: some pages render despite errors, others don't. 404s for navigable items. |
| 5 | Error prevention | **2** | Forms are accessible while API is disconnected (admin role creation). No validation before actions. 7 dead routes reachable from navigation. |
| 6 | Recognition rather than recall | **2** | Sidebar icons have no labels or tooltips. 15+ identical-looking document icons. Users must memorize what each icon means. |
| 7 | Flexibility and efficiency of use | **3** | Command palette (Cmd+K) is good. Keyboard shortcuts exist. Settings has 40 navigation items. Sidebar icons support power users but alienate newcomers. |
| 8 | Aesthetic and minimalist design | **3** | Dark theme is polished and professional when visible. Good spacing in Chunking Playground and Search pages. Settings pages are information-dense but well-organized with clear groupings (Server & Auth, Knowledge Tools, Workspace, About). |
| 9 | Help users recover from errors | **1** | The single most critical failure. Error overlay provides a developer stack trace, not user-friendly guidance. "Unable to load" errors repeat 10+ times on Chatbooks. No recovery actions offered. |
| 10 | Help and documentation | **3** | Documentation page exists but is empty. Keyboard shortcut modal exists (?). Setup page explains server configuration clearly. Help icon (?) in header is good. |
| 11 | Accessibility | **2** | Dark theme has reasonable contrast ratios. Icon-only navigation fails accessibility (no aria-labels visible). Focus indicators not tested due to overlay. WCAG issues with color-only differentiation in theme selector. |
| 12 | Responsive design | **2** | Header collapses appropriately on mobile. But error overlay destroys mobile usability entirely. Sidebar adapts to icon-only mode. Search page content gets cropped by overlay on mobile. |
| 13 | Performance perception | **3** | Pages load quickly (under 3s in puppeteer). "Balanced" preset shown in search. Lazy loading for code-split routes. But the error overlay makes performance irrelevant since users see a crash. |

**Overall Score: 2.4 / 5** (would likely be 3.5+ once the chrome.storage.local issue is resolved)

---

## 5. Detailed Findings by Page/Flow

### 5.1 Home (`/`)
- **Screenshot**: `home_desktop.png`, `home_mobile.png`
- **Strengths**: None observable - entirely blocked by error overlay
- **Issues**:
  - [H9/Sev-4] Runtime TypeError overlay covers entire page
  - No home/dashboard content visible at all
  - Mobile: overlay fills screen with no dismiss option
- **Recommendation**: After fixing #1, design a proper dashboard landing page showing recent activity, quick actions (New Chat, Ingest Media, Search), and system status.

### 5.2 Login/Setup (`/login`)
- **Screenshot**: `login_desktop.png`
- **Strengths**:
  - Clean, centered layout with clear information hierarchy
  - "About tldw server integration" explainer card is helpful
  - Bullet points explain what the server enables (chat, knowledge search, media)
  - Toggle between "Single User (API Key)" and "Multi User (Login)" is clear
  - Good helper text below API Key field explaining the default key
  - "View server setup guide" link for additional help
  - Action buttons (Save, Test Connection, Grant Site Access) are well-differentiated
  - Health check badges ("Core: waiting", "RAG: waiting") provide status
- **Issues**:
  - [H4/Sev-1] "Grant Site Access" button purpose is unclear (extension-specific concept in web context)
  - [H2/Sev-1] "extension" language ("turns this extension into a workspace") is misleading in web context
- **Recommendation**: Conditionally hide extension-specific UI elements when running as a web app. Change "extension" to "app" in web context.

### 5.3 Search / Knowledge QA (`/search`)
- **Screenshot**: `search-with-query_desktop.png`, `search-results_desktop.png`, `search_mobile.png`
- **Strengths**:
  - Excellent empty state with hero icon and clear description ("Ask questions about your documents and get AI-powered answers with citations from your knowledge base")
  - Clean search input with "Ask" button
  - History sidebar with "Preset: Balanced" dropdown
  - "Web search off" toggle provides transparency
  - "No search history yet - Your searches will appear here" is a good empty state message
- **Issues**:
  - [H9/Sev-3] Error overlay blocks initial load; only visible after error is dismissed
  - [H1/Sev-1] Keyboard shortcut badges not fully rendering
  - [H12/Sev-3] Mobile: error overlay covers the search interface, and when partially visible, the "Knowledge QA" text and search bar get clipped
- **Recommendation**: This is one of the best-designed pages. After fixing the chrome.storage issue, this page will work well. Consider adding search suggestions or sample queries for first-time users.

### 5.4 Chat (`/chat`)
- **Screenshot**: `chat_desktop.png`, `chat_mobile.png`, `chat-with-input_desktop.png`
- **Strengths**:
  - Header shows "tldw Assistant" branding
  - Compact toolbar icons (Search, Cmd+K, compose, settings, help)
  - Chat input textarea was found and functional (Puppeteer could type into it)
- **Issues**:
  - [H9/Sev-4] Error overlay covers chat interface entirely
  - [H1/Sev-3] No model selection visible in the chat header (behind overlay)
  - [H12/Sev-3] Mobile: completely unusable
- **Recommendation**: After fixing the storage issue, validate the chat flow end-to-end. The interaction test confirmed the input is present and typeable.

### 5.5 Settings (`/settings` and sub-routes)
- **Screenshot**: `settings_desktop.png`, `settings-first-nav_desktop.png`, `settings-model_desktop.png`
- **Strengths**:
  - Well-organized 4-group navigation sidebar: Server & Auth, Knowledge Tools, Workspace, About
  - Each item has an icon + label in the sidebar (unlike the main sidebar)
  - "Beta" badges clearly mark experimental features
  - 40 settings navigation items are well-categorized
  - Content area is clean with appropriate form controls (toggles, dropdowns, inputs)
  - General Settings page has useful organization: Language, OCR, Web Search, System, Theme
  - "Change Theme" with System/Light/Dark toggle and color palette is well-implemented
  - Collapsible "Advanced Timeouts" section keeps the interface uncluttered
- **Issues**:
  - [H9/Sev-4] Error overlay blocks everything on first load
  - [H4/Sev-3] 7 sidebar items link to 404 pages
  - [H8/Sev-2] When sidebar is visible, content area is narrow on 1440px; the sidebar takes ~280px
  - [H6/Sev-1] Some settings labels are abbreviations ("RAG", "MCP", "MLX") without explanation for non-technical users
  - [H2/Sev-1] "Follow app theme (auto)" preview is tiny and barely readable
- **Recommendation**: Remove 404 items from sidebar. Add tooltips for technical abbreviations. Increase the theme preview size.

### 5.6 Audio (`/audio`)
- **Screenshot**: `audio_desktop.png`
- **Strengths**:
  - TTS controls visible: Play, Stop, Download buttons
  - "Advanced controls" and "Voice cloning & custom voices" collapsible sections
  - "Speech history" section with search and filters (All items, All dropdown)
  - Word/char/segment counts visible ("0 words | 0 chars | 0 segments Est. duration: 0s")
- **Issues**:
  - [H4/Sev-2] `{{count}}` template variable not resolved in "Keeps the most recent {{count}} items"
  - [H9/Sev-4] Error overlay blocks the entire page
- **Recommendation**: Fix template variable resolution. This page has solid UX patterns.

### 5.7 Admin (`/admin`)
- **Screenshot**: `admin_desktop.png`
- **Strengths**:
  - Clean table layout for Roles (Name, Description, System, Actions columns)
  - "Create role" inline form with placeholder text ("Role name (e.g. anal...)", "Optional description")
  - "Media ingestion budget" section with User/media.default dropdowns
  - Error banner clearly states "Invalid API key (GET /api/v1/admin/roles)"
- **Issues**:
  - [H5/Sev-2] "Create role" form is active despite API being unreachable - user could try to create a role and get a confusing error
  - [H8/Sev-1] "No data" empty state uses a generic file icon; could use a more contextual illustration
  - [H5/Sev-2] Placeholder text "e.g. anal..." is a truncation of "analyst" but reads poorly
- **Recommendation**: Disable form when API is unreachable. Expand placeholder to "e.g. analyst" to avoid unfortunate truncation. Show a clear "Connect to server first" message.

### 5.8 Workflow Editor (`/workflow-editor`)
- **Screenshot**: `workflow-editor_desktop.png`
- **Strengths**:
  - Professional node-based editor with drag-and-drop canvas
  - Node Library sidebar with categorized nodes (AI & LLM: 22 nodes)
  - Clear node names with icons (LLM Prompt, Translate, Moderation, Image Gen, Summarize, Voice Intent, etc.)
  - Search bar in Node Library
  - Save button in top-right toolbar
  - Three tab icons at the top of the sidebar (likely Nodes, Settings, Run)
- **Issues**:
  - [H10/Sev-2] No onboarding or empty-state guidance for first-time users
  - [H1/Sev-1] "Drag, click, or press Enter to add nodes" hint is at very bottom, below scroll
  - [H4/Sev-1] Orange START/END nodes on canvas lack labels or explanation
  - [H8/Sev-1] Canvas background is plain dark; could benefit from a subtle grid pattern for alignment
- **Recommendation**: Add an empty-state overlay: "Create your first workflow: drag nodes from the library onto the canvas." Add grid to canvas. Add zoom controls.

### 5.9 Chunking Playground (`/chunking-playground`)
- **Screenshot**: `chunking-playground_desktop.png`
- **Strengths**:
  - Excellent page layout: clear title + description, tabs, two-column design
  - Tabs: Single | Compare | Templates | Capabilities
  - Input methods: Paste Text, Upload File, Upload PDF, Sample Text, From Media Library
  - Settings panel: Method (Words dropdown), Max Size (400), Overlap (200), Language (English)
  - Advanced Options collapsible
  - "Reset to defaults" and "Save as Template" actions
  - "Chunk Text" button with scissors icon
  - Results toggle: Cards | Inline
  - Empty state: "Enter text and click 'Chunk Text' to see results" with icon
- **Issues**:
  - [H8/Sev-1] Settings panel could use a border or background to separate it visually from the input area
- **Recommendation**: This is the best-designed page in the application. Use it as a reference for other tool pages.

### 5.10 Documentation (`/documentation`)
- **Screenshot**: `documentation_desktop.png`
- **Strengths**:
  - Clean layout with search bar and tabs
  - Good empty state: "No documentation found" with icon and instruction to add markdown files
- **Issues**:
  - [H4/Sev-2] Raw template variables: "Sources: {{extensionPath}} and {{serverPath}}"
  - [H1/Sev-1] Both tabs show "(0)" - no documentation available
- **Recommendation**: Resolve template variables. Pre-populate with built-in documentation.

### 5.11 Chatbooks (`/chatbooks`)
- **Screenshot**: `chatbooks_desktop.png`
- **Strengths**:
  - Comprehensive export page covering 10+ content categories
  - Each section has consistent layout: checkbox, table header, filters, refresh
  - "Export Selected" button at bottom
- **Issues**:
  - [H9/Sev-3] Every single section shows red error "Unable to load items - Invalid API key" - visually overwhelming
  - [H8/Sev-2] 10+ identical error messages create a wall of red
- **Recommendation**: Show a single banner at the top: "Server connection required. Configure your API key in Settings." Disable/collapse individual sections until connected.

### 5.12 Health Monitor (`/settings/health`)
- **Screenshot**: `settings-health_desktop.png`
- **Strengths**:
  - Detailed system health information
  - Tabbed interface (HTTP/GRPC/Chat) for different metric types
  - JSON config editors for endpoints
  - MCP section for Model Context Protocol monitoring
- **Issues**:
  - [H2/Sev-2] Raw JSON displayed as primary content - not user-friendly
  - [H8/Sev-2] Dense information layout without visual hierarchy
  - [H9/Sev-2] "Queue diagnostics unavailable" error at bottom
- **Recommendation**: Replace raw JSON with a dashboard view (status cards, charts). Keep JSON behind a "Developer view" toggle.

---

## 6. Cross-Cutting Themes

### 6.1 Chrome Extension vs Web App Identity Crisis
The most pervasive issue is that the shared UI package (`packages/ui/`) was built primarily for a Chrome extension and uses `chrome.storage.local` for data persistence. In the web browser context, this API doesn't exist, causing a crash on every page. The error manifests through `PageAssitDatabase` at `db/index.ts:172` and cascades through the `useMigration` hook that runs on every page load.

### 6.2 Error Cascade Pattern
When the API is not connected (invalid API key), errors cascade across the application:
- Chat history toast on every page
- 10+ "Unable to load items" errors on Chatbooks
- "Unable to load roles" on Admin
- "Queue diagnostics unavailable" on Health
**Pattern**: Each component independently fetches and independently fails, rather than using a centralized connectivity state.

### 6.3 Icon-Only Navigation
The main sidebar uses 15+ icon-only buttons with no labels, tooltips, or aria-labels. Many icons are visually similar (document/page icons for Notes, Chatbooks, Prompts, Documentation, Characters). This forces users to memorize positions rather than recognize labels.

### 6.4 Template Variable Leakage
Multiple pages show unresolved template variables (`{{count}}`, `{{extensionPath}}`, `{{serverPath}}`). This suggests the template resolution system doesn't handle fallback values.

### 6.5 404 Routes in Navigation
7 routes are listed in the settings navigation sidebar but return 404 errors. These are mostly Beta features that were removed or never implemented but whose navigation entries remain.

### 6.6 Consistent Dark Theme (Positive)
The dark theme is well-executed with appropriate contrast, consistent color usage (blue for primary actions, red for destructive/error, gray for secondary), and professional typography. The color palette across all pages is harmonious.

### 6.7 Well-Designed Tool Pages (Positive)
Pages like Chunking Playground, Workflow Editor, and Knowledge QA show mature UX thinking: clear information hierarchy, good empty states, appropriate use of tabs and panels, actionable empty state messages.

---

## 7. Accessibility Audit Summary

### Perceivable
- **Color contrast**: Dark theme generally meets AA contrast ratios for text (light gray on dark navy). Error overlay uses red text on dark background which may not meet WCAG AA for small text.
- **Non-text content**: Sidebar icons lack alt text or aria-labels. No visible text alternatives for icon-only navigation.
- **Template variables**: Raw `{{variable}}` text is confusing for screen readers.

### Operable
- **Keyboard navigation**: Command palette (Cmd+K) provides keyboard-driven navigation. Keyboard shortcut modal (?) exists. However, sidebar icon-only buttons lack keyboard focus indicators (not testable behind error overlay).
- **Focus management**: Error overlay traps focus (good for modal pattern). But it prevents access to the underlying page.
- **Touch targets**: Sidebar icons appear to be ~20px which is below the 44px minimum recommended by WCAG 2.5.5.

### Understandable
- **Labels**: Settings sidebar has good labels. Main sidebar has no labels.
- **Error identification**: Error messages don't provide clear recovery instructions. "Invalid API key" errors don't link to where the key should be configured.
- **Language**: Mix of technical jargon (RAG, MCP, FTS5) and user-friendly language. No glossary or hover definitions.

### Robust
- **HTML semantics**: Not directly auditable through screenshots. The settings nav appears to use proper link semantics (`<a>` tags found by Puppeteer).
- **ARIA**: Sidebar needs `aria-label` attributes on icon-only buttons.

---

## 8. Top 10 Quick Wins

| # | What to Fix | Before | After | Impact | Effort |
|---|------------|--------|-------|--------|--------|
| 1 | **Guard `chrome.storage.local` access** | `this.db = chrome.storage.local` crashes in web browser | Add `if (typeof chrome?.storage?.local !== 'undefined')` guard with localStorage/IndexedDB fallback | Unblocks the entire web application | S-M |
| 2 | **Remove 404 routes from navigation** | 7 sidebar items link to non-existent pages | Remove or hide entries where `page file does not exist` | Eliminates user confusion and dead ends | S |
| 3 | **Resolve template variables** | `{{count}}`, `{{extensionPath}}`, `{{serverPath}}` shown as raw text | Provide fallback values: `count` -> "50", paths -> actual paths or "not configured" | Removes unprofessional raw variables | S |
| 4 | **Add sidebar tooltips** | Icon-only sidebar with no labels | Add `title` and `aria-label` to every sidebar icon button | Massive usability and accessibility improvement | S |
| 5 | **Consolidate API error messages** | 10+ identical "Unable to load" errors on Chatbooks, per-page toast | Single top banner: "Server connection required" with link to Settings | Reduces error noise by 90% | S |
| 6 | **Fix admin placeholder text** | "Role name (e.g. anal...)" | "Role name (e.g. analyst)" | Eliminates embarrassing truncation | S |
| 7 | **Disable forms when API unreachable** | "Create role" form active with no API | Disable form controls, show "Connect to server first" | Prevents user frustration | S |
| 8 | **Make chat history toast transient** | Persistent red toast on every page | Auto-dismiss after 5 seconds, only show on chat-related pages | Reduces visual noise across all pages | S |
| 9 | **Add "extension" vs "web" context detection** | Login page says "turns this extension into a workspace" | Detect context and use "app" instead of "extension" for web | Reduces confusion for web users | S |
| 10 | **Add empty-state to Workflow Editor** | Blank canvas with unlabeled START/END nodes | Overlay: "Drag a node from the library to get started" with arrow pointing to sidebar | Better first-time experience | S |

---

## 9. Strategic Recommendations

### 9.1 Implement a Web-Specific Storage Adapter (Priority: Critical)
Create an abstraction layer in `packages/ui/src/db/` that detects the runtime environment (Chrome extension vs. web browser) and selects the appropriate storage backend. For web: use IndexedDB (via Dexie, which is already in the codebase per the stack trace) or localStorage. This single change will unlock the entire web application.

### 9.2 Create a Centralized Connectivity State Manager (Priority: High)
Implement a React context that tracks server connectivity (API key validity, server reachability). Components should subscribe to this context rather than independently fetching and failing. When disconnected, show a single persistent banner with a "Configure" action button, and gracefully degrade all data-dependent components to their empty states rather than error states.

### 9.3 Design System Formalization (Priority: Medium)
The application already has consistent visual patterns. Formalize these into a documented design system:
- **Colors**: The existing dark theme palette (navy backgrounds, blue primary, red destructive)
- **Typography**: Current font stack and size scale
- **Components**: Standardize the "tool page" pattern visible in Chunking Playground (title + description + tabs + two-column layout) as a reusable template
- **Empty states**: Standardize the icon + heading + description + action pattern
- **Error states**: Create a single, reusable error/disconnected component

### 9.4 Progressive Disclosure for Settings (Priority: Medium)
With 40+ settings navigation items, the settings area is overwhelming. Implement:
- A "Quick Setup" wizard that guides new users through the essential 5-6 settings
- Collapse Beta features behind a "Show experimental features" toggle
- Add search/filter to the settings sidebar
- Show "Recommended" badges on settings most users need

### 9.5 Onboarding Flow (Priority: Medium)
The application is feature-rich but offers no guidance. Create a first-run experience that:
1. Detects first visit (no API key configured)
2. Walks through server connection
3. Shows a feature tour of the top 5 capabilities (Chat, Search, Media, Audio, Settings)
4. Provides sample data or a "Try it" experience
The `/onboarding-test` route suggests this is already planned.

---

## Appendix A: Interaction Test Results

| Test | Result | Notes |
|------|--------|-------|
| Chat input (type text) | PASS | Textarea found and text entered successfully |
| Search input (type + submit) | PASS | Query entered, Enter pressed, page responded |
| Settings navigation (click links) | PASS | 40 nav links found and first one clicked |
| Theme toggle (dark/light) | FAIL | No theme toggle button found with standard selectors |
| Media empty form submit | FAIL | No submit button found with standard selector |

## Appendix B: Redirect Map

| Source Route | Destination | Likely Reason |
|-------------|-------------|---------------|
| `/profile` | `/settings` | Profile merged into settings |
| `/config` | `/settings` | Config merged into settings |
| `/admin/data-ops` | `/admin/server` | Feature consolidated |
| `/admin/watchlists-runs` | `/admin/server` | Feature consolidated |
| `/admin/watchlists-items` | `/admin/server` | Feature consolidated |
| `/connectors` | `/settings` | Not yet implemented |
| `/connectors/sources` | `/settings` | Not yet implemented |
| `/connectors/jobs` | `/settings` | Not yet implemented |
| `/connectors/browse` | `/settings` | Not yet implemented |

## Appendix C: Error Issue Count Accumulation

As the automation navigated pages sequentially, the Next.js error badge accumulated:
- Page 1-3: "1 Issue"
- Page 4 (media): "2 Issues"
- Page 13+ (after search): "3 Issues"
This suggests errors are not isolated per-page but accumulate in the Next.js dev error tracker.
