# Chat Voice Conversation Transport Design

Date: 2026-03-25
Status: Approved for planning
Owner: Codex brainstorming session

## Summary

Investigate and harden the `/chat` voice-conversation path used by the WebUI playground and the extension sidepanel so it behaves as one honest, shared feature: user speech is transcribed, the turn is submitted automatically, assistant text streams into chat, and assistant audio plays back automatically.

The reported symptom is:

- standalone STT and TTS work on the Speech/STT-TTS page
- `/chat` voice conversation can transcribe the user but then appear to do nothing

The approved direction is:

- keep the existing backend streaming transport centered on `/api/v1/audio/chat/stream`
- do not treat standalone STT + standalone TTS as sufficient proof that `/chat` voice conversation is available
- add one shared availability and preflight layer for both chat surfaces
- make voice-chat TTS resolution explicit instead of relying on opaque fallback behavior
- preserve broad legacy audio capability reporting where the repo still depends on it

## Problem

The current `/chat` voice-conversation implementation is a stricter feature than the standalone Speech page, but the client-side capability model and startup behavior do not fully reflect that.

Today, the shared chat voice flow depends on:

- a WebSocket transport to `/api/v1/audio/chat/stream`
- a valid chat model and provider resolution
- a server-usable TTS configuration
- streaming playback of returned audio frames

But the surrounding UI still mixes together multiple meanings of "audio support":

- standalone STT support
- standalone TTS support
- generic audio health
- true voice-conversation transport support

That creates a plausible failure mode where the feature looks available, the transcript arrives, and then the combined voice loop stalls or fails without a clear reason.

## User-Validated Success Criteria

For both the WebUI `/chat` surface and the extension sidepanel chat surface:

- the user can enable voice conversation
- speaking starts a turn without requiring manual send
- the user transcript is added to chat
- assistant text streams into the active assistant message
- assistant audio plays automatically
- failure states are explicit and actionable rather than silent

## Goals

- Make `/chat` voice conversation work across both chat surfaces together, not one at a time.
- Keep the existing `/api/v1/audio/chat/stream` backend path as the primary transport.
- Separate broad audio capability from strict voice-conversation transport capability.
- Unify the availability rules for:
  - WebUI playground chat
  - extension sidepanel chat
- Add shared preflight validation before opening the voice-chat session.
- Make voice-chat startup and runtime failures user-visible and diagnosable.
- Preserve chat transcript integrity when a voice turn succeeds or fails mid-stream.

## Non-Goals

- Add a new backend endpoint for this fix.
- Replace `/api/v1/audio/chat/stream` with a stitched REST fallback in this iteration.
- Redesign the standalone Speech/STT-TTS page.
- Redefine every existing usage of `hasVoiceChat` across the entire app in one pass.
- Bind voice conversation to the generic message-TTS autoplay preference.

## Current State

### Shared Voice Transport

The current voice-conversation client already exists in the shared UI package:

- [`useVoiceChatStream.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useVoiceChatStream.tsx)

It:

- opens a WebSocket to `/api/v1/audio/chat/stream`
- streams microphone audio
- sends a `config` frame with STT, LLM, and TTS settings
- creates chat messages from `full_transcript`, `llm_delta`, and `llm_message`
- plays returned TTS audio chunks with:
  - [`useStreamingAudioPlayer.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useStreamingAudioPlayer.tsx)

### Chat Surface Integration

Both surfaces already consume the shared voice stream hook:

- WebUI playground:
  - [`PlaygroundForm.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx)
- extension/chat sidepanel:
  - [`form.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Sidepanel/Chat/form.tsx)

But their availability checks are not identical:

- the playground path is closer to strict voice-chat transport gating
- the sidepanel still falls back to looser generic audio capability in places

### Capability Detection

Current capability inference lives in:

