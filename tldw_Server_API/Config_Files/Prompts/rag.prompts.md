# RAG Module Prompts

## Retrieval Guidance (Relevance)
```
Return the most relevant passages that answer the query. Prefer passages that
directly contain the requested facts, entities, or numbers. Avoid redundant results.
```

## Reranking Instruction
```
Rerank the following candidates by how well they answer the query. Penalize verbose
or off-topic matches. Promote entries that contain precise, verifiable statements.
```

Changelog:
- v1.0: Seed prompts for retrieval and reranking.
