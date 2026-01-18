# Extension Frontend Migration Map (Stage 1)

## Source references
- `src/routes/route-registry.tsx`
- `src/routes/*`
- `src/entries/background.ts`
- `src/entries/shared/background-init.ts`
- `src/entries/hf-pull.content.ts`
- `tailwind.config.js`
- `package.json`
- `pages/*` in `tldw-frontend`

## Extension route inventory (options)
Main entry
- `/` -> `src/routes/option-index.tsx` (Playground + onboarding)

Settings
- `/settings` -> `components/Option/Settings/general-settings`
- `/settings/tldw` -> `components/Option/Settings/tldw`
- `/settings/model` -> `components/Option/Models`
- `/settings/chat` -> `components/Option/Settings/ChatSettings`
- `/settings/quick-ingest` -> `components/Option/Settings/QuickIngestSettings`
- `/settings/speech` -> `components/Option/Settings/SpeechSettings`
- `/settings/rag` -> `components/Option/Settings/rag`
- `/settings/evaluations` -> `components/Option/Settings/evaluations`
- `/settings/prompt-studio` -> `components/Option/Settings/prompt-studio`
- `/settings/knowledge` -> `components/Option/Knowledge`
- `/settings/chatbooks` -> `components/Option/Settings/chatbooks`
- `/settings/characters` -> `components/Option/Settings/WorkspaceLinks`
- `/settings/world-books` -> `components/Option/Settings/WorkspaceLinks`
- `/settings/chat-dictionaries` -> `components/Option/Settings/WorkspaceLinks`
- `/settings/share` -> `components/Option/Share`
- `/settings/health` -> `src/routes/option-settings-health.tsx`
- `/settings/processed` -> `src/routes/option-settings-processed.tsx`
- `/settings/about` -> `components/Option/Settings/about`

Workspace + knowledge
- `/media` -> `src/routes/option-media.tsx`
- `/media-trash` -> `src/routes/option-media-trash.tsx`
- `/media-multi` -> `src/routes/option-media-multi.tsx`
- `/review` -> `src/routes/option-media-multi.tsx`
- `/content-review` -> `src/routes/option-content-review.tsx`
- `/notes` -> `src/routes/option-notes.tsx`
- `/knowledge` -> `src/routes/option-knowledge.tsx`
- `/world-books` -> `src/routes/option-world-books.tsx`
- `/dictionaries` -> `src/routes/option-dictionaries.tsx`
- `/characters` -> `src/routes/option-characters.tsx`
- `/prompts` -> `src/routes/option-prompts.tsx`
- `/prompt-studio` -> `src/routes/option-prompt-studio.tsx`
- `/evaluations` -> `src/routes/option-evaluations.tsx`
- `/flashcards` -> `src/routes/option-flashcards.tsx`
- `/quiz` -> `src/routes/option-quiz.tsx`
- `/watchlists` -> `src/routes/option-watchlists.tsx`
- `/collections` -> `src/routes/option-collections.tsx`

Audio
- `/tts` -> `src/routes/option-tts.tsx`
- `/stt` -> `src/routes/option-stt.tsx`
- `/speech` -> `src/routes/option-speech.tsx`

Tools + playgrounds
- `/chunking-playground` -> `src/routes/option-chunking-playground.tsx`
- `/chatbooks` -> `src/routes/option-chatbooks-playground.tsx`
- `/kanban` -> `src/routes/option-kanban-playground.tsx`
- `/data-tables` -> `src/routes/option-data-tables.tsx`
- `/documentation` -> `src/routes/option-documentation.tsx`
- `/quick-chat-popout` -> `src/routes/option-quick-chat-popout.tsx`

Admin
- `/admin/server` -> `src/routes/option-admin-server.tsx`
- `/admin/llamacpp` -> `src/routes/option-admin-llamacpp.tsx`
- `/admin/mlx` -> `src/routes/option-admin-mlx.tsx`

Other
- `/onboarding-test` -> Onboarding wizard standalone (test route)

## Extension route inventory (sidepanel)
Sidepanel chat
- `/` -> `src/routes/sidepanel-chat.tsx`
- `/agent` -> `src/routes/sidepanel-agent.tsx`
- `/settings` -> `src/routes/sidepanel-settings.tsx`
- `/error-boundary-test` -> `src/routes/sidepanel-error-boundary-test.tsx`

## Proposed Next.js route translation (no embedded React Router)
Keep option routes as-is. Move sidepanel routes under `/chat` to avoid collisions with option `/settings`.
- `/` -> `OptionIndex` (Playground)
- `/settings/*` -> same paths as extension
- `/media`, `/media-trash`, `/media-multi`, `/review`, `/content-review` -> same paths
- `/notes`, `/knowledge`, `/world-books`, `/dictionaries`, `/characters`, `/prompts`, `/prompt-studio`, `/evaluations`, `/flashcards`, `/quiz`, `/watchlists`, `/collections` -> same paths
- `/tts`, `/stt`, `/speech` -> same paths
- `/chunking-playground`, `/chatbooks`, `/kanban`, `/data-tables`, `/documentation`, `/quick-chat-popout` -> same paths
- `/admin/server`, `/admin/llamacpp`, `/admin/mlx` -> same paths
- `/chat` -> `SidepanelChat`
- `/chat/agent` -> `SidepanelAgent`
- `/chat/settings` -> `SidepanelSettings` (or merge into `/settings/chat`)
- `/__debug__/sidepanel-error-boundary` -> `SidepanelErrorBoundaryTest` (optional; internal only)

