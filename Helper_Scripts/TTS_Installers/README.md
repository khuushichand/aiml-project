TTS Backend Installers

Standalone scripts to install assets and dependencies for individual TTS providers.

Run from the project root with your Python environment activated (e.g., venv).

Examples:
- Kokoro (v1.0 ONNX + voices):
  python Helper_Scripts/TTS_Installers/install_tts_kokoro.py

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

Notes
- Scripts use tldw’s internal installer utilities where possible (pip + HF snapshots).
- Downloads respect environment flags:
  - Set TLDW_SETUP_SKIP_DOWNLOADS=1 to skip model downloads.
  - Set TLDW_SETUP_SKIP_PIP=1 to skip pip installs.
- Kokoro requires eSpeak NG (system library). The script detects it and prints platform-specific guidance if missing.

