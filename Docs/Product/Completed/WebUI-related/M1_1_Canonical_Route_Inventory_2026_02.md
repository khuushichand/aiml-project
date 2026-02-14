# M1.1 Canonical Route Inventory (WebUI)

Status: Complete (Initial Draft)  
Owner: WebUI + Product  
Milestone: M1.1 (February 13-February 17, 2026)  
Last Updated: February 12, 2026  
Related: `Docs/Product/WebUI/M1_Navigation_IA_Execution_Plan_2026_02.md`

## Purpose

Define the route source of truth for WebUI navigation consolidation, including:
- Canonical app routes
- Sidepanel routes
- Legacy/alias redirects
- Wrapper-only and standalone pages that are outside the registry

## Source of Truth Inputs

- `apps/packages/ui/src/routes/route-registry.tsx`
- `apps/packages/ui/src/routes/route-paths.ts`
- `apps/tldw-frontend/pages/**/*.tsx`
- `apps/tldw-frontend/components/navigation/RouteRedirect.tsx`
- `apps/tldw-frontend/e2e/smoke/page-inventory.ts`

## Inventory Summary

- Option routes in registry: `64`
- Sidepanel routes in registry: `5`
- Next page alias redirects (`RouteRedirect` pages): `19`
- Standalone/wrapper pages outside registry: `11`

## A) Canonical Option Routes (Registry)

Route status key:
- `Canonical`: primary destination
- `Beta`: canonical but marked beta in nav metadata
- `Alias`: legacy route that forwards to canonical destination
- `Candidate Alias`: duplicate entry point to same destination; needs M1 decision

| Route | IA Area | Status | Notes |
|---|---|---|---|
| `/` | Core | Canonical | Home/landing shell |
| `/setup` | Core | Canonical | Setup route |
| `/chat` | Core | Canonical | Chat-focused entry |
| `/onboarding-test` | Core | Canonical | Test/onboarding harness |
| `/settings` | Settings | Canonical | General settings landing |
| `/settings/tldw` | Settings (Server/Auth) | Canonical | Server connection/auth |
| `/settings/model` | Settings (Server) | Canonical | Model/provider settings |
| `/settings/chat` | Settings (Server) | Canonical | Chat behavior settings |
| `/settings/ui` | Settings (Server) | Canonical | UI customization |
| `/settings/splash` | Settings (Server) | Canonical | Splash controls |
| `/settings/quick-ingest` | Settings (Server) | Canonical | Ingest behavior |
| `/settings/speech` | Settings (Server) | Canonical | Speech settings |
| `/settings/image-generation` | Settings (Server) | Canonical | Image generation |
| `/settings/evaluations` | Settings (Server) | Beta | Evaluation settings |
| `/settings/processed` | Settings | Canonical | Processed content settings |
| `/settings/health` | Settings (Server) | Canonical | Health/diagnostics |
| `/settings/prompt-studio` | Settings (Server) | Beta | Prompt Studio settings surface |
| `/settings/rag` | Settings (Server) | Canonical | RAG settings |
| `/settings/guardian` | Settings (Server) | Beta | Guardian controls |
| `/settings/knowledge` | Settings (Knowledge) | Canonical | Knowledge settings |
| `/settings/chatbooks` | Settings (Knowledge) | Canonical | Chatbooks settings |
| `/settings/world-books` | Settings (Knowledge) | Canonical | World books settings |
| `/settings/chat-dictionaries` | Settings (Knowledge) | Canonical | Dictionary settings |
| `/settings/characters` | Settings (Knowledge) | Canonical | Character settings |
| `/settings/prompt` | Settings (Workspace) | Canonical | Prompt workspace settings |
| `/settings/share` | Settings (Workspace) | Canonical | Share settings |
| `/settings/about` | Settings (About) | Canonical | About/info |
| `/knowledge` | Knowledge | Canonical | Knowledge QA workspace |
| `/media` | Knowledge | Canonical | Media workspace |
| `/media-trash` | Knowledge | Canonical | Trash view |
| `/world-books` | Knowledge | Canonical | World books workspace |
| `/dictionaries` | Knowledge | Canonical | Dictionaries workspace |
| `/characters` | Knowledge | Canonical | Characters workspace |
| `/prompts` | Knowledge | Canonical | Unified prompts workspace |
| `/prompt-studio` | Knowledge | Alias | Redirects to `/prompts?tab=studio` |
| `/media-multi` | Workspace | Canonical | Multi-item review |
| `/review` | Workspace | Alias | Redirects to `/media-multi` |
| `/content-review` | Workspace | Canonical | Content review queue |
| `/notes` | Workspace | Canonical | Notes workspace |
| `/flashcards` | Workspace | Canonical | Flashcards |
| `/quiz` | Workspace | Beta | Quiz workspace |
| `/collections` | Workspace | Beta | Collections |
| `/watchlists` | Workspace | Canonical | Watchlists |
| `/chatbooks` | Workspace | Canonical | Chatbooks playground |
| `/kanban` | Workspace | Canonical | Kanban playground |
| `/data-tables` | Workspace | Beta | Data tables studio |
| `/document-workspace` | Workspace | Beta | Constant path from `route-paths.ts` |
| `/workspace-playground` | Workspace | Beta | Research studio |
| `/model-playground` | Workspace | Beta | Model playground |
| `/writing-playground` | Workspace | Beta | Writing playground |
| `/workflow-editor` | Workspace | Beta | Workflow editor |
| `/acp-playground` | Workspace | Beta | ACP playground |
| `/skills` | Workspace | Beta | Skills surface |
| `/audiobook-studio` | Workspace | Beta | Audiobook studio |
| `/evaluations` | Workspace | Canonical | Evaluations workspace |
| `/chunking-playground` | Workspace | Canonical | Chunking tools |
| `/moderation-playground` | Workspace | Canonical | Moderation tools |
| `/tts` | Audio | Canonical | TTS playground |
| `/stt` | Audio | Canonical | STT playground |
| `/speech` | Audio | Canonical | Speech playground |
| `/documentation` | Help | Canonical | Documentation page |
| `/admin/server` | Admin | Canonical | Server admin |
| `/admin/llamacpp` | Admin | Canonical | Llama.cpp admin |
| `/admin/mlx` | Admin | Canonical | MLX admin |
| `/quick-chat-popout` | Utility | Canonical | Detached quick chat route |

