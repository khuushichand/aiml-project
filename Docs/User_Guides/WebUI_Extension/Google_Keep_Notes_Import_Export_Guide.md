# Google Keep Notes Import and Export Guide

This guide explains the safest ways to move notes between Google Keep and tldw Notes using:

- [Google Takeout](https://takeout.google.com/) for an official Google export/archive
- [keep-it-markdown](https://github.com/djsudduth/keep-it-markdown) for Markdown export/import workflows
- the existing tldw Notes import/export features in the WebUI

## Overview

There are two different paths here, and they are not equivalent:

- `Google Takeout` is Google's official archive/export path. If you want a backup before you touch anything else, start here.
- `keep-it-markdown` (KIM) is a third-party command-line tool that uses an unofficial Google Keep API to export notes as Markdown and import Markdown back into Keep.

For tldw users, the practical migration path is usually:

1. Export or back up your Google Keep notes.
2. Produce Markdown files with `keep-it-markdown`.
3. Import those `.md` files into tldw Notes.

If you want a clean rollback path, make a Google Takeout archive first, even if you plan to use KIM for the actual Markdown export.

## Choose The Right Path

| Goal | Recommended path | Why |
| --- | --- | --- |
| Back up Google Keep | Google Takeout | Official export path from Google |
| Move Google Keep notes into tldw | KIM export to Markdown, then import into tldw Notes | Matches tldw's current Markdown import support |
| Move tldw notes back toward Keep | Export Markdown from tldw, then optionally use `keep-it-markdown -i` | Best-effort only; not a perfect round trip |

## Google Keep To tldw

### 1. Create a backup first

Open [Google Takeout](https://takeout.google.com/) and export your Keep data before you start any migration work.

Why this matters:

- it gives you an official archive of your notes
- it gives you a recovery point if the Markdown conversion is not what you expected
- KIM's import/export workflow uses an unofficial API, so you should keep a vendor-provided backup

### 2. Export Keep notes as Markdown with KIM

KIM's upstream README says it can:

- convert Google Keep notes to Markdown
- export notes as individual Markdown files
- import Markdown files back into Keep

The upstream project also warns that it uses an unofficial Google Keep API and that Google could change that API at any time.

Recommended approach:

1. Read the upstream project instructions: [keep-it-markdown](https://github.com/djsudduth/keep-it-markdown)
2. Install KIM in its own directory
3. Test on a very small batch first
4. Export the notes you want as `.md` files

Useful upstream behaviors to know:

- KIM exports notes as individual Markdown files
- KIM can preserve labels/tags in Markdown-friendly form
- KIM can also export media files where supported
- KIM recommends starting with a small query rather than exporting everything immediately

If you prefer to archive first and migrate second, do the Takeout backup first, then run KIM for the Markdown export.

### 3. Import the Markdown files into tldw Notes

In the tldw WebUI:

1. Open the `Notes` page
2. Click `Import`
3. Upload your `.md`, `.markdown`, or `.json` files
4. Choose a duplicate strategy
5. Confirm the import

tldw currently supports these duplicate strategies:

- `skip`: ignore imported notes whose IDs already exist
- `overwrite`: replace matching note IDs with the imported content
- `create_copy`: create a new note instead of reusing the imported ID

For Markdown imports, tldw currently derives the title in this order:

1. a top-level Markdown heading like `# My Note`
2. the filename
3. the first non-empty line

### 4. What usually maps cleanly

These fields usually survive the Keep -> Markdown -> tldw path well:

- note title
- note body text
- simple labels/tags when they appear as Markdown tags or front matter

tldw can also turn front matter such as `keywords:` or `tags:` into note keywords during Markdown import.

### 5. What may not round-trip cleanly

Do not expect a perfect 1:1 conversion for Keep-specific features such as:

- reminders
- pin/archive state
- checklist layout fidelity
- drawing and attachment behavior
- audio/media metadata
- other Keep-specific metadata or formatting details

Treat the Markdown export as a content migration, not an exact product clone.

## tldw Back To Google Keep

### Preferred path: export one note at a time

If you want to move a note from tldw back into Google Keep, the cleanest route is:

1. open the note in tldw
2. export it as Markdown
3. import that Markdown file with KIM

tldw's single-note Markdown export currently writes:

- front matter for keywords when present
- a `# Title` heading
- the note body content

That shape is easier to work with than the bulk Markdown export.

### Bulk export caveat

tldw also supports bulk Markdown export from the Notes page, but the current behavior is different:

- bulk export writes one combined `notes-export.md` file
- it does not create one Markdown file per note

If you want to re-import many notes into Google Keep through KIM, you will likely need to:

1. export from tldw
2. split the combined Markdown file into one file per note
3. place those files in a single directory
4. import that directory with KIM

### KIM import warnings

KIM's upstream README calls out several import restrictions:

- import uses `python kim.py -i`
- Google may lock you out if you try to import too many files too quickly
- import is limited to a single directory, not nested subdirectories
- KIM imports `.md` and `.txt` files
- KIM does not import media during this flow
- KIM does not scan files to create new labels automatically
- only existing Keep labels can be reused

Because of those limits, test with a handful of notes first before attempting a large reverse import.

## Troubleshooting And Limitations

### tldw does not directly import raw Google Keep exports

The documented tldw import paths are:

- Markdown files
- JSON note payloads or note-export wrappers

That means raw Google Keep Takeout output is not the documented direct import format for tldw Notes. Use KIM or another conversion step to produce Markdown first.

### My imported note title looks wrong

For Markdown import, tldw currently uses:

1. `# Heading`
2. filename
3. first non-empty line

If you want predictable titles, make sure each file starts with a clear `# Title` heading.

### My labels did not come across

KIM and tldw do not use the exact same label model as Google Keep. For the best results:

- keep labels simple
- prefer Markdown-friendly tags
- use `keywords:` or `tags:` front matter when you want tldw keywords on import

### Importing back into Keep is failing or risky

KIM uses an unofficial Google Keep API. The upstream project explicitly warns that:

- Google can change the API
- imports can hit Google rate limits
- very large imports can trigger account lockouts

Use a small batch first and keep your Google Takeout backup.

## Recommended Safe Workflow

If you want the lowest-risk path:

1. Export a Keep backup from [Google Takeout](https://takeout.google.com/)
2. Use [keep-it-markdown](https://github.com/djsudduth/keep-it-markdown) to export a small set of Keep notes to Markdown
3. Import those Markdown files into tldw Notes
4. Verify the results
5. Repeat on larger batches only after the small test looks correct

If you later need to move notes back toward Keep, start with single-note Markdown export from tldw before attempting any large bulk reverse import.
