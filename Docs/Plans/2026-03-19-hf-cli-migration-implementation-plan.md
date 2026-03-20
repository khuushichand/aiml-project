# Hugging Face CLI Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace outdated `huggingface-cli` references with `hf`, refresh adjacent install guidance toward `pip install -U "huggingface_hub"`, and keep package/import references unchanged.

**Architecture:** Treat this as a targeted text migration with one runtime/test string change and a bounded docs sweep. Update the regression test first so the runtime help text change is test-driven, then apply the matching Python string update, and finally sweep the affected docs and READMEs for CLI and install-guidance consistency.

**Tech Stack:** Python, pytest, Markdown, Bandit, ripgrep

---

## Stage 1: Capture The Approved Design
**Goal:** Record the migration scope, constraints, and preferred install guidance.
**Success Criteria:** A task-specific design note exists under `docs/plans/` and reflects the approved approach.
**Tests:** None.
**Status:** Complete

## Stage 2: Add The Failing Regression Expectation
**Goal:** Prove that the current runtime guidance still points users at `huggingface-cli`.
**Success Criteria:** The targeted unit test fails before implementation because it expects `hf download`.
**Tests:** `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Audio/test_qwen3_asr.py -k validate_model_path_missing_no_download -v`
**Status:** Not Started

## Stage 3: Implement The Runtime String Update
**Goal:** Update user-facing runtime guidance to `hf download` and keep the test green.
**Success Criteria:** The targeted test passes with the new help text.
**Tests:** `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Audio/test_qwen3_asr.py -k validate_model_path_missing_no_download -v`
**Status:** Not Started

## Stage 4: Sweep Docs And READMEs
**Goal:** Replace legacy CLI naming and modernize adjacent install guidance in the current touch set.
**Success Criteria:** All current `huggingface-cli`/`huggingface_cli` references are updated, and nearby guidance prefers `pip install -U "huggingface_hub"` where CLI setup is being described.
**Tests:** `rg -n "huggingface-cli|huggingface_cli" /Users/macbook-dev/Documents/GitHub/tldw_server2`
**Status:** Not Started

## Stage 5: Verify Regression And Security
**Goal:** Confirm the migration is complete and the touched Python scope has no new Bandit findings.
**Success Criteria:** Targeted pytest, repo grep, and Bandit runs succeed.
**Tests:** `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Audio/test_qwen3_asr.py -k validate_model_path_missing_no_download -v`; `rg -n "huggingface-cli|huggingface_cli" /Users/macbook-dev/Documents/GitHub/tldw_server2`; `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Transcription_Qwen3ASR.py tldw_Server_API/tests/Audio/test_qwen3_asr.py -f json -o /tmp/bandit_hf_cli_migration.json`
**Status:** Not Started

### Task 1: Update The Failing Test Expectation

**Files:**
- Modify: `tldw_Server_API/tests/Audio/test_qwen3_asr.py`

**Step 1: Write the failing test**

Change the assertion in `test_validate_model_path_missing_no_download` so it expects `hf download` in the error string instead of `huggingface-cli download`.

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Audio/test_qwen3_asr.py -k validate_model_path_missing_no_download -v`

Expected: FAIL because the runtime string still contains `huggingface-cli download`.

### Task 2: Update The Runtime Help Text

**Files:**
- Modify: `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Transcription_Qwen3ASR.py`

**Step 1: Write minimal implementation**

- Replace the module docstring examples from `huggingface-cli download` to `hf download`.
- Replace the two user-facing `BadRequestError` download hints from `huggingface-cli download` to `hf download`.

**Step 2: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Audio/test_qwen3_asr.py -k validate_model_path_missing_no_download -v`

Expected: PASS with the updated runtime guidance.

### Task 3: Sweep The Existing Docs Footprint

**Files:**
- Modify: `Docs/STT-TTS/TTS-SETUP-GUIDE.md`
- Modify: `Docs/STT-TTS/QWEN3_ASR_SETUP.md`
- Modify: `Docs/STT-TTS/VIBEVOICE_GETTING_STARTED.md`
- Modify: `Docs/STT-TTS/CHATTERBOX_SETUP.md`
- Modify: `Docs/STT-TTS/VIBEVOICE_INSTALLATION.md`
- Modify: `Docs/User_Guides/WebUI_Extension/PocketTTS_Voice_Cloning_Guide.md`
- Modify: `Docs/User_Guides/WebUI_Extension/Getting-Started-STT_and_TTS.md`
- Modify: `Docs/User_Guides/WebUI_Extension/TTS_Getting_Started.md`
- Modify: `tldw_Server_API/tests/TTS/adapters/README.md`
- Modify: `tldw_Server_API/app/core/TTS/TTS-README.md`
- Modify: `tldw_Server_API/app/core/TTS/TTS-DEPLOYMENT.md`

**Step 1: Update CLI references**

- Replace `huggingface-cli` prose references with `hf`.
- Replace `huggingface-cli download` examples with `hf download`.

**Step 2: Refresh install guidance**

- Where a touched section tells users to install CLI support, prefer `pip install -U "huggingface_hub"`.
- Where a touched section discusses gated/private repos, add or preserve concise `hf auth login` guidance.
- Leave Python package/import names unchanged.

**Step 3: Review wording**

Verify each touched section still reads naturally and does not mix old/new CLI names.

### Task 4: Verify The Migration

**Files:**
- Modify: none

**Step 1: Run targeted regression test**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Audio/test_qwen3_asr.py -k validate_model_path_missing_no_download -v`

**Step 2: Run repository grep**

Run: `rg -n "huggingface-cli|huggingface_cli" /Users/macbook-dev/Documents/GitHub/tldw_server2`

Expected: no matches.

**Step 3: Run Bandit on touched Python scope**

Run: `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Transcription_Qwen3ASR.py tldw_Server_API/tests/Audio/test_qwen3_asr.py -f json -o /tmp/bandit_hf_cli_migration.json`
