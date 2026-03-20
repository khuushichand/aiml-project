# Speech-To-Text Documentation


## To Do
Switch to mobiusLabs model: https://github.com/SYSTRAN/faster-whisper/issues/1030
https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo
https://huggingface.co/spaces/hf-audio/open_asr_leaderboard
https://github.com/EvolvingLMMs-Lab/Aero-1
https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2
https://github.com/cxyfer/GeminiASR
https://github.com/taresh18/conversify
https://github.com/kyutai-labs/delayed-streams-modeling/
https://www.reddit.com/r/LocalLLaMA/comments/1lgv0y9/help_me_build_a_good_tts_llm_stt_stack/
https://huggingface.co/Banafo/Kroko-ASR
https://github.com/travisvn/chatterbox-tts-api/
https://huggingface.co/livekit/turn-detector
https://github.com/livekit/agents/tree/main/livekit-plugins/livekit-plugins-turn-detector
https://github.com/senstella/parakeet-mlx
https://github.com/zai-org/GLM-ASR
https://github.com/ibm-granite/granite-speech-models?tab=readme-ov-file
https://github.com/altunenes/parakeet-rs?tab=readme-ov-file

Latice
    https://github.com/LATICE-AI/inference
    https://github.com/LATICE-AI
Benchmark
    https://github.com/dnhkng/GLaDOS/blob/main/src/glados/ASR/asr.py
    https://github.com/SYSTRAN/faster-whisper/blob/master/tests/test_transcribe.py


API
    https://github.com/heimoshuiyu/whisper-fastapi


Review potential use of quantized STT Models:
    * https://opennmt.net/CTranslate2/quantization.html

## Overview
- **Usage**
    1. If transcribing english audio, use [Whisper-Turbo v3](https://huggingface.co/openai/whisper-large-v3-turbo)
       * Model used in this project: [Deepdml/faster-whisper-large-v3-turbo-ct2](https://huggingface.co/deepdml/faster-whisper-large-v3-turbo-ct2)
    2. If transcribing non-english audio, use [Whisper-Large distil v3](https://huggingface.co/distil-whisper/distil-large-v3)
    3. If that fails, then use [Whisper-Large v3](https://huggingface.co/openai/whisper-large-v3) -> Whisper-Large v2
- **Voice-Audio-Detection(VAD)**
    - Unified WS path now supports Silero-based turn detection with auto-commit.
    - Server-clamped tunables: `vad_threshold` [0.1..0.9] (default 0.5), `min_silence_ms` [150..1500] (default 250), `turn_stop_secs` [0.1..0.75] (default 0.2), `min_utterance_secs` guard (default 0.4).
    - Fail-open: if Silero cannot load (e.g., torch hub disabled), streaming continues without auto-commit and logs once.
    - Client guidance: keep pauses ≥ configured `turn_stop_secs` to trigger finals; still allowed to send manual `{type:"commit"}`.
    - Runtime Silero VAD integration for streaming turn detection loads the Python model via `torch.hub.load("snakers4/silero-vad", "silero_vad", ...)` or a local checkout under `models/`, not directly from any ONNX weights file.
    - Offline diarization VAD can optionally use a local Silero ONNX model via onnxruntime when `[Diarization].vad_backend=onnx_silero` in `Config_Files/config.txt`; when unset or set to `silero_hub` it uses the PyTorch Silero repo via torch.hub.
    - Weights: faster-whisper already ships `silero_vad_v6.onnx`; use `python Helper_Scripts/install_silero_vad_weights.py` if you want a copy under `models/` (no downloads; it only copies from the existing package assets). This helper is optional; current streaming VAD path does not consume the copied ONNX file directly, while the ONNX diarization backend looks at `[Diarization].onnx_model_path`.
- **Speaker-Diarization**
    - Use Pyannote to determine speaker boundaries in audio files.
    - This feature is currently either implemented poorly or it's not that great at diarization.
- **Transcription**
    - Use Faster Whisper to transcribe audio files. Uses Whisper models currently
    - Faster_whisper is a re-implementation of whisper using via CTranslate2(an inference engine for Transformers models)
          - Supports both CPU and GPU + Quantization
          - https://opennmt.net/CTranslate2/quantization.html

- **Backend**
  - faster_whisper
  - Model: `WhisperModel` (User-selectable)

- **Whisper Models**
  - https://huggingface.co/distil-whisper/distil-large-v3

### Speech-to-Text
- **Flow**
    1. Convert an input file (like .m4a or .mp4) to .wav via `convert_to_wav(...)`.
    2. Transcribe with `speech_to_text(...)`, which uses Faster Whisper to generate time-stamped text segments.
    3. (Optional)Diarize the same .wav with `audio_diarization(...)`, which uses pyannote to determine speaker boundaries.
    4. (Optional)Combine them in `combine_transcription_and_diarization(...)` to match the transcription segments to the speakers based on time.
- **Key Libraries:**
    - [Faster Whisper](https://github.com/SYSTRAN/faster-whisper) (faster_whisper.WhisperModel) for transcription.
    - [Pyannote](https://github.com/pyannote/pyannote-audio) (pyannote.audio.pipelines.speaker_diarization) for speaker diarization.
    - [FFmpeg](https://www.ffmpeg.org/) (via subprocess or os.system) to convert audio to the desired WAV format.
    - [PyAudio](https://people.csail.mit.edu/hubert/pyaudio/) (for optional live recording).

#### Canonical STT entrypoints

- `speech_to_text(...)` (in `Audio_Transcription_Lib.py`)
  - File or NumPy input; returns a list of segment dicts (or `(segments, language)` when `return_language=True`).
  - Used by media ingestion, offline workers, and any code that needs structured timestamps or caching on disk.
- `transcribe_audio(...)` (in `Audio_Transcription_Lib.py`)
  - NumPy waveform input; routes to the appropriate provider and returns a single transcript string.
  - Used by `/audio/transcriptions`, speech-chat, and streaming sinks when they already have in-memory audio.
  - May return provider-specific error sentinels like `"[Transcription error] ..."`, which callers must detect with `is_transcription_error_message(...)` and convert into structured errors instead of treating as user speech.


### Benchmarks
- https://github.com/Picovoice/speech-to-text-benchmark
https://huggingface.co/spaces/hf-audio/open_asr_leaderboard



### Link Dump:
STT
    https://github.com/KoljaB/RealtimeSTT
    https://github.com/southbridgeai/offmute
    https://github.com/flatmax/speech-to-text
    https://github.com/collabora/WhisperLive
    https://github.com/fedirz/faster-whisper-server
    https://github.com/ufal/whisper_streaming
    MoonShine
        https://github.com/usefulsensors/moonshine
        https://github.com/huggingface/transformers.js-examples/tree/main/moonshine-web
        https://huggingface.co/onnx-community/moonshine-base-ONNX
    https://github.com/FreedomIntelligence/Soundwave
        https://arxiv.org/abs/2502.12900
https://github.com/psdwizzard/MeetingBuddy
https://github.com/mehtabmahir/easy-whisper-ui
