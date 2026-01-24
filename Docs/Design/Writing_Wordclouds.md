# Writing Wordclouds (Design)

## Goal
Expose a writing-module feature to generate word clouds from arbitrary user-supplied text. Output is JSON only, computed in the background and cached.

## API
### Create/Queue
`POST /api/v1/writing/wordclouds`

Request:
```json
{
  "text": "string",
  "options": {
    "max_words": 100,
    "min_word_length": 3,
    "keep_numbers": false,
    "stopwords": ["optional", "list"]
  }
}
```

Response (202 when queued, 200 when cached/ready):
```json
{
  "id": "hash-id",
  "status": "queued|running|ready|failed",
  "cached": true,
  "result": {
    "words": [{"text":"example","weight":12}],
    "meta": {"input_chars":123, "total_tokens":456, "top_n":100}
  },
  "error": null
}
```

### Fetch Status/Result
`GET /api/v1/writing/wordclouds/{id}`

## Storage
New table `writing_wordclouds` in ChaChaNotes DB:
- `id` (TEXT, primary key; hash of text + options)
- `status` (queued|running|ready|failed)
- `options_json`, `words_json`, `meta_json`, `error`
- timestamps + `client_id`

Cached results keyed by a stable SHA-256 hash of `text + options_json`.

## Background Flow
- POST computes hash and checks cache.
- If ready, return 200 with cached result.
- If queued/running, return 202.
- If missing, insert row as queued and schedule background compute.
- In tests, compute inline to avoid flakiness.

## Tokenization/Weights
- Normalize to lowercase.
- Regex tokens over `[\\w'-]+`, filter by length.
- Optional stopword removal (default English list).
- Weight = raw frequency.

