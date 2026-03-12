# Google Keep Notes Import/Export Design

Date: 2026-03-07
Status: Approved
Scope: User-facing documentation for moving notes between Google Keep and tldw Notes

## 1. Summary

Add a published WebUI user guide that explains how to:

- export notes from Google Keep using Google Takeout
- convert Google Keep exports into Markdown with `keep-it-markdown`
- import those Markdown files into tldw Notes
- export tldw notes back out as Markdown for optional re-import into Google Keep

The guide is documentation-only. No backend or WebUI behavior changes are part of this scope.

## 2. User-Approved Decisions

1. The deliverable is a single end-user guide, not an API-first reference.
2. The primary workflow is `Google Keep -> tldw Notes`.
3. `keep-it-markdown` is documented as the practical bridge for Markdown-based migration.
4. Reverse flow `tldw Notes -> Google Keep` is included as a secondary, best-effort workflow with explicit warnings.
5. The guide should be published under the existing WebUI user guides.

## 3. Current State

### 3.1 Verified tldw behavior

The current product already supports the workflows the guide will describe:

- Notes import accepts `json` and `markdown` items via `POST /api/v1/notes/import`.
- Supported duplicate strategies are `skip`, `overwrite`, and `create_copy`.
- Markdown import derives titles from:
  - `# Heading`
  - filename fallback
  - first non-empty line
- Markdown front matter can populate keywords from `keywords:` or `tags:`.
- The WebUI Notes page already exposes:
  - import from `.json`, `.md`, and `.markdown`
  - single-note Markdown export
  - bulk Markdown export

Relevant verified code paths:

- `tldw_Server_API/app/api/v1/schemas/notes_schemas.py`
- `tldw_Server_API/app/api/v1/endpoints/notes.py`
- `apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
- `apps/packages/ui/src/components/Notes/export-utils.ts`

### 3.2 Important product limitations

- Raw Google Keep Takeout exports are not documented as directly importable into tldw.
- Bulk Markdown export from the Notes page currently produces a single combined `.md` file, not one file per note.
- Reverse import into Google Keep through `keep-it-markdown` depends on an unofficial Google Keep interface and should be described as best effort only.

## 4. Goals and Non-Goals

### 4.1 Goals

- Provide a clear migration path from Google Keep into tldw Notes.
- Keep the instructions grounded in currently supported product behavior.
- Distinguish official Google export paths from unofficial import tooling.
- Reduce user confusion about what metadata round-trips cleanly and what does not.

### 4.2 Non-Goals

- Building direct native Google Keep import/export into tldw.
- Documenting every `keep-it-markdown` feature or flag.
- Expanding the Notes API or WebUI.
- Adding screenshots or UI redesign work in this scope.

## 5. Proposed Documentation Placement

Create a new published guide at:

- `Docs/User_Guides/WebUI_Extension/Google_Keep_Notes_Import_Export_Guide.md`

Update navigation in:

- `Docs/mkdocs.yml`
- `Docs/User_Guides/index.md`

This keeps the guide in the published docs set and places it with other end-user WebUI workflows.

## 6. Guide Structure

The guide should contain four main sections.

### 6.1 Overview and decision table

Explain the difference between:

- Google Takeout as the official archive/export source
- `keep-it-markdown` as the practical conversion/import bridge

Include a short decision table:

- backup/archive Google Keep data
- migrate Google Keep notes into tldw
- export tldw notes back to Markdown for Keep re-import

### 6.2 Google Keep to tldw

Document the recommended flow:

1. Export Keep data from Google Takeout.
2. Use `keep-it-markdown` to convert/export Keep notes into Markdown files.
3. Open tldw Notes and import the generated `.md` files.
4. Explain duplicate handling in plain language.

Document what should map cleanly:

- note title
- note body
- labels/tags when represented as Markdown front matter or imported tags

Document likely gaps:

- reminders
- checklists/layout fidelity
- attachments and other Keep-specific metadata

### 6.3 tldw back to Google Keep

Document the secondary reverse path:

1. Export a single tldw note as Markdown when possible.
2. For bulk export, explain that the current output is one combined Markdown file.
3. If the user wants to re-import many notes into Keep, they may need to split the combined file into one note per file before using `keep-it-markdown import`.

The guide must clearly warn that this is not a guaranteed 1:1 round trip.

### 6.4 Troubleshooting and limitations

Cover specific issues:

- JSON import expectations in tldw
- Markdown title extraction behavior
- keyword/tag front matter behavior
- unofficial Google Keep import caveats
- recommendation to test a small batch first

## 7. Content Rules

The guide should:

- be written for end users, not backend integrators
- include only lightweight command examples
- avoid claiming support that is not verified in this repository
- link to the external tools instead of duplicating their full installation manuals
- call out unofficial tooling clearly and early

## 8. Verification Plan

Implementation should verify:

1. The new source guide exists under `Docs/User_Guides/WebUI_Extension/`.
2. The guide is added to the WebUI navigation in `Docs/mkdocs.yml`.
3. The guide is linked from `Docs/User_Guides/index.md`.
4. `Helper_Scripts/refresh_docs_published.sh` propagates it into `Docs/Published/User_Guides/WebUI_Extension/`.
5. `mkdocs build -f Docs/mkdocs.yml` succeeds after the doc is added.

Bandit is not required for the final implementation because the touched scope is Markdown and MkDocs navigation, not executable Python.

## 9. Recommended Implementation Sequence

1. Draft the guide content from verified product behavior.
2. Add the navigation and landing-page link.
3. Refresh published docs.
4. Run a local docs build.
5. Review wording for unsupported or over-broad claims.
