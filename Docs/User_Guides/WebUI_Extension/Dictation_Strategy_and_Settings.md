# Dictation Strategy and Settings (WebUI + Extension)

This guide explains how dictation mode is selected in WebUI `/chat` and extension sidepanel chat, and how fallback works when server STT errors occur.

## Strategy Modes

The shared dictation strategy supports three requested modes:
- `auto`
- `server`
- `browser`

Resolved runtime mode is one of:
- `server`
- `browser`
- `unavailable`

## Settings and Overrides

Storage-backed settings used by both surfaces:
- `dictation_auto_fallback`:
  - `true`: default requested mode resolves to `auto`.
  - `false`: default requested mode resolves to `server`.
- `dictationModeOverride`:
  - `server`: force server STT only.
  - `browser`: force browser speech recognition only.
  - `auto` or `null`: allow automatic strategy resolution.

Speech-to-Text defaults in Settings are applied to server dictation requests:
- model
- language
- task (`transcribe` or `translate`)
- response format
- optional segmentation parameters

## Fallback Behavior

In `auto` mode, server dictation errors are classified into canonical error classes.

Auto-fallback to browser dictation is allowed for:
- `unsupported_api`
- `provider_unavailable`
- `model_unavailable`
- `transient_failure`

Auto-fallback is blocked for:
- `permission_denied`
- `auth_error`
- `quota_error`
- `empty_transcript`
- `unknown_error`

When fallback is blocked, the surface remains on server mode and shows the server error to the user.

## Diagnostics and Privacy

Both surfaces emit a sanitized event:
- `tldw:dictation:diagnostics`

Diagnostics include:
- requested/resolved mode,
- fallback reason,
- terminal error class,
- toggle intent and server/browser routing state.

Diagnostics exclude:
- transcript text,
- prompt text,
- raw audio/binary payloads.
