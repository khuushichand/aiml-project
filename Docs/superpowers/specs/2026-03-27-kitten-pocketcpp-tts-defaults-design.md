# KittenTTS And PocketTTS.cpp Default TTS Design

**Goal:** Make `kitten_tts` the primary default TTS engine and `pocket_tts_cpp` the preferred fallback across server-side automatic selection, backend generation services, SDK defaults, and all fresh-profile UI defaults, while preserving a working first-run experience.

## Problem

The current default TTS behavior is split across several layers:

- server provider priority in [tldw_Server_API/Config_Files/tts_providers_config.yaml](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/Config_Files/tts_providers_config.yaml)
- legacy startup config paths that can still influence instantiated adapters
- fresh UI storage fallbacks in chat, Playground, shared message playback, and standalone TTS surfaces
- backend generation services that still apply model/voice fallbacks when requests omit TTS settings
- voice assistant SDK defaults

Today those defaults are inconsistent and still lean on:

- `openai` or `kokoro` in backend provider ordering
- `ttsProvider="browser"` in some UI flows
- `tldwTtsModel="kokoro"` and `tldwTtsVoice="af_heart"` in fresh-profile voice chat flows
- `kokoro` and `af_heart` fallbacks in some backend output-generation paths
- `kokoro` defaults in the voice assistant SDK

That means a user can ask for “KittenTTS and PocketTTS.cpp as the defaults” and still land on Kokoro or browser-backed speech on a clean session.

## Desired Behavior

For fresh defaults, the system should behave as follows:

- `kitten_tts` is the primary default TTS engine
- `pocket_tts_cpp` is the next preferred fallback engine
- fresh UI sessions default to the server-backed TTS path, not browser TTS
- fresh UI sessions choose a working KittenTTS model and a valid Kitten voice by default
- existing stored user preferences remain untouched
- backend request/template overrides still win over the new defaults

The system should not:

- forcibly migrate or overwrite existing user settings
- make `pocket_tts_cpp` the initial selected UI model when no valid cloned/stored voice exists
- claim a default that fails on first run because PocketTTS.cpp is selected without a usable voice

## Key Constraint

`pocket_tts_cpp` is not equivalent to KittenTTS for first-run UX.

KittenTTS ships with standard voices and can safely be selected as a fresh default. PocketTTS.cpp is a voice-cloning-oriented runtime and often requires a stored or cloned voice before it can produce useful output. In the current configuration and UI language, that often surfaces as `clone_required`.

Because of that:

- `kitten_tts` can be the universal initial UI default
- `pocket_tts_cpp` should be the preferred fallback and secondary engine
- `pocket_tts_cpp` should only become the effective active default when prerequisites are actually satisfied

For this design, PocketTTS.cpp readiness should mean all of the following are true:

- the provider is enabled and reported usable by the server-side health/capability surface
- the required runtime assets for `pocket_tts_cpp` are present
- a concrete usable voice is already selected or stored, rather than a `clone_required` placeholder or empty value

## Approach

### 1. Change backend provider priority

Update [tldw_Server_API/Config_Files/tts_providers_config.yaml](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/Config_Files/tts_providers_config.yaml) so the effective default order begins with:

1. `kitten_tts`
2. `pocket_tts_cpp`

Other providers should remain available after those entries, but the ordering should no longer make Kokoro or OpenAI the first automatic choice.

### 2. Align provider enablement with the new default policy

The default provider order only matters if the providers are actually enabled and usable.

The new baseline should be:

- `kitten_tts` enabled by default for local-first usage
- `pocket_tts_cpp` preferred as fallback when it is configured and ready under the readiness definition above

The implementation must avoid a false default where `pocket_tts_cpp` is prioritized but unavailable on a fresh machine.

### 3. Change fresh UI defaults from browser/Kokoro to tldw/KittenTTS

Fresh UI storage fallbacks should be updated so a new user session resolves to:

- `ttsProvider = "tldw"`
- `tldwTtsModel = "KittenML/kitten-tts-nano-0.8"` or the chosen canonical Kitten default
- `tldwTtsVoice = <valid Kitten fallback voice>`

This needs to cover all fresh-default entry points that currently hardcode browser or Kokoro fallbacks, including:

- chat voice conversation hooks
- Playground voice conversation hooks
- speech/TTS playground entry points
- workspace audio/TTS helper surfaces where fresh defaults are materialized
- shared message playback helpers that currently materialize `useStorage(..., fallback)` defaults

This scope is intentionally repo-wide for fresh-profile defaults, not chat-only.

### 4. Keep PocketTTS.cpp as the preferred secondary engine

The UI should reflect the new priority without pretending PocketTTS.cpp is a universal first-run choice.

That means:

