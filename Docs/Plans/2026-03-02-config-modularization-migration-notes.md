# Config Modularization Migration Notes (2026-03-02)

This note captures the compatibility-impacting config changes introduced during the config modularization and hardening effort.

## Summary

- Added modular config section loaders under `tldw_Server_API/app/core/config_sections/`.
- Added `legacy_get()` compatibility accessor in `tldw_Server_API/app/core/config.py` for legacy call sites.
- Removed placeholder-based TTS defaults in `load_and_log_configs()` and replaced them with safe runtime defaults.

## TTS Default Changes

The loader now treats common placeholder literals as unset values in `[TTS-Settings]`:

- empty string
- `FIXME`
- `TODO`
- `TBD`
- `CHANGE_ME`
- `CHANGE-ME`
- `PLACEHOLDER`
- `NONE`
- `NULL`
- `N/A`
- `NA`

When these are encountered for TTS settings, defaults are applied:

- `default_google_tts_model`: `en-US`
- `default_google_tts_voice`: `en-US-Neural2-A`
- `default_eleven_tts_model`: `eleven_monolingual_v1`
- `default_eleven_tts_voice`: `pNInz6obpgDQGcFmaJgB`
- `default_eleven_tts_language_code`: `en`
- `default_eleven_tts_voice_stability`: `0.5`
- `default_eleven_tts_voice_similiarity_boost`: `0.75`
- `default_eleven_tts_voice_style`: `0.0`
- `default_eleven_tts_voice_use_speaker_boost`: `true`
- `default_eleven_tts_output_format`: `mp3_44100_128`

## Operator Action

- If you intentionally need non-default ElevenLabs or Google TTS behavior, set explicit non-placeholder values in:
  - environment variables where supported, and/or
  - `tldw_Server_API/Config_Files/config.txt` under `[TTS-Settings]`.
- Do not use placeholder literals for deployed configs; they will be normalized to defaults.

## Verification Added

- `tldw_Server_API/tests/Config/test_config_precedence_contract.py`
  - `test_tts_defaults_are_valid_values_not_placeholders`
  - Asserts that placeholder values do not survive into runtime `tts_settings`.
