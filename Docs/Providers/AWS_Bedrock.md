AWS Bedrock Provider (OpenAI-Compatible Chat API)

Overview
- The server now supports AWS Bedrock via its OpenAI-compatible Chat Completions endpoint.
- Streaming and non-streaming responses are supported.
- Bedrock Guardrails are supported via request-body passthrough.

Configuration
- Environment variables (preferred) or `tldw_Server_API/Config_Files/config.txt` [API] keys:
  - `BEDROCK_API_KEY` or `AWS_BEARER_TOKEN_BEDROCK`
  - `BEDROCK_REGION` (e.g., `us-west-2`) or `BEDROCK_RUNTIME_ENDPOINT` (e.g., `https://bedrock-runtime.us-west-2.amazonaws.com`)
  - Optional defaults:
    - `BEDROCK_MODEL` (e.g., `openai.gpt-oss-20b-1:0`)
    - `BEDROCK_STREAMING`, `BEDROCK_TEMPERATURE`, `BEDROCK_TOP_P`, `BEDROCK_MAX_TOKENS`, `BEDROCK_API_TIMEOUT`, `BEDROCK_API_RETRY`, `BEDROCK_API_RETRY_DELAY`

Example Request
- Endpoint: `POST /api/v1/chat/completions`
- Body:

  {
    "api_provider": "bedrock",
    "model": "openai.gpt-oss-20b-1:0",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Summarize the doc."}
    ],
    "stream": false
  }

Guardrails (Optional)
- Include guardrails via `extra_headers` and `extra_body` in the request body.
- Example:

  {
    "api_provider": "bedrock",
    "model": "openai.gpt-oss-20b-1:0",
    "messages": [
      {"role": "user", "content": "Hello"}
    ],
    "extra_headers": {
      "X-Amzn-Bedrock-GuardrailIdentifier": "gr-123",
      "X-Amzn-Bedrock-GuardrailVersion": "1",
      "X-Amzn-Bedrock-Trace": "ENABLED"
    },
    "extra_body": {
      "amazon-bedrock-guardrailConfig": {"tagSuffix": "audit1"}
    }
  }

Notes
- This integration uses Bedrock’s OpenAI compatibility layer at `https://bedrock-runtime.<region>.amazonaws.com/openai/v1/chat/completions`.
- Authentication uses a Bearer token (`BEDROCK_API_KEY` or `AWS_BEARER_TOKEN_BEDROCK`).
- If you prefer SigV4 credential signing instead of API keys, open an issue; we can add an alternate auth mode.

Troubleshooting
- 401/403: Verify `BEDROCK_API_KEY` (or `AWS_BEARER_TOKEN_BEDROCK`) and model access in the target region.
- 404: Check the `BEDROCK_REGION` vs `BEDROCK_RUNTIME_ENDPOINT` and the `model` name.
- 429: Backoff; the server retries common retriable errors, but noisy requests may still rate-limit.
