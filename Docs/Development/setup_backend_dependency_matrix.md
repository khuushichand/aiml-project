# Setup Wizard Backend Dependency Matrix

This reference captures the Python packages, model assets, and notable system
prerequisites required for each backend that the first-time setup wizard can
install. It will act as the source of truth while we extend the installer to
bootstrap both dependencies and model weights automatically.

## Speech-to-Text Backends

| Backend option | Core Python packages | Model assets pulled today | Extra notes |
| --- | --- | --- | --- |
| `faster_whisper` | `faster-whisper` (brings `ctranslate2`, `onnxruntime`), optional `torch` when using GPU | Whisper checkpoints via `WhisperModel` helper | Requires working `ffmpeg`. GPU acceleration needs CUDA build of `faster-whisper` or `ctranslate2` wheels. |
| `qwen2_audio` | `transformers>=4.41`, `torch` (`torchvision` for pretrained configs), `accelerate`, `soundfile`, `sentencepiece`, `numpy` | `Qwen/Qwen2-Audio-7B-Instruct` (processor + model) | Benefits from CUDA; CPU mode is extremely slow. Ensure libsndfile is available for `soundfile`. |
| `nemo_parakeet_standard` | `nemo_toolkit[asr]>=1.23`, `torch>=2.1`, `pytorch-lightning`, `sentencepiece`, `omegaconf`, `soundfile`, `librosa` | `nvidia/parakeet-tdt-0.6b-v3` via NeMo downloader | Strongly GPU-oriented. Needs CUDA-enabled PyTorch and optional `apex`. Downloads to `NEMO_CACHE_DIR`. |
| `nemo_parakeet_onnx` | `onnxruntime-gpu` (or `onnxruntime` for CPU), `huggingface_hub`, `soundfile`, `librosa`, `numpy` | ONNX weights from `nvidia/parakeet-tdt-0.6b-v3` snapshot | Requires preprocessing libs (`librosa`). GPU ONNX runtime should match CUDA version. |
| `nemo_parakeet_mlx` | Apple MLX stack: `mlx`, `mlx-lm`, `numpy` | MLX-format Parakeet checkpoints (expected inside `models/nemo`) | macOS/Apple Silicon only. Relies on MLX Python wheels (`pip install mlx mlx-lm`). |
| `nemo_canary` | `nemo_toolkit[asr]`, `torch`, `pytorch-lightning`, `sentencepiece`, `omegaconf`, `soundfile`, `librosa` | `nvidia/canary-1b-v2` via NeMo downloader | Same CUDA expectations as Parakeet standard. |

## Text-to-Speech Backends

| Backend option | Core Python packages | Model assets pulled today | Extra notes |
| --- | --- | --- | --- |
| `kokoro` (ONNX) | `kokoro-onnx`, `onnxruntime`/`onnxruntime-gpu`, `phonemizer`, `espeak-phonemizer`, `numpy` | `kokoro-82m/kokoro-v0_19.onnx`, `voices.json` | Requires eSpeak phoneme library (`espeak-ng` system package) when `phonemizer` looks for shared libs. |
| `kokoro` (PyTorch) | `kokoro`, `torch`, optional `torchaudio` | Same as above plus PyTorch checkpoints (`kokoro.pt`, `config.json`) | PyTorch build must match platform (CUDA/MPS/CPU). |
| `dia` | `transformers>=4.38`, `torch`, `accelerate`, `safetensors`, `sentencepiece`, `numpy`, `soundfile` | `nari-labs/dia` via Hugging Face | GPU strongly recommended. Large (1.6B) model; ensure adequate VRAM. |
| `higgs` | `boson-multimodal` (from https://github.com/boson-ai/higgs-audio), `torch`, `torchaudio`, `soundfile`, `hydra-core`, `sentencepiece`, `numpy` | `bosonai/higgs-audio-v2-generation-3B-base`, `bosonai/higgs-audio-v2-tokenizer` | Installation currently requires cloning repo + `pip install -e`. GPU recommended; CPU fallback slow. |
| `vibevoice` | `git+https://github.com/microsoft/VibeVoice.git` (includes deps), `torch>=2.1`, `torchaudio`, `numpy`, `sentencepiece`, `soundfile` | `microsoft/VibeVoice-1.5B` and/or `WestZhang/VibeVoice-Large-pt` | Installer already runs `pip install` for main package. Needs FlashAttention 2 or fallback to SDPA; GPU with ≥16GB VRAM advised. |

## Embedding Model Downloads

| Selection | Core Python packages | Model assets | Extra notes |
| --- | --- | --- | --- |
| Hugging Face presets (e.g., `sentence-transformers/all-MiniLM-L6-v2`) | `sentence-transformers`, `torch`, `numpy`, `scikit-learn`, `tokenizers`, `huggingface_hub` | Chosen model snapshot via `snapshot_download` | CPU okay; GPU acceleration optional. For ONNX-flavoured models also need `onnxruntime`. |
| Custom Hugging Face IDs | Same as above (depends on architecture) | User-specified repo snapshots | Warn when `trust_remote_code=True` is needed; append to trusted list automatically. |
| ONNX embeddings (future) | `onnxruntime`, `numpy`, optional `optimum` | Model-specific ONNX bundles | Determine provider-specific extras (e.g., MiniLM onnx). |

## Shared System Requirements

- **FFmpeg** – Required for all media ingestion/STT pipelines (already a project-wide prerequisite).
- **CUDA Toolkit** – Needed for GPU-accelerated PyTorch/ONNX runtimes. Ensure installer can detect GPU versus CPU environments.
- **espeak-ng / phonemizer backends** – Necessary for Kokoro phoneme generation when using ONNX backend.
- **libsndfile** – Required by `soundfile` for audio IO (Qwen2Audio, Dia, Higgs, VibeVoice, Nemo ONNX).
- **Git** – Already assumed present (VibeVoice pip install uses git+https URLs).
- **Installer flags** – `TLDW_SETUP_SKIP_PIP=1` skips package installation; `TLDW_SETUP_SKIP_DOWNLOADS=1` skips model downloads; `TLDW_SETUP_PIP_INDEX_URL=<url>` points pip to a mirror; `TLDW_INSTALL_STATE_DIR=/path` forces the status file into a writable location.

This matrix will drive the installer updates in the next planning steps: we’ll
determine which dependencies must be installed automatically, how to pick CPU
vs. GPU wheels, and what fallbacks or user guidance we need when prerequisites
are missing.
