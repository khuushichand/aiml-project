# Transcript Segmentation API (TreeSeg)

Segments a transcript into coherent blocks to aid diarization and human editing.
Uses a hierarchical tree segmentation algorithm (arXiv:2407.12028) over utterance-level
embeddings of context-expanded blocks.

## Endpoint

- POST `/api/v1/audio/segment/transcript`

## Auth + Rate Limits

- Single-user mode: send `X-API-KEY: <your_key>`
- Multi-user mode (JWT): send `Authorization: Bearer <JWT>`

Rate limiting: 30 requests/minute per IP (SlowAPI).

## Request Body

```
{
  "entries": [
    {"composite": "Hello team", "start": 0.0, "end": 2.5, "speaker": "SPEAKER_0"},
    {"composite": "Project update ...", "start": 2.6, "end": 5.1, "speaker": "SPEAKER_1"}
  ],
  "K": 6,
  "min_segment_size": 5,
  "lambda_balance": 0.01,
  "utterance_expansion_width": 2,
  "min_improvement_ratio": 0.0,
  "embeddings_provider": "openai",
  "embeddings_model": "text-embedding-3-small"
}
```

Fields:
- `entries`: List of utterances. Each requires `composite` text. Optional: `start`, `end`, `speaker`, `metadata`.
- `K`: Maximum number of segments to produce.
- `min_segment_size`: Minimum utterances per segment.
- `lambda_balance`: Balance penalty to discourage degenerate splits.
- `utterance_expansion_width`: Number of previous utterances concatenated to each block.
- `min_improvement_ratio`: Stop splitting when relative improvement (per split) drops below this threshold (0-1).
- `embeddings_provider`/`embeddings_model`: Optional overrides when using the built-in embedding service.

## Response Body

```
{
  "transitions": [0,0,0,1,0,0,1,...],
  "transition_indices": [3, 6],
  "segments": [
    {
      "indices": [0,1,2],
      "start_index": 0,
      "end_index": 2,
      "start_time": 0.0,
      "end_time": 5.1,
      "speakers": ["SPEAKER_0","SPEAKER_1"],
      "text": "Hello team\nProject update ..."
    },
    ...
  ]
}
```

- `transitions`: A vector with 1 marking the first utterance of each segment (except the first).
- `transition_indices`: Start indices (0-based) of each segment after the first. Convenient for UI.
- `segments`: Ordered list of coherent segments with indices, time bounds, speakers, and concatenated text.

## Notes

- Embeddings are provider-agnostic. If not injecting your own embedder, the service uses the configured AsyncEmbeddingService.
- Tweak `min_segment_size`, `lambda_balance`, and `utterance_expansion_width` to adjust segment granularity and balance.
  - Larger `min_segment_size` = fewer segments; higher `lambda_balance` = more balanced sizes.
- This API is intended to propose edit boundaries; always allow human oversight.

## Errors

- 401 Unauthorized: Missing/invalid `X-API-KEY` or Bearer token
- 400 Bad Request: `entries` missing or empty
- 429 Too Many Requests: Rate limit exceeded
- 500 Internal Server Error: Segmentation failed

## Example (curl)

```
curl -X POST "http://127.0.0.1:8000/api/v1/audio/segment/transcript" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "entries": [
      {"composite": "TOPIC_A: hello"},
      {"composite": "TOPIC_A: details"},
      {"composite": "TOPIC_B: change topic"}
    ],
    "K": 2,
    "min_segment_size": 1,
    "lambda_balance": 0.01,
    "utterance_expansion_width": 1
  }'
```

## Integration with Diarization

`DiarizationService.propose_human_edit_boundaries(...)` provides a helper to call TreeSeg on transcript entries
and return transitions and segments for UI editing boundaries.
