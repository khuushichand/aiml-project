# Flashcards Study Guide

_Last updated: 2026-02-18_

This guide explains the Flashcards flow in `Study`, `Manage`, and `Transfer`, including scheduling basics, cloze syntax, and import/export formats.

## Daily Study Workflow

1. Add cards through `Manage` (manual create), `Transfer` import, or `Transfer` generate.
2. Open `Study` and review due cards.
3. Reveal the answer, then rate recall (`Again`, `Hard`, `Good`, `Easy`).
4. Repeat daily. The scheduler adjusts next due dates from your ratings.

## Ratings and Scheduling Basics

The review buttons map to SM-2 quality values:

| Button | Quality | Meaning |
|---|---:|---|
| Again | 0 | You forgot the card; repeat soon. |
| Hard | 2 | You recalled with effort; keep interval short. |
| Good | 3 | Normal successful recall. |
| Easy | 5 | Very easy recall; increase interval more aggressively. |

Scheduling terms shown in UI:

- `Memory strength` (`ef`): Ease factor controlling interval growth.
- `Next review gap` (`interval_days`): Days until next scheduled review.
- `Recall runs` (`repetitions`): Successful recall count.
- `Relearns` (`lapses`): Times the card was forgotten after learning.

## Cloze Syntax

Use cloze cards when you want blanks inside sentence context.

- Required pattern: `{{c1::answer}}`
- Multiple deletions are allowed (`{{c2::...}}`, `{{c3::...}}`, etc.)
- At least one cloze deletion must appear in `Front` text for cloze cards

Example:

`The powerhouse of the cell is the {{c1::mitochondrion}}.`

## Import and Export Formats

### Delimited (CSV/TSV)

Accepted header names include:

- `Deck`, `Front`, `Back`, `Tags`, `Notes`, `Extra`
- `Model_Type`, `Reverse`, `Is_Cloze`, `Deck_Description`

Notes:

- Without headers, default column order is `Deck, Front, Back, Tags, Notes`.
- `Tags` can be comma-separated or space-separated.
- If imports fail by row, use row-level errors in `Transfer` and jump to inline format help.

### JSON / JSONL

Supported fields:

- `deck`/`deck_name`
- `front`/`question`
- `back`/`answer`
- `tags` (array or string)
- `notes`, `extra`, `model_type`, `reverse`, `is_cloze`

Accepted payload forms:

- JSON array of items
- JSON object containing `items`
- JSONL (`.jsonl` / `.ndjson`) with one object per line

### APKG Export

APKG export is available from `Transfer` and preserves scheduling metadata for Anki import.

## Troubleshooting

- `Missing required field`: verify header mapping and ensure required values are present.
- `Invalid cloze`: ensure `Front` includes at least one `{{cN::...}}` deletion.
- `Line too long`: check delimiter selection and malformed line breaks.
- `Maximum import`: split into smaller batches and retry.