- lists and provider priority should place PocketTTS.cpp immediately after KittenTTS where the UI reflects default order
- auto-selection logic may choose PocketTTS.cpp only when the readiness gate above is satisfied
- generic fresh fallbacks should remain on KittenTTS until PocketTTS.cpp readiness is proven

### 5. Align SDK defaults with the product defaults

The voice assistant SDK currently defaults to Kokoro-style settings.

To keep external consumers aligned with the product defaults, its fresh defaults should move to the new policy:

- default `ttsProvider` should prefer `kitten_tts`
- default `ttsVoice` should resolve to the canonical Kitten fallback voice
- PocketTTS.cpp should be documented or supported as the preferred fallback rather than the initial unconditional choice

The SDK section should not describe a `ttsModel` default unless the SDK config surface actually grows that field.

### 6. Align backend generation-service fallbacks

This defaults policy should also apply to backend non-chat generation paths that currently synthesize their own fallback provider/model/voice values.

That includes at minimum:

- output generation services
- audiobook/job workers

Those paths should inherit the new priority policy when request-level or template-level TTS settings are absent, while still preserving any explicit request/template overrides.

### 7. Preserve existing users

This is a defaults change, not a migration.

Existing stored settings in local storage or persisted app settings should remain as-is. Only the fallback values used when no preference exists should change.

## Files

- Modify: [tldw_Server_API/Config_Files/tts_providers_config.yaml](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/Config_Files/tts_providers_config.yaml)
- Modify: [tldw_Server_API/app/services/outputs_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/services/outputs_service.py)
- Modify: [tldw_Server_API/app/services/audiobook_jobs_worker.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/services/audiobook_jobs_worker.py)
- Modify: [apps/packages/ui/src/hooks/useVoiceChatStream.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useVoiceChatStream.tsx)
- Modify: [apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx)
- Modify: [apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx)
- Modify: [apps/packages/ui/src/components/Option/TTS/TtsPlaygroundPage.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/TTS/TtsPlaygroundPage.tsx)
- Modify: [apps/packages/ui/src/components/Option/TTS/TtsProviderPanel.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/TTS/TtsProviderPanel.tsx)
- Modify: [apps/packages/ui/src/components/Common/Playground/useMessageState.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/Playground/useMessageState.ts)
- Modify: [apps/packages/ui/src/components/Common/Playground/Message.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/Playground/Message.tsx)
- Modify as needed: [apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/hooks/useAudioTtsSettings.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/hooks/useAudioTtsSettings.tsx)
- Modify as needed: [apps/packages/ui/src/hooks/useResolvedPersonaVoiceDefaults.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useResolvedPersonaVoiceDefaults.tsx)
- Modify: [apps/packages/voice-assistant-sdk/src/client/VoiceAssistantClient.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/voice-assistant-sdk/src/client/VoiceAssistantClient.ts)
- Update tests in:
  - [tldw_Server_API/tests](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/tests)
  - [apps/packages/ui/src/hooks/__tests__](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/__tests__)
  - [apps/packages/ui/src/components/Option](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option)
  - [apps/packages/voice-assistant-sdk/src](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/voice-assistant-sdk/src)

## Testing

Add tests first for:

1. Backend effective TTS priority begins with `kitten_tts`, then `pocket_tts_cpp`.
2. Fresh voice chat/UI fallbacks resolve to `ttsProvider="tldw"` and a Kitten model, not browser/Kokoro.
3. Fresh TTS playground fallbacks resolve to KittenTTS defaults.
4. Shared message playback and workspace helper fallbacks no longer resolve to browser/Kokoro on a fresh profile.
5. Backend output-generation and audiobook fallback logic no longer resolves to Kokoro/`af_heart` when explicit settings are absent.
6. SDK defaults no longer resolve to Kokoro and instead expose the canonical Kitten provider/voice defaults.
7. Existing stored settings and explicit request/template overrides still override the new defaults.

Verification should include:

- backend config/effective health checks showing the intended providers are visible and usable
- a fresh-profile browser verification showing the voice/chat controls resolve to KittenTTS by default
- a fresh-profile verification of standalone TTS and shared message playback surfaces
- regression checks for existing TTS settings flows, backend output jobs, and voice conversation availability logic

## Risks

- If `kitten_tts` is made primary but not actually enabled/available in the target environment, the new default will still feel broken.
- If PocketTTS.cpp is treated as an unconditional first selection, first-run UX can regress due to missing cloned voices.
- If only some UI or backend fallback surfaces are updated, new sessions will remain inconsistent across chat, Playground, TTS pages, message playback, SDK consumers, and non-chat generation jobs.

## Recommendation

Proceed with a two-tier default policy:

- make `kitten_tts` the true universal fresh default
- make `pocket_tts_cpp` the preferred fallback when ready

That satisfies the intent of “KittenTTS and PocketTTS.cpp are the defaults” without replacing a working default with a clone-dependent one that may fail on first run.
