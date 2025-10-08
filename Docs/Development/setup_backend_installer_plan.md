# Setup Backend Installer – Execution Plan

This note captures how we will extend `install_manager.py` to provision both the
Python dependencies and the model files for each selectable backend. It builds
on the dependency matrix recorded in `setup_backend_dependency_matrix.md`.

## 1. Installer Responsibilities

For every backend selected in the setup wizard we need to:

1. Ensure the required Python packages (and extras) are installed.
2. Download or stage the model artifacts.
3. Record progress so the WebUI reflects installs, skips, and errors.
4. Keep the process idempotent – running the installer repeatedly should be safe.

The existing implementation already handles bullet 2 for most backends; this
work focuses on bullet 1 while preserving model download behaviour.

## 2. Package Installation Strategy

### Group dependencies upfront

- Build a dependency manifest keyed by backend (e.g. `faster_whisper`,
  `nemo_parakeet_standard`, `kokoro`).
- Each entry lists one or more `pip install` strings plus optional metadata such
  as "GPU only" or "requires system package".
- When processing the install plan we aggregate all package requirements into a
  set to avoid duplicate installs (e.g. multiple backends requiring `torch`).

### Installing with `pip`

- Use `sys.executable -m pip install --upgrade --no-input <pkg>` so we leverage
  the same interpreter running the server.
- Capture `stdout`/`stderr` and push truncated summaries into the status file on
  success/failure.
- Honour a new environment flag, `TLDW_SETUP_SKIP_PIP`, mirroring the existing
  `TLDW_SETUP_SKIP_DOWNLOADS`, to allow offline/disconnected setups to skip
  package installs gracefully.
- Allow operators to point pip at a custom index with
  `TLDW_SETUP_PIP_INDEX_URL` (useful for artifactory-style mirrors). The flag is
  optional; when unset we use the default PyPI index.
- Support an optional custom index URL via `TLDW_SETUP_PIP_INDEX_URL` to help on
  air-gapped networks.

### GPU vs. CPU packages

- Default to CPU wheels (no custom index) unless we detect a CUDA runtime via
  `torch.cuda.is_available()` or environment hints (`TLDW_SETUP_FORCE_CUDA`).
- Where upstream libraries offer architecture-specific wheels (e.g.
  `onnxruntime-gpu`), install the GPU variant only when CUDA is available;
  otherwise fall back to `onnxruntime`.
- Document the expectation that advanced users can override packages by
  pre-installing their desired builds before running the wizard.

### Idempotency & validation

- Before invoking `pip`, probe whether the package is already importable. If it
  is and we are not forced to upgrade, mark the step as `skipped` with a note.
- For packages that expose a `__version__`, log it in the status entry to aid
  troubleshooting.
- Surface actionable errors (e.g. missing build toolchain) back to the WebUI via
  the status panel.

## 3. Execution Order

1. **Aggregate dependencies** from the plan (STT → TTS → embeddings) and run a
   consolidated `pip` install phase. Failures in this phase should mark the
   relevant backend as failed and continue processing others.
2. **Download models** using the existing functions. Model downloads are skipped
   when `TLDW_SETUP_SKIP_DOWNLOADS` is set or when dependency checks fail.
3. **Finalize status** – if all steps for a backend finish, mark it `completed`.
   If either dependency install or model download fails, mark as `failed` with
   details.

## 4. Logging & WebUI Surface

- Extend `InstallationStatus.step()` usage to include sub-steps such as
  `deps:faster_whisper` and `models:faster_whisper`. The wizard will display
  these entries, giving users immediate visibility into which phase failed.
- When skipping due to offline mode or pre-existing installs, set status to
  `skipped` with a concise explanation.

## 5. Future Considerations

- Some backends (e.g. Higgs) require repo-based installs. We'll encapsulate
  these as `pip` tasks that point to git URLs, noting the additional runtime.
- System-level prerequisites (CUDA toolkit, espeak-ng, ffmpeg) cannot be managed
  by `pip`; the wizard should surface reminders when we detect missing shared
  libraries during import checks.
- Once the package installer is in place we can offer a "verify" button in the
  WebUI to re-run dependency checks without downloading models again.

With this design in place we can proceed to implement the dependency installer
and expand test coverage to validate success, failure, and skip paths.
