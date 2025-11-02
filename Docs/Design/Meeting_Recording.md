# Meeting Recording


https://github.com/Zackriya-Solutions/meeting-minutes
https://github.com/fastrepl/hyprnote
https://github.com/cooldude6000/meeting-bot69
https://www.granola.ai/
https://github.com/Zackriya-Solutions/meeting-minutes
https://github.com/murtaza-nasir/speakr


## Current Capabilities

- Real-time streaming transcription over WebSocket with segment-level metadata (start/end timestamps, overlap) for timeline visualizations.
- Optional live insights engine (`insights` config block) that mirrors granola-style meeting notes: continuous summaries, action items, decisions, and topic tags.
- Final post-meeting summary emitted on `commit`, using the same JSON schema as live updates to simplify client storage/sharing.
- Configurable cadence via `summary_interval_seconds` and `context_window_segments`, with provider/model defaults resolved from the primary chat settings.
- Backward-compatible behavior when insights are disabled-clients see the original transcript messages without additional payloads.
- Speaker diarization toggle that annotates each finalized segment with `speaker_id`/`speaker_label` and can persist a session WAV for replay or downstream processing.
