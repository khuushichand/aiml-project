Custom Vocabulary for STT
=========================

Overview
--------
This feature lets you bias transcription and correct common mishearings without touching model tokenizers. It works in two ways:

- Whisper prompt bias: Injects an `initial_prompt` built from your domain terms to guide recognition.
- Post-processing replacements: Applies whole-word text replacements to the transcribed text (all providers).

Supported paths
---------------
- Faster-Whisper (batch): initial_prompt + post-replacements
- Faster-Whisper (streaming): initial_prompt + post-replacements
- Nemo Parakeet/Canary (batch/streaming): post-replacements
- External providers (OpenAI-compatible): post-replacements

Configuration
-------------
Edit `tldw_Server_API/Config_Files/config.txt` under `[STT-Settings]`:

```
# Path to a file with domain terms (one per line) or JSON list
custom_vocab_terms_file = ./Config_Files/custom_vocab/terms.txt

# Path to a JSON mapping of misheard->correct (or text lines "wrong=correct")
custom_vocab_replacements_file = ./Config_Files/custom_vocab/replacements.json

# Toggle prompt and replacements
custom_vocab_initial_prompt_enable = True
custom_vocab_postprocess_enable = True

# Template for the Whisper initial prompt ("{terms}" is replaced by a comma-separated list)
custom_vocab_prompt_template = Domain terms: {terms}.

# If True, replacements are case-sensitive
custom_vocab_case_sensitive = False
```

Sample files
------------
- `Config_Files/custom_vocab/terms.sample.txt`
  - One term per line
  - Example: `Acme\nPhasor\nIoT Sensor Hub\nXJ-12\n`

- `Config_Files/custom_vocab/replacements.sample.json`
  - JSON object mapping common mishearings to the desired text
  - Example: `{ "phase or": "phasor", "XJ12": "XJ-12", "IOT": "IoT" }`

Behavior details
----------------
- The terms list is capped (64 items) to keep prompts compact.
- Replacements are applied with whole-word matching and case-insensitive by default.
- Do NOT edit model vocabulary/tokenizer files (e.g., Parakeet `vocab.json`). This feature is prompt + post-processing only.

Where it lives
--------------
- Helper: `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Custom_Vocabulary.py`
- Whisper (batch): `Audio_Transcription_Lib.py`
- Whisper (streaming): `Audio_Streaming_Unified.py`
- API post-processing: `api/v1/endpoints/audio.py`

Quick test
----------
1. Place your files:
   - `Config_Files/custom_vocab/terms.txt`
   - `Config_Files/custom_vocab/replacements.json`
2. Update config keys above and restart the server.
3. Transcribe an audio sample and confirm domain terms are preserved and replacements applied.

Troubleshooting
---------------
- No effect on Whisper? Ensure `custom_vocab_initial_prompt_enable=True` and the terms file path is correct.
- Replacements not applying? Check `custom_vocab_postprocess_enable=True` and that keys match whole words (or set case-sensitive behavior).
