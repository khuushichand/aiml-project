# Playground Chat Voice Button Visibility Design

**Goal:** Keep speech-to-speech discoverable in Playground chat by showing the voice controls even when realtime voice conversation is unavailable, while preserving the stricter backend availability contract for whether the control can actually be used.

## Problem

The current chat UI hides the speech-to-speech button entirely when `voiceChatAvailable` is false. After the recent voice conversation contract changes, that value now depends on stricter conditions than basic STT/TTS availability:

- realtime voice transport must be advertised
- auth must be ready
- STT/TTS health must not be unhealthy or unavailable
- TTS configuration must be complete

This is technically correct, but it creates a discoverability regression. Users can no longer tell whether speech-to-speech exists but is unavailable, or whether the feature was removed altogether.

## Desired Behavior

The UI should:

- keep the main headphone button visible when voice is relevant to the connected chat surface
- keep the `Modes -> Voice mode` entry visible as well
- disable those controls when speech-to-speech is unavailable
- explain why the control is disabled using the existing shared availability contract

The UI should not:

- relax the real availability contract
- permit starting voice conversation when the transport or config is missing

## Approach

### 1. Separate visibility from availability

Today, the main button only renders when `voiceChatAvailable` is true. That couples visibility to operability.

The change will introduce a broader render condition for chat voice controls, based on voice relevance rather than full readiness. The recommended visibility condition is:

- connected server plus audio-relevant capability, derived from existing `hasServerVoiceChat`

That lets the control remain visible for builds that still expose STT/TTS or voice-chat-related capabilities, even if the stricter realtime transport requirement is not satisfied.

### 2. Preserve the existing enablement gate

`voiceChatAvailable` will continue to be computed from `resolveVoiceConversationAvailability(...)`.

That means the button and mode entry will remain disabled when:

- `hasVoiceConversationTransport` is false
- auth is missing
- STT/TTS health is bad
- TTS config is incomplete

No runtime behavior changes are planned for the actual start/stop flow.

### 3. Surface the shared unavailable reason

The existing availability object already carries:

- `reason`
- `message`

The UI will resolve the message key into a user-facing string once and thread it into all Playground voice entry points:

- main headphone button tooltip/title
- `Modes -> Voice mode` entry tooltip/title
- Playground tools popover voice control tooltip/title

This keeps Playground surfaces consistent and avoids duplicating reason mapping logic.

### 4. Update the main button UX

The main button should:

- render whenever voice is relevant to the server connection
- stay enabled only when `voiceChatAvailable && !isSending`
- stay disabled otherwise
- use the unavailable reason for tooltip/title when disabled due to availability

Active and error styling should remain unchanged for enabled states.

### 5. Update the mode launcher UX

The `Modes -> Voice mode` entry should:

- remain visible
- remain disabled when unavailable or sending
- expose the same unavailable reason in tooltip/title text

This preserves parity between the two entry points.

### 6. Keep the Playground tools popover aligned

The Playground tools popover already exposes a voice entry point and should not drift from the main button and `Modes` entry.

The popover control should:

- stay visible as it does today
- remain disabled when unavailable or sending
- show the same shared unavailable reason instead of generic unavailable copy

This keeps all Playground voice entry points aligned on the same contract and explanation.

### 7. Disabled-state explanation strategy

Disabled controls do not always provide reliable hover behavior on their own, so the implementation should not rely on the button element alone to carry the explanation.

The implementation should:

- use a wrapper or equivalent stable trigger so the unavailable reason remains inspectable
- keep `title` or equivalent accessible labeling aligned with the same resolved reason
- test for deterministic surfaced copy rather than brittle visual hover-only behavior where possible

## Files

- Modify: `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/PlaygroundModeLauncher.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/PlaygroundToolsPopover.tsx`
- Modify tests in `apps/packages/ui/src/components/Option/Playground/__tests__/`

## Testing

Add tests first for:

1. The main voice button remains rendered when voice is relevant but unavailable due to `transport_missing`.
2. The main voice button is disabled and exposes the unavailable reason.
3. The `Modes -> Voice mode` entry remains visible when unavailable.
4. The mode entry is disabled and exposes the same unavailable reason.
5. The Playground tools popover voice control exposes the same unavailable reason.

Regression verification:

- existing voice conversation contract tests should still pass unchanged
- existing toolbar tests should continue passing

## Risks

- If the broader visibility condition is too broad, the control may appear in cases where users do not expect voice features at all.
- If the reason string is not threaded cleanly, one Playground voice surface may be descriptive while another remains opaque.

## Recommendation

Proceed with a presentation-only fix:

- broaden render visibility
- keep strict availability
- expose shared disabled reasons consistently

This solves the user-reported disappearance in Playground chat without weakening the transport contract introduced by the recent voice conversation changes.
