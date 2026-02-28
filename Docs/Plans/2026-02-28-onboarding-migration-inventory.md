# 2026-02-28 Onboarding Migration Inventory

This inventory records onboarding-adjacent documentation moved to the canonical self-hosting profile guides.

Canonical index: `Docs/Getting_Started/README.md`

| Path | Action | Replacement | Notes |
| --- | --- | --- | --- |
| `README.md` | migrated | `Docs/Getting_Started/README.md` | Root entry point now routes readers to profile chooser. |
| `Docs/Getting_Started/README.md` | migrated | `Docs/Getting_Started/README.md` | Rewritten as canonical profile index. |
| `Docs/Getting_Started/Profile_Local_Single_User.md` | migrated | `Docs/Getting_Started/Profile_Local_Single_User.md` | Canonical local single-user onboarding flow. |
| `Docs/Getting_Started/Profile_Docker_Single_User.md` | migrated | `Docs/Getting_Started/Profile_Docker_Single_User.md` | Canonical docker single-user onboarding flow. |
| `Docs/Getting_Started/Profile_Docker_Multi_User_Postgres.md` | migrated | `Docs/Getting_Started/Profile_Docker_Multi_User_Postgres.md` | Canonical docker multi-user plus Postgres onboarding flow. |
| `Docs/Getting_Started/GPU_STT_Addon.md` | migrated | `Docs/Getting_Started/GPU_STT_Addon.md` | Canonical optional GPU/STT add-on guide. |
| `Docs/User_Guides/Server/CLI_Reference.md` | redirected | `Docs/Getting_Started/README.md` | Removed startup setup walkthrough; now points to canonical profile guides. |
| `Docs/Deployment/First_Time_Production_Setup.md` | redirected | `Docs/Getting_Started/Profile_Docker_Multi_User_Postgres.md` | Removed duplicate install/setup command sequences; retained production hardening context. |
| `Docs/API-related/AuthNZ-API-Guide.md` | redirected | `Docs/Getting_Started/Profile_Local_Single_User.md` and `Docs/Getting_Started/Profile_Docker_Multi_User_Postgres.md` | Mode setup moved to profile docs; API contract guidance remains here. |
| `Docs/Code_Documentation/Code_Map.md` | updated | `Docs/Getting_Started/README.md` | Removed stale legacy ingestion endpoint reference; kept architecture mapping focus. |

## Cutover Rule

Setup commands for first-time self-hosting belong only in canonical profile guides under `Docs/Getting_Started/`.
