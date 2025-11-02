OpenAI-Compatible Strict Mode for Local Providers
=================================================

Overview
--------
Some OpenAI-compatible local servers are strict about accepted request fields. If a request includes
non-standard keys (for example, `top_k`), these servers may respond with 400/422 errors.

To support these environments, the server provides a strict filtering option for local providers that
drops non-standard fields from the Chat Completions payload.

When to Enable
--------------
Enable strict mode when you observe provider errors that mention unknown or unsupported parameters.
Common symptoms include:

- HTTP 400/422 responses immediately upon request
- Error messages like "unknown field top_k" or "unsupported parameter"

Configuration
-------------
Set `strict_openai_compat: true` in the relevant provider’s configuration block. Supported sections:

- `local_llm`
- `llama_api`
- `ooba_api` (Text Generation WebUI OpenAI Extension)
- `tabby_api`
- `vllm_api`
- `aphrodite_api`
- `ollama_api`

For the `local_llm` section, you can also enable strict mode via environment variable:

```bash
export LOCAL_LLM_STRICT_OPENAI_COMPAT=1
```

Effect
------
When strict mode is enabled, requests are filtered to only include the standard OpenAI Chat Completions keys:

```
messages, model, temperature, top_p, max_tokens, n, stop, presence_penalty, frequency_penalty,
logit_bias, seed, response_format, tools, tool_choice, logprobs, top_logprobs, user, stream
```

Notes
-----
- This does not affect commercial providers; it only applies to local OpenAI-compatible providers listed above.
- If your server supports a broader set of parameters, leave strict mode disabled (default) to pass them through.
- See the LLM module README for additional details and examples:
  `tldw_Server_API/app/core/LLM_Calls/README.md`
