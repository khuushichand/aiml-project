# Google Keep Notes Import/Export Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a published WebUI user guide that explains how to move notes from Google Keep into tldw Notes, and how to export tldw notes back to Markdown for optional Google Keep re-import.

**Architecture:** This is a documentation-only change. The implementation adds one new Markdown guide under the published `Docs/User_Guides` tree, wires it into MkDocs navigation and the user-guide index, refreshes the curated `Docs/Published` mirror, and verifies that the resulting docs build succeeds. All content must stay aligned with currently verified Notes API and WebUI behavior.

**Tech Stack:** Markdown, MkDocs Material, existing `Docs/` publishing flow, FastAPI Notes import/export contracts, React Notes UI.

---

### Task 0: Isolated Worktree and Docs Tooling Preflight

**Files:**
- Verify only: git worktree metadata and docs tooling state

**Step 1: Create or switch to a dedicated worktree**

Run:
`git worktree add .worktrees/google-keep-notes-docs -b codex/google-keep-notes-docs`

Expected:
- A new isolated worktree is created.
- The branch name starts with `codex/`.

**Step 2: Verify branch isolation**

Run:
`cd .worktrees/google-keep-notes-docs && git branch --show-current && git rev-parse --show-toplevel`

Expected:
- Branch is `codex/google-keep-notes-docs`
- Top-level path is the worktree path, not the primary workspace root

**Step 3: Activate the project virtual environment**

Run:
`source .venv/bin/activate && python --version`

Expected:
- Python runs from the project virtual environment

**Step 4: Verify MkDocs tooling is available**

Run:
`source .venv/bin/activate && python -m mkdocs --version`

Expected:
- MkDocs prints a version and exits successfully

**Step 5: Commit**

No commit for preflight.

### Task 1: Create the Google Keep Notes Guide

**Files:**
- Create: `Docs/User_Guides/WebUI_Extension/Google_Keep_Notes_Import_Export_Guide.md`
- Reference: `tldw_Server_API/app/api/v1/schemas/notes_schemas.py`
- Reference: `tldw_Server_API/app/api/v1/endpoints/notes.py`
- Reference: `apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
- Reference: `apps/packages/ui/src/components/Notes/export-utils.ts`

**Step 1: Verify the guide does not already exist**

Run:
`test -f Docs/User_Guides/WebUI_Extension/Google_Keep_Notes_Import_Export_Guide.md`

Expected:
- Non-zero exit status because the file does not exist yet

**Step 2: Write the guide with the approved structure**

Create `Docs/User_Guides/WebUI_Extension/Google_Keep_Notes_Import_Export_Guide.md` with this structure:

```markdown
# Google Keep Notes Import and Export Guide

## Overview

Explain:
- Google Takeout is the official Google export/archive path
- `keep-it-markdown` is the practical bridge for producing Markdown files or importing Markdown back into Keep
- tldw Notes imports Markdown and JSON today

## Choose the right path

| Goal | Recommended path | Why |
| --- | --- | --- |
| Back up Google Keep | Google Takeout | Official export path |
| Move Google Keep notes into tldw | Takeout -> `keep-it-markdown` -> tldw Notes import | Matches current tldw Markdown import support |
| Move tldw notes back toward Keep | tldw Markdown export -> optional `keep-it-markdown import` | Best-effort only |

## Google Keep to tldw

### 1. Export from Google Takeout
- Link to `https://takeout.google.com/`
- Tell the user to export Keep data first

### 2. Convert/export notes with `keep-it-markdown`
- Link to `https://github.com/djsudduth/keep-it-markdown`
- Keep installation details brief and defer to upstream README
- Explain that the goal is to end up with `.md` note files

### 3. Import the notes into tldw
- Open the Notes page
- Use the Import action
- Upload `.md`, `.markdown`, or `.json`
- Explain duplicate strategies:
  - `skip`
  - `overwrite`
  - `create_copy`

