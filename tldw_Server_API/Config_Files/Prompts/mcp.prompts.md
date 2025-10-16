# MCP Module Prompts

## Tool Invocation Guidance
```
Choose the minimal set of tools to fulfill the request. Validate inputs, handle
errors gracefully, and return clear results. When uncertain, ask clarifying questions.
```

Changelog:
- v1.1: Add knowledge.search/get examples with chunk_with_siblings retrieval.
- v1.0: Initial MCP tool invocation guidance.

## Example Prompts

### search_knowledge
Use the unified knowledge search to find relevant Notes/Media/Chats/Characters/Prompts.

Instructions to the agent:
```
1) Call knowledge.search with a clear, specific query and optional filters.
2) Review URIs and pick the most promising few.
3) For each, call knowledge.get with retrieval.mode = "chunk_with_siblings" and a token budget.
4) Summarize or answer using the returned content; avoid pasting everything verbatim.
```

Suggested tool call (example):
```
knowledge.search {
  query: "explain the merge node usage in n8n",
  limit: 8,
  sources: ["media", "notes"],
  snippet_length: 300,
  filters: { media: { media_types: ["html", "pdf"], order_by: "relevance" } }
}
```

Then retrieve a top result with a budgeted window around the anchor chunk:
```
knowledge.get {
  source: "media",
  id: 123,
  retrieval: { mode: "chunk_with_siblings", max_tokens: 6000, chars_per_token: 4 }
}
```

### my_knowledge
Restrict to private per-user sources and bias towards Notes/Chats, still using chunked retrieval.

Suggested tool call (example):
```
knowledge.search {
  query: "project alpha meeting decisions",
  sources: ["notes", "chats", "media"],
  limit: 10,
  snippet_length: 300,
  filters: { chats: { by: "both" } }
}

knowledge.get {
  source: "chats",
  id: "conversation-42",
  retrieval: { mode: "chunk_with_siblings", max_tokens: 2000, chars_per_token: 4 }
}
```
