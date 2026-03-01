# GPU/STT Add-on

Use this add-on when your selected profile needs GPU acceleration for speech-to-text workflows.
This is not a standalone setup guide. Complete one base profile first, then apply this add-on.

## Prerequisites

- A supported NVIDIA GPU
- Current NVIDIA drivers and CUDA runtime
- `nvidia-smi` available on host
- Container toolkit/runtime support for GPU pass-through (if using Docker)

## Install

- Install NVIDIA drivers and validate with `nvidia-smi`.
- Ensure your base profile is already working before enabling GPU/STT.
- Add any required STT model/provider configuration keys in `.env` or config.

## Run

- Restart your chosen deployment profile after enabling GPU configuration.
- If containerized, ensure GPU runtime flags are active for the API container.

## Verify

```bash
nvidia-smi
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/docs > /dev/null && echo "docs-ok"
```

Confirm STT path behavior in logs during a transcription request.

## Troubleshoot

- If GPU is not detected, verify host driver/CUDA installation first.
- If container cannot access GPU, verify NVIDIA container runtime/toolkit setup.
- If STT falls back to CPU unexpectedly, review provider/model config and startup logs.