- [`server-capabilities.ts`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/services/tldw/server-capabilities.ts)
- [`useTldwAudioStatus.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useTldwAudioStatus.tsx)

Important current behavior:

- `hasStt` may be true if STT routes exist
- `hasTts` may be true if TTS routes exist
- `hasVoiceChat` is currently inferred from either:
  - `/api/v1/audio/chat/stream`
  - or `hasStt && hasTts`

This is useful for broad audio compatibility, but it is too loose for the `/chat` voice-conversation toggle.

### TTS Resolution Risk

Voice conversation currently reads the same global TTS settings used elsewhere:

- provider
- model
- voice
- format
- speed

Relevant code:

- [`useVoiceChatStream.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useVoiceChatStream.tsx)
- [`TTSModeSettings.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Settings/TTSModeSettings.tsx)

One risk area is that `ttsProvider="browser"` is a valid standalone TTS setting elsewhere in the product, but `/chat` voice conversation still requires a server-side TTS result on the voice-chat transport. The current hook does not make that distinction explicit enough.

### Backend Status

The backend streaming transport is already implemented and documented:

- [`Docs/API/Audio_Chat.md`](/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/API/Audio_Chat.md)
- [`audio_streaming.py`](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py)

Relevant test coverage already passes locally for the backend streaming route:

- [`test_ws_audio_chat_stream.py`](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/tests/Audio/test_ws_audio_chat_stream.py)

This means the current investigation should focus first on transport gating, startup validation, and shared surface behavior rather than assuming the core backend route is fundamentally broken.

## Root Cause Hypothesis

The precise production failure has not been reproduced yet, but the current code supports a strong root-cause hypothesis:

### 1. The UI can over-advertise voice conversation

The client may treat "STT + TTS available" as meaning "voice conversation available," even though `/chat` voice conversation requires the actual streaming route and a valid combined config.

### 2. Voice-chat startup preflight is under-specified

The hook does not centralize all required checks before opening the transport:

- server URL present
- auth token/API key present
- selected chat model present
- provider resolution succeeds
- effective voice-chat TTS configuration is valid for server-side synthesis

### 3. TTS configuration is honest in some surfaces but ambiguous in voice chat

The standalone TTS feature can legitimately use browser-local playback semantics. The voice-conversation transport cannot. If those settings are reused without explicit normalization, the voice loop can fail or behave opaquely after transcription.

## Proposed Design

### 1. Introduce a Strict Voice-Conversation Transport Capability

Do not redefine the current broad `hasVoiceChat` meaning in place.

Instead, add a stricter capability specifically for `/chat` voice conversation. Recommended name:

- `hasVoiceConversationTransport`

Definition:

- true only when `/api/v1/audio/chat/stream` is advertised

Keep existing `hasVoiceChat` semantics if other callers still depend on the broader "voice-like audio support" meaning.

This avoids solving the `/chat` issue by silently breaking legacy assumptions elsewhere in the app.

Conservative capability rule:

- strict voice-conversation transport capability must not be inferred solely from the optimistic bundled fallback OpenAPI spec
- if capability discovery falls back to the bundled local spec instead of an authoritative server spec, treat strict transport support as unknown or unavailable for `/chat` voice conversation
- do not let fallback discovery reintroduce the same over-advertising problem this design is intended to remove

### 2. Add One Shared Voice-Conversation Availability Resolver

Create a shared helper or hook in the UI package that both chat surfaces must use.

Responsibilities:

- combine connection readiness
- combine strict transport capability
- combine generic audio health where still relevant
- combine voice-chat preflight results
- return a structured availability result rather than a single boolean

Recommended output shape:

```ts
type VoiceConversationAvailability = {
  available: boolean
  reason:
    | "ok"
    | "transport_missing"
    | "not_connected"
    | "auth_missing"
    | "model_missing"
    | "tts_config_missing"
    | "tts_provider_unsupported"
    | "audio_unhealthy"
    | "unknown"
  message: string | null
}
```

Both of these files should consume the same resolver:

- [`PlaygroundForm.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx)
- [`form.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Sidepanel/Chat/form.tsx)

This prevents the current surface drift where one chat surface is stricter than the other.

### 3. Add Explicit Voice-Chat Preflight in `useVoiceChatStream`

Before opening the WebSocket, the hook should validate and normalize all required startup inputs.

Required checks:

- configured server URL exists
- auth token or API key exists for the current auth mode
- if a client-selected model is present, it resolves to a usable provider path
- if no client-selected model is present, the client may intentionally omit `llm.model` and defer to backend defaults rather than hard-failing preflight
- the effective voice-chat TTS config resolves to a server-usable provider/model/voice/format combination

If any preflight step fails:

- do not open the WebSocket
- surface a clear error to the caller
- keep the reason stable enough for tests and UX copy

### 4. Resolve Voice-Chat TTS Config Explicitly

The design should not simply reject `ttsProvider="browser"` as invalid in all cases, because the current hook effectively tries to synthesize server audio using the tldw model/voice defaults when browser is selected.

Instead, define one explicit normalization step for voice conversation:

```ts
type ResolvedVoiceChatTtsConfig = {
  provider?: string
  model: string
  voice: string
  speed: number
  format: string
}
```

Behavior:

- `tldw` provider:
  - require a valid tldw model and voice
- `openai` provider:
  - require a valid OpenAI TTS model and voice
- `elevenlabs` provider:
  - require a valid ElevenLabs model and voice id
- `browser` provider:
  - do not use browser voice names or browser-local synthesis for `/chat` voice conversation
  - resolve through the existing tldw server TTS settings only:
    - `tldwTtsModel`
    - `tldwTtsVoice`
    - `tldwTtsSpeed`
    - `tldwTtsResponseFormat`
  - infer the provider from `tldwTtsModel` using the existing provider inference and server provider-key normalization helpers
  - if provider inference fails, allow `provider` to remain omitted, but still require non-empty model and voice so the backend can resolve from the model alias
  - otherwise fail with a clear reason such as "Voice conversation needs a server TTS model and voice"

This means the source of truth for the browser-provider fallback is explicit:

- browser provider remains valid for standalone/local playback elsewhere
- voice conversation reuses the existing server-oriented tldw TTS settings as its fallback profile
- the browser-selected voice itself is ignored for voice conversation

This preserves current product flexibility without pretending the browser-local TTS mode is itself the transport for `/chat` voice conversation.

### 5. Keep Voice-Conversation Autoplay Explicitly Always-On

Voice conversation should remain an always-play-back mode by design.

Reason:

- the user-selected mode is "voice conversation," not "transcribe only"
- normal message-level TTS autoplay settings are about optional message playback
- binding voice conversation to the generic autoplay toggle creates a confusing failure mode where the feature appears to succeed textually but not audibly

That means:

- voice conversation autoplay is intentional and separate from message-TTS autoplay
- no behavior change is required here other than documenting the contract clearly

### 6. Preserve the Current Runtime Chat Loop

When voice conversation is available and preflight passes, keep the current overall runtime structure:

- mic audio streams to `/api/v1/audio/chat/stream`
- `full_transcript` creates the user turn
- `llm_delta` updates the in-flight assistant message
- `llm_message` finalizes assistant text
- `tts_start` plus binary audio frames plus `tts_done` drives spoken playback

Relevant units:

- [`useVoiceChatStream.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useVoiceChatStream.tsx)
- [`useVoiceChatMessages.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useVoiceChatMessages.tsx)

The target fix is not a transport rewrite. It is making the existing transport honest, shared, and diagnosable.

### 7. Standardize Failure Handling Across Both Surfaces

Failures should split into two categories.

#### Unavailable Before Start

Examples:

- no `/api/v1/audio/chat/stream`
- missing auth
- missing model
- unresolved TTS configuration

Behavior:

- disable or immediately reject voice conversation
- show a stable, actionable reason
- do not pretend the feature is active

#### Failed After Start

Examples:

- WebSocket disconnect
- rate limit/quota
- backend `bad_request`
- backend TTS generation failure

Behavior:

- if no `full_transcript` has been emitted yet, persist no chat turn
- if `full_transcript` has already created the user message:
  - keep the user message
  - if no assistant text has streamed yet, remove the empty assistant placeholder
  - if assistant text has streamed, finalize the visible assistant message with the accumulated partial text and mark it as interrupted using the existing interrupted-generation metadata shape
- disable the active voice-conversation toggle
- show the surfaced error or a normalized fallback string

The same status model and messages should be used by:

- [`PlaygroundForm.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx)
- [`form.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Sidepanel/Chat/form.tsx)

Interruption metadata contract:

- do not invent a new voice-chat-only message metadata shape
- reuse the existing interrupted-generation pattern already used in the main chat flows:
  - `generationInfo.interrupted`
  - `generationInfo.interruptionReason`
  - `generationInfo.interruptedAt`
- apply that existing shape through the current message-variant update path so the interrupted assistant state is rendered consistently with other partial-response failures

## Testing Strategy

### 1. Capability Tests

Extend:

- [`server-capabilities.test.ts`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/services/__tests__/server-capabilities.test.ts)

Verify:

- legacy broad `hasVoiceChat` behavior remains unchanged unless intentionally migrated
- new strict `hasVoiceConversationTransport` is true only when `/api/v1/audio/chat/stream` exists

### 2. Shared Audio Status / Availability Tests

Extend:

- [`useTldwAudioStatus.test.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/__tests__/useTldwAudioStatus.test.tsx)

