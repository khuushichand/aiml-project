PRD — Voice‑to‑Voice Chat (Full‑screen Playground + Chat Sidebar)

  Owner: You
  Date: 2026‑01‑24
  Status: Draft

  ———

  ## 1) Problem & Goal

  Users want hands‑free, voice‑to‑voice conversations in both the full‑screen chat playground and the chat sidebar. They should be able to configure server‑side STT + TTS, speak naturally, auto‑send on silence or
  trigger phrase, and receive spoken responses while preserving the text chat transcript.

  ———

  ## 2) Goals

  - Voice‑to‑voice loop with minimal friction (listen → auto‑send → reply spoken).
  - Dedicated LLM model for voice chat (separate from standard chat model).
  - Streaming TTS playback when possible; fallback to generate‑then‑play.
  - Available in both:
      - Full‑screen Playground
      - Chat Sidebar (sidepanel UI)
  - Uses existing STT/TTS settings and server capabilities.

  ———

  ## 3) Non‑Goals

  - Replacing the standard text chat flow.
  - Adding new server endpoints (use existing /api/v1/audio/chat/stream).
  - Voice activity detection on the client (server VAD preferred).
  - UI/UX re‑design of all chat surfaces.

  ———

  ## 4) Users & Use Cases

  Primary user: Power user multitasking, prefers voice input/output.
  Use cases:

  - Hands‑free brainstorming or Q&A.
  - Voice dictation with immediate spoken response.
  - Low‑latency conversational mode in the sidebar.

  ———

  ## 5) UX Summary

  ### Entry Points

  - Toggle “Voice Chat” in:
      - src/components/Option/Playground/PlaygroundForm.tsx
      - src/components/Sidepanel/Chat/form.tsx

  ### Core Flow

  1. User enables Voice Chat.
  2. Microphone streams to server via WS.
  3. Server VAD commits turn (or trigger phrase).
  4. User transcript posted into chat.
  5. Assistant response streamed as text and audio.
  6. Audio plays automatically; chat transcript persists.

  ### Visual States

  - Listening (mic active)
  - Thinking (waiting for LLM)
  - Speaking (TTS playing)
  - Error (mic denied, WS down, quota exceeded)

  ———

  ## 6) Functional Requirements

  ### Voice Chat Mode

  - Toggle on/off.
  - Dedicated model selection (voice‑specific).
  - Supports both full‑screen + sidebar.
  - Works across normal chat and voice mode without losing text history.

  ### Dictation + Auto Send

  - Auto‑send when:
      - Silence duration X ms (maps to server VAD config).
      - Trigger phrase detected (client‑side string check).
  - Strip trigger phrase from final message.

  ### Streaming

  - Preferred: true streaming TTS playback from WS binary chunks.
  - Fallback: generate full audio then play when streaming unavailable.

  ### Text Record

  - User’s transcript saved as normal user chat message.
  - Assistant response saved as normal assistant message.
  - Streaming text updates live while audio plays.

  ———

  ## 7) Technical Approach (Client)

  Client shape (required):

  New hook: useVoiceChatStream

  - Opens WS (UI or background port; see Open Questions).
  - Sends config:

    {
      "type": "config",
      "stt": {...},
      "llm": {...},
      "tts": {...}
    }
  - STT config uses existing settings:
      - speechToTextLanguage, sttModel, segmentation, etc. from SSTSettings.
  - TTS config uses existing settings:
      - provider/voice/model/speed from TTSModeSettings.
  - VAD config:
      - stt.enable_vad = true
      - stt.min_silence_ms = pauseMs
  - Streams mic PCM with useMicStream as base64:

    { "type":"audio", "data": "<base64>" }
  - Handles incoming frames:
      - JSON: partial, full_transcript, llm_delta, llm_message, tts_start, tts_done
      - Binary: TTS audio chunks (play now or buffer)

  UI integration

  - Toggle in PlaygroundForm + Sidepanel Chat form.
  - On full_transcript: insert user message into chat store.
  - On llm_delta: update active assistant message streaming content.
  - On audio: auto‑play streaming TTS.

  ———

  ## 8) Server Dependencies

  Existing endpoint:

  - WS /api/v1/audio/chat/stream
    Located in: ../tldw_server2/tldw_Server_API/app/api/v1/endpoints/audio.py

  Capabilities already supported:

  - VAD auto‑commit
  - Streaming LLM deltas
  - Streaming TTS audio frames (binary)
  - Configurable STT/LLM/TTS via initial config frame

  ———

  ## 9) Settings & Configuration

  Add new voice chat settings (stored in local storage or settings registry):

  - voiceChatEnabled (bool)
  - voiceChatModel (string, dedicated)
  - voiceChatPauseMs (number)
  - voiceChatTriggerPhrases (array of strings)
  - voiceChatAutoResume (bool)
  - voiceChatBargeIn (bool)
  - voiceChatTtsMode (“stream” | “full”)

  Reuse existing:

  - STT settings from SSTSettings
  - TTS settings from TTSModeSettings

  ———

  ## 10) Error Handling

  - Mic permission denied → user‑friendly toast.
  - WS errors / quota exceeded → display message + auto‑disable voice mode.
  - No server audio support → disable toggle + show reason.

  ———

  ## 11) Telemetry / Metrics

  (If telemetry exists)

  - Voice chat session start/stop
  - WS connection failures
  - Average response latency (STT → LLM → TTS)
  - Auto‑commit rate vs manual commit rate

  ———

  ## 12) Acceptance Criteria

  - Voice chat works in full‑screen playground and sidebar.
  - Dedicated model selection used in voice mode.
  - Silence timeout auto‑sends message.
  - Trigger phrase auto‑sends message and is removed.
  - Assistant replies stream as text + audio.
  - Chat transcript remains accurate and persistent.
  - Fallback to full‑audio playback works when streaming fails.

  ———

  ## 13) Phases

  Phase 1: MVP

  - Voice toggle in both UIs
  - WS audio chat stream
  - Auto‑commit by silence
  - Streaming audio playback
  - Text transcript + assistant streaming text

  Phase 2: Enhancements

  - Trigger phrases config
  - Barge‑in support
  - Dedicated UI panel with live waveform/levels
  - Optional push‑to‑talk mode

  ———

  ## 14) Open Questions

  1. WS connection location: UI directly or via background port? - UI directly
  2. Should voice chat respect normal RAG/tool settings or force minimal chat? - force minimal chat
  3. Should trigger phrases be localizable or fixed? - fixed
  4. Should TTS auto‑play still respect the global “auto‑play” setting? - Yes