## Existing Next pages to replace/redirect
Direct replacements
- `pages/index.tsx` -> `/` (OptionIndex)
- `pages/chat.tsx` -> `/chat` (SidepanelChat)
- `pages/media.tsx` -> `/media`
- `pages/content-review.tsx` -> `/content-review`
- `pages/evaluations.tsx` -> `/evaluations`
- `pages/watchlists.tsx` -> `/watchlists`
- `pages/audio.tsx` -> `/speech` or split into `/tts` + `/stt`
- `pages/config.tsx` -> `/settings`
- `pages/search.tsx` -> map to `/knowledge` or add a dedicated `/search` route from extension if needed
- `pages/claims-review.tsx` -> map to `/content-review` (or drop if redundant)

Needs explicit decision
- `pages/reading.tsx` -> maps best to `/collections` (reading list now in Collections)
- `pages/items.tsx` -> likely `/media` or `/collections` (confirm usage)
- `pages/profile.tsx` -> no direct extension route (decide keep/retire)
- `pages/privileges.tsx` -> no direct extension route (decide keep/retire)
- `pages/media/[id]/view.tsx` -> no direct extension route (decide if keep for deep links)
- `pages/admin/*` -> replace with `/admin/*` extension routes
- `pages/connectors/*` -> no direct extension route (decide keep/retire)
- `pages/login.tsx` -> depends on auth flow; extension uses local config storage + onboarding

## Extension-only platform features to replace
Background/service worker
- `src/entries/background.ts`, `src/entries/shared/background-init.ts`
- Replaces: context menus, commands, action badge, alarms, runtime messaging, openapi drift check.
- Web replacement: in-app command palette/actions, scheduled server-side jobs or client timers, direct API calls.

Content scripts + page capture
- `src/entries/hf-pull.content.ts`, `src/libs/get-tab-contents.ts`, `src/libs/get-html.ts`, `src/libs/get-screenshot.ts`
- Replaces: in-page injection, tab capture, active tab scraping.
- Web replacement: ingest-by-URL in UI, file uploads, optional bookmarklet or desktop agent integration.

Extension APIs
- `browser.runtime.*` / `chrome.runtime.*` message passing
- `browser.tabs.*` / `chrome.tabs.*` open tab / capture
- `browser.notifications` / `chrome.notifications`
- `browser.contextMenus`, `browser.alarms`, `browser.commands`
- `chrome.tts` (speech)
- `browser.i18n` (extension strings)
- `browser.storage.*` and `@plasmohq/storage` (settings persistence)
- `browser.runtime.sendNativeMessage` (tldw-agent native messaging)

Web replacements
- Direct API clients with fetch/axios, SSE/WebSocket for streaming.
- Local storage/IndexedDB for settings (Dexie already in use).
- Web Notifications API or in-app toasts.
- Web Speech API or server-side TTS.
- i18next with JSON locale assets (drop `src/public/_locales`).
- Optional desktop agent over HTTP/WebSocket instead of native messaging.

## Dependency delta (extension vs current frontend)
Likely add to `tldw-frontend` (from extension)
- UI/state: `antd`, `@ant-design/cssinjs`, `zustand`, `react-i18next`, `i18next`, `i18next-browser-languagedetector`, `i18next-icu`
- UX/rendering: `react-markdown`, `remark-gfm`, `rehype-katex`, `rehype-mathjax`, `react-syntax-highlighter`, `prism-react-renderer`, `react-toastify`
- Data/infra: `dexie-react-hooks`, `@tanstack/react-virtual`, `@dnd-kit/*`, `dayjs`, `xlsx`
- Media/utilities: `dompurify`, `html2canvas`, `html-to-text`, `turndown`, `cheerio`, `@mozilla/readability`
- Charts/graph: `cytoscape`, `cytoscape-dagre`, `mermaid`, `d3-dsv`
- Icons: `lucide-react`, `@heroicons/react`, `react-icons`

Likely drop (extension-only)
- `wxt`, `@plasmohq/storage`, `@types/chrome`, `@types/firefox-webext-browser`, extension build tooling.
- `react-router-dom` (routes move to Next pages).

Version conflicts to resolve
- Tailwind v3 config in extension vs Tailwind v4 in `tldw-frontend`.
- Dexie version mismatch (extension `4.x`, frontend `3.x`).
- React version alignment (extension `18.2`, frontend `18.3`).

## Styling + assets to migrate
- Tailwind tokens from `<extension-repo>/tailwind.config.js`.
- CSS variables and token files in `<extension-repo>/src/styles/`.
- Fonts referenced in Tailwind config (Space Grotesk, Inter, Arimo).
- Icons and static assets in `<extension-repo>/src/public` (exclude `_locales`).
