# Flashcards

## 1. Descriptive of Current Feature Set

- Purpose: Export learning material as Anki `.apkg` decks for spaced repetition.
- Capabilities:
  - Build Basic and Cloze models; multi-template cards with Extra field
  - Deterministic IDs, scheduling defaults, deck metadata
  - Package assembly with media-less decks (cards only)
- Inputs/Outputs:
  - Inputs: rows (front/back/extra or cloze text) and deck definitions
  - Outputs: single `.apkg` file stream or bytes for download
- Related Endpoints:
  - (No direct endpoints; used by higher-level export flows)
- Related Module:
  - `tldw_Server_API/app/core/Flashcards/apkg_exporter.py:1`

## 2. Technical Details of Features

- Architecture & Data Flow:
  - Pure-Python APKG generator that writes SQLite structures into a zip container with deck JSON
- Key Classes/Functions:
  - `export_apkg_from_rows` (builds deck, models, notes, cards)
  - Utility helpers: `_build_models_json`, `_build_decks_json`, `_build_conf_json`, `_compute_card_sched`
- Dependencies:
  - Standard library (sqlite3, zipfile); no network
- Data Models & DB:
  - On-the-fly Anki collection schema creation; no persistent server DB usage
- Configuration:
  - None required; card styling and deck names passed in
- Concurrency & Performance:
  - In-memory build; large decks may require temp files (handled internally)
- Error Handling:
  - Validates inputs and falls back to defaults for optional fields
- Security:
  - No external I/O apart from optional file write by caller

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure:
  - `Flashcards/apkg_exporter.py` (single-purpose exporter)
- Extension Points:
  - Add new model templates; add media embedding if needed
- Coding Patterns:
  - Keep exporter side-effect-free; return bytes for API download paths
- Tests:
  - `tldw_Server_API/tests/Flashcards/test_apkg_exporter.py:1`
- Local Dev Tips:
  - Generate a small deck with 2–3 notes and inspect in Anki
- Pitfalls & Gotchas:
  - Very large decks impact memory; consider streaming write patterns if expanded
- Roadmap/TODOs:
  - Optional media support; style presets per project