Or add a dedicated test for the new resolver if availability logic is split out.

Verify:

- `/chat` voice conversation does not light up from `hasAudio` alone
- both surfaces get the same availability result for the same capability and settings input

### 3. Hook Preflight Tests

Extend:

- [`useVoiceChatStream.interrupt.test.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx)

Add cases for:

- missing auth
- no selected client model, allowing backend defaults
- selected model present but provider resolution fails
- unresolved TTS config
- browser provider without valid server fallback
- backend disconnect after transcript begins

### 4. Cross-Surface Contract Tests

Add or extend contract tests so both surfaces prove they consume the same voice-conversation availability rule.

Relevant existing contract direction:

- [`dictation.cross-surface.contract.test.ts`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Playground/__tests__/dictation.cross-surface.contract.test.ts)

### 5. Manual Verification Matrix

Required manual checks:

1. Server exposes standalone STT and TTS but not `/audio/chat/stream`
   - Speech page standalone STT/TTS still works
   - `/chat` voice conversation is unavailable with a clear reason

2. Server exposes `/audio/chat/stream`
   - WebUI `/chat` voice conversation submits automatically
   - assistant text streams into chat
   - assistant audio plays automatically

3. Extension sidepanel with the same server
   - same voice conversation behavior and same availability logic

4. Misconfigured TTS state
   - user gets a clear voice-conversation-specific failure rather than transcript-only stall

5. Capability discovery falls back to bundled local spec only
   - `/chat` voice conversation does not become available solely because the fallback spec contains `/audio/chat/stream`
   - strict transport support stays conservative until authoritative discovery succeeds

6. No selected client model
   - voice conversation may still start if backend defaults can carry the turn
   - if a user-selected model is present but provider resolution fails, preflight surfaces a clear model/provider error

## Implementation Notes For Planning

- Prefer a new strict transport capability over redefining `hasVoiceChat` in place.
- Prefer one shared resolver over duplicating surface-specific booleans.
- Prefer explicit TTS normalization over ad hoc provider branching in the UI layer.
- Treat the backend route as provisionally healthy unless new reproduction evidence points elsewhere.
- Keep a stitched REST fallback out of this fix unless new investigation proves the strict transport is unavailable in important supported deployments.

## Rejected Alternatives

### 1. Redefine `hasVoiceChat` globally

Rejected because the current repo and tests already use that name for a looser meaning.

### 2. Add a stitched REST fallback immediately

Rejected for this fix because it introduces a second voice-chat architecture before the primary transport has been made honest and diagnosable.

### 3. Treat browser TTS as always invalid for voice chat

Rejected because the current product state already mixes browser-facing TTS selection with server-backed voice-chat synthesis. The fix should make that mapping explicit, not silently overcorrect it.

## Definition Of Done For Planning

- the spec distinguishes broad audio support from strict voice-conversation transport support
- both chat surfaces are required to use the same availability contract
- voice-chat preflight explicitly covers auth, model, and TTS config resolution
- the design makes autoplay behavior intentional rather than accidental
- the testing plan covers both capability semantics and the reported transcript-only stall class
