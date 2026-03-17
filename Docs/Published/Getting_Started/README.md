# Getting Started (Self-Hosting Profiles)

Choose exactly one base setup profile and follow it end-to-end.

Recommended default:
- Run `make quickstart` from the repo root for the Docker single-user + WebUI path.
- Use `make quickstart-docker` if you want the API-only Docker path.
- Use `Docker multi-user + Postgres` when you need a team or public deployment.
- Use `Local single-user` for development, debugging, or contributor workflows.

Canonical base profiles:

1. [Local single-user](./Profile_Local_Single_User.md)
2. [Docker single-user](./Profile_Docker_Single_User.md)
3. [Docker multi-user + Postgres](./Profile_Docker_Multi_User_Postgres.md)

Optional add-ons:

- [GPU/STT Add-on](./GPU_STT_Addon.md) (apply after your base profile is working)

## How To Use These Guides

- Pick the profile that matches your target environment.
- For most users, start with the `quickstart-docker-webui` path via `make quickstart`.
- Complete the guide sections in order: prerequisites, install, run, verify, troubleshoot.
- Do not mix setup commands from other docs unless the guide explicitly links to them.
- Apply add-ons only after your chosen base profile is healthy.

## Notes

- This page is the onboarding index for self-hosting.
- For legacy/deeper reference material, use linked docs from each profile guide.

## Migration Disposition (2026-02-28)

Onboarding setup content was consolidated into these canonical guides.

| Path | Action | Replacement |
| --- | --- | --- |
| `README.md` | migrated | `Docs/Getting_Started/README.md` |
| `Docs/Deployment/First_Time_Production_Setup.md` | redirected | `Docs/Getting_Started/Profile_Docker_Multi_User_Postgres.md` |
| `Docs/User_Guides/Server/CLI_Reference.md` | redirected | `Docs/Getting_Started/README.md` |
