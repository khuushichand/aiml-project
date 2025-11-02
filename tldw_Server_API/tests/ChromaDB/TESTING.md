ChromaDB Tests - Running and Skips

This note explains why some ChromaDB tests are skipped/xfail and how to run or avoid them.

Skip/xfail categories
- requires_model (gated by network/model availability)
  - What: Tests that need lightweight HuggingFace models or external providers.
  - Default: Skipped unless enabled.
  - Enable: `RUN_MODEL_TESTS=1 pytest -m "requires_model"` or `pytest --run-model-tests`.
  - Notes: Requires network access; may download small models on first run.

- legacy_skip and xfail (targets legacy/internals or not-yet-implemented APIs)
  - What: Tests that exercised internal helpers or features not present in the current API.
  - Markers: `@pytest.mark.legacy_skip` and `@pytest.mark.xfail(strict=False, reason=...)`.
  - Why: Keeps intent visible without failing the suite; documents future work via TODO tags.
  - Include anyway: `pytest -m "legacy_skip or xfail"
  - Exclude explicitly: default runs already pass; you can also use `-m "not legacy_skip"` to filter them out.

- Environment/version-conditional skips
  - What: Tests with an inline `pytest.skip(...)` when the underlying ChromaDB client/platform exhibits known init/path issues (e.g., collection re-open on certain versions/OS).
  - How to run: Use a ChromaDB version/OS combination where the known issue does not reproduce, then the test will run normally.

Quick recipes
- Run all unit tests without model downloads:
  - `pytest -m "unit and not requires_model and not legacy_skip" -q`

- Run integration tests using deterministic embeddings only (no network):
  - `pytest tldw_Server_API/tests/ChromaDB/integration -q`

- Enable model-backed tests (requires network):
  - `RUN_MODEL_TESTS=1 pytest -m "requires_model" -q`

- See what’s being skipped and why:
  - `pytest -q -rs` (reports skip reasons)

Notes
- The `legacy_skip` marker is informational; tests are also marked `xfail(strict=False)` to prevent failures when they run. If a feature is implemented, replace the marker with a real assertion-based test.
- For CI environments with restricted `/tmp`, set `TMPDIR` to a workspace path: `TMPDIR=$PWD/.tmp pytest ...`.