### 4. What maps well and what does not
- Maps well: title, note body, simple tags/keywords
- May not map cleanly: reminders, Keep-specific metadata, some attachments, checklist/layout fidelity

## tldw back to Google Keep

### Preferred path: single-note export
- Export one note as Markdown from the Notes page
- Explain that single-note export writes front matter plus note body

### Bulk export caveat
- Explain that bulk Markdown export currently produces one combined `.md` file
- If the user wants many notes back in Keep, they may need to split the file into one note per file before using `keep-it-markdown import`

### Unofficial-import warning
- State clearly that `keep-it-markdown` reverse import depends on an unofficial Google Keep interface
- Recommend testing with a small batch first

## Troubleshooting and limitations

- Raw Google Keep Takeout HTML/JSON is not the documented direct import path for tldw
- tldw Markdown import uses `# Heading`, filename, or first non-empty line as title fallback
- Front matter `keywords:` and `tags:` can become tldw keywords
- Reverse Keep import can break if Google changes behavior or rate limits apply
```

**Step 3: Verify the required sections exist**

Run:
`rg -n "^## (Overview|Choose the right path|Google Keep to tldw|tldw back to Google Keep|Troubleshooting and limitations)$" Docs/User_Guides/WebUI_Extension/Google_Keep_Notes_Import_Export_Guide.md`

Expected:
- One match for each required section heading

**Step 4: Verify the guide includes the required external links and duplicate strategies**

Run:
`rg -n "takeout.google.com|keep-it-markdown|skip|overwrite|create_copy" Docs/User_Guides/WebUI_Extension/Google_Keep_Notes_Import_Export_Guide.md`

Expected:
- Matches for both external references
- Matches for all three duplicate strategies

**Step 5: Commit**

```bash
git add Docs/User_Guides/WebUI_Extension/Google_Keep_Notes_Import_Export_Guide.md
git commit -m "docs(user-guides): add Google Keep notes import/export guide"
```

### Task 2: Add Navigation and Landing-Page Links

**Files:**
- Modify: `Docs/mkdocs.yml`
- Modify: `Docs/User_Guides/index.md`

**Step 1: Verify the guide is not already linked**

Run:
`rg -n "Google Keep Notes Import and Export" Docs/mkdocs.yml Docs/User_Guides/index.md`

Expected:
- No matches yet

**Step 2: Add the MkDocs nav entry**

Update `Docs/mkdocs.yml` under `User Guides -> WebUI & Extension -> Chatbooks & Workflows`:

```yaml
          - Chatbooks & Workflows:
              - Chatbook User Guide: User_Guides/WebUI_Extension/Chatbook_User_Guide.md
              - Chatbook Tools Getting Started: User_Guides/WebUI_Extension/Chatbook_Tools_Getting_Started.md
              - Google Keep Notes Import and Export: User_Guides/WebUI_Extension/Google_Keep_Notes_Import_Export_Guide.md
              - Workflows Examples: User_Guides/WebUI_Extension/Workflows_Examples.md
```

**Step 3: Add the index link**

Update `Docs/User_Guides/index.md` under `### Chatbooks and Workflows`:

```markdown
- [Chatbook User Guide](WebUI_Extension/Chatbook_User_Guide.md)
- [Chatbook Tools Getting Started](WebUI_Extension/Chatbook_Tools_Getting_Started.md)
- [Google Keep Notes Import and Export](WebUI_Extension/Google_Keep_Notes_Import_Export_Guide.md)
- [Workflows Examples](WebUI_Extension/Workflows_Examples.md)
```

If the section does not exist yet, create it and keep the section title parallel with the MkDocs navigation.

**Step 4: Verify the links are present**

Run:
`rg -n "Google Keep Notes Import and Export" Docs/mkdocs.yml Docs/User_Guides/index.md`

Expected:
- One match in `Docs/mkdocs.yml`
- One match in `Docs/User_Guides/index.md`

**Step 5: Commit**

```bash
git add Docs/mkdocs.yml Docs/User_Guides/index.md
git commit -m "docs(nav): link Google Keep notes guide"
```

