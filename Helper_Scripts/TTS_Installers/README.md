TTS Backend Installers

Standalone scripts to install assets and dependencies for individual TTS providers.

Run from the project root with your Python environment activated (e.g., venv).

Examples:
- Kokoro (v1.0 ONNX + voices):
  python Helper_Scripts/TTS_Installers/install_tts_kokoro.py
  # Overwrite existing assets:
  # python Helper_Scripts/TTS_Installers/install_tts_kokoro.py --force

- NeuTTS (deps + optional prefetch):
  python Helper_Scripts/TTS_Installers/install_tts_neutts.py --prefetch

- Dia (deps + model snapshot):
  python Helper_Scripts/TTS_Installers/install_tts_dia.py

- Higgs (deps + model/tokenizer snapshots):
  python Helper_Scripts/TTS_Installers/install_tts_higgs.py

- VibeVoice (deps + 1.5B snapshot):
  python Helper_Scripts/TTS_Installers/install_tts_vibevoice.py --variant 1.5B

- IndexTTS2 (deps + create checkpoints directory):
  python Helper_Scripts/TTS_Installers/install_tts_index_tts2.py

- Chatterbox (deps only):
  python Helper_Scripts/TTS_Installers/install_tts_chatterbox.py

- Supertonic2 (assets + config snippet):
  python Helper_Scripts/TTS_Installers/install_tts_supertonic2.py
  # Skip config updates:
  # python Helper_Scripts/TTS_Installers/install_tts_supertonic2.py --no-config-update

Notes
- Scripts use tldw’s internal installer utilities where possible (pip + HF snapshots).
- Downloads respect environment flags:
  - Set TLDW_SETUP_SKIP_DOWNLOADS=1 to skip model downloads.
  - Set TLDW_SETUP_SKIP_PIP=1 to skip pip installs.
  - Set TLDW_SETUP_FORCE_DOWNLOADS=1 (or pass --force where available) to overwrite existing assets.
- Kokoro requires eSpeak NG (system library). The script detects it and prints platform-specific guidance if missing.

Asset-only helper for Kokoro (no pip installs):
  python Helper_Scripts/download_kokoro_assets.py \
    --repo-id onnx-community/Kokoro-82M-v1.0-ONNX-timestamped \
    --model-path models/kokoro/onnx/model.onnx \
    --voices-dir models/kokoro/voices