## B) Canonical Sidepanel Routes (Registry)

| Route | Status | Notes |
|---|---|---|
| `/` | Canonical | Sidepanel chat |
| `/agent` | Canonical | Sidepanel agent |
| `/persona` | Canonical | Sidepanel persona |
| `/settings` | Canonical | Sidepanel settings |
| `/error-boundary-test` | Debug | Sidepanel error-boundary test route |

## C) Legacy Alias Redirect Matrix (Next Pages)

These aliases are implemented in `apps/tldw-frontend/pages/**` using `RouteRedirect`.

| Alias Route | Canonical Route | Suggested Lifecycle (M1) | Current State |
|---|---|---|---|
| `/search` | `/knowledge` | Keep + instrument usage | Active redirect |
| `/config` | `/settings` | Keep + instrument usage | Active redirect |
| `/profile` | `/settings` | Keep + instrument usage | Active redirect |
| `/privileges` | `/settings` | Keep + instrument usage | Active redirect |
| `/audio` | `/speech` | Keep + instrument usage | Active redirect |
| `/reading` | `/collections` | Keep + instrument usage | Active redirect |
| `/claims-review` | `/content-review` | Keep + instrument usage | Active redirect |
| `/review` | `/media-multi` | Keep + instrument usage | Active redirect |
| `/media/:id/view` | `/media` | Keep + instrument usage | Active redirect |
| `/connectors` | `/settings` | Keep + instrument usage | Active redirect |
| `/connectors/browse` | `/settings` | Keep + instrument usage | Active redirect |
| `/connectors/jobs` | `/settings` | Keep + instrument usage | Active redirect |
| `/connectors/sources` | `/settings` | Keep + instrument usage | Active redirect |
| `/admin` | `/admin/server` | Keep + instrument usage | Active redirect |
| `/admin/orgs` | `/admin/server` | Keep + instrument usage | Active redirect |
| `/admin/data-ops` | `/admin/server` | Keep + instrument usage | Active redirect |
| `/admin/watchlists-items` | `/admin/server` | Keep + instrument usage | Active redirect |
| `/admin/watchlists-runs` | `/admin/server` | Keep + instrument usage | Active redirect |
| `/admin/maintenance` | `/admin/server` | Keep + instrument usage | Active redirect |

## D) Wrapper/Standalone Pages Outside Route Registry

| Page Route | Classification | Resolution Target |
|---|---|---|
| `/chat/agent` | Wrapper (sidepanel) | Align to `/agent` conventions |
| `/chat/settings` | Wrapper (sidepanel) | Align to `/settings` sidepanel conventions |
| `/document-workspace` | Wrapper (option route constant) | Keep; ensure parity in inventory tooling |
| `/items` | Orphan workspace page | Decide canonicalization: add to registry or retire |
| `/login` | Standalone auth utility | Keep and define explicit relation to `/settings/tldw` |
| `/for/journalists` | Standalone marketing/segment page | Keep outside app-route registry |
| `/for/osint` | Standalone marketing/segment page | Keep outside app-route registry |
| `/for/researchers` | Standalone marketing/segment page | Keep outside app-route registry |
| `/404` | System route | Keep as dedicated recovery page |
| `/__debug__/authz.spec` | Debug route | Keep internal only |
| `/__debug__/sidepanel-error-boundary` | Debug wrapper | Maps to sidepanel error-boundary test |

## E) Coverage and Alignment Notes

- `page-inventory.ts` includes both canonical and alias routes for smoke purposes.
- `route-registry.tsx` is the canonical app-route definition for options/sidepanel.
- Current mismatch to resolve in M1.1/M1.2:
  - Registry routes without Next wrappers (`/acp-playground`, `/audiobook-studio`, `/model-playground`, `/prompt-studio`, `/settings/image-generation`, `/settings/ui`, `/skills`, `/writing-playground`).
  - Next wrapper route not in registry (`/items`).

## M1.1 Decisions Required

1. Decide whether `/items` becomes a canonical registry route or is sunset.
2. Decide if wrapper parity is required for all registry routes in WebUI deep linking.
3. Approve alias deprecation policy threshold (based on M1.4 telemetry).

## Change Log

- February 12, 2026: Initial canonical inventory and alias matrix published.
- February 12, 2026: Converted `/review` to an explicit alias redirect to `/media-multi`.