### Task 3: Refresh the Curated Published Docs

**Files:**
- Generated by script: `Docs/Published/User_Guides/WebUI_Extension/Google_Keep_Notes_Import_Export_Guide.md`
- Generated by script: `Docs/Published/User_Guides/index.md`

**Step 1: Verify the published guide is absent before refresh**

Run:
`test -f Docs/Published/User_Guides/WebUI_Extension/Google_Keep_Notes_Import_Export_Guide.md`

Expected:
- Non-zero exit status before the refresh script runs

**Step 2: Refresh the curated docs**

Run:
`bash Helper_Scripts/refresh_docs_published.sh`

Expected:
- The script completes successfully
- `Docs/Published/User_Guides/` is refreshed from `Docs/User_Guides/`

**Step 3: Verify the published guide and published index were updated**

Run:
`test -f Docs/Published/User_Guides/WebUI_Extension/Google_Keep_Notes_Import_Export_Guide.md && rg -n "Google Keep Notes Import and Export" Docs/Published/User_Guides/index.md`

Expected:
- The published guide file exists
- The published index contains the new link

**Step 4: Spot-check that the generated guide content matches the source**

Run:
`diff -u Docs/User_Guides/WebUI_Extension/Google_Keep_Notes_Import_Export_Guide.md Docs/Published/User_Guides/WebUI_Extension/Google_Keep_Notes_Import_Export_Guide.md`

Expected:
- No differences

**Step 5: Commit**

```bash
git add Docs/Published/User_Guides/WebUI_Extension/Google_Keep_Notes_Import_Export_Guide.md \
  Docs/Published/User_Guides/index.md
git commit -m "docs(published): refresh Google Keep notes guide"
```

### Task 4: Verify the Guide Against Product Behavior and Build the Docs

**Files:**
- Verify only unless fixes are required

**Step 1: Re-verify the documented Notes import contract**

Run:
`rg -n "format: Literal\\[\"json\", \"markdown\"\\]|duplicate_strategy: Literal\\[\"skip\", \"overwrite\", \"create_copy\"\\]" tldw_Server_API/app/api/v1/schemas/notes_schemas.py`

Expected:
- Matches proving the guide's import-format and duplicate-strategy claims are still accurate

**Step 2: Re-verify the documented WebUI behavior**

Run:
`rg -n "accept=\".json,.md,.markdown|duplicate_strategy: importDuplicateStrategy|notes-export.md|buildSingleNoteMarkdown" apps/packages/ui/src/components/Notes/NotesManagerPage.tsx apps/packages/ui/src/components/Notes/export-utils.ts`

Expected:
- Matches proving the guide's WebUI import/export claims are still accurate

**Step 3: Build the docs site**

Run:
`source .venv/bin/activate && python -m mkdocs build -f Docs/mkdocs.yml`

Expected:
- MkDocs build succeeds without broken-path errors for the new page

**Step 4: Fix any wording or nav issues exposed by verification, then rerun**

If any command above fails:
- correct the guide text or navigation
- rerun the failed command until it passes

**Step 5: Commit**

```bash
git add Docs/User_Guides/WebUI_Extension/Google_Keep_Notes_Import_Export_Guide.md \
  Docs/mkdocs.yml \
  Docs/User_Guides/index.md \
  Docs/Published/User_Guides/WebUI_Extension/Google_Keep_Notes_Import_Export_Guide.md \
  Docs/Published/User_Guides/index.md
git commit -m "docs: finalize Google Keep notes migration guide"
```

## Security and Quality Notes

- Bandit is not applicable for this implementation because the touched scope is Markdown and MkDocs navigation rather than executable Python.
- Do not manually edit `Docs/Published/` files; always regenerate them with `Helper_Scripts/refresh_docs_published.sh`.
- Keep every product claim tied to verified source behavior in `notes.py`, `notes_schemas.py`, `NotesManagerPage.tsx`, or `export-utils.ts`.
