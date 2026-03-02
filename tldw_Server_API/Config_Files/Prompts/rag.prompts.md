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

## instruction_tuned
```
Use the provided context to answer the question. Do not use any other knowledge.
Context:
{context}
Question: {question}
Answer:
```

## multi_hop_compact
```
Answer using ONLY the provided documents. Connect evidence across sources.
Context:
{context}
Question: {question}
Provide concise synthesis with inline source citations.
```

## expert_synthesis
```
You are a meticulous research assistant. Synthesize evidence, resolve contradictions,
and provide a precise answer grounded ONLY in context.
Context:
{context}
Question: {question}
Answer with explicit source citations.
```

Changelog:
- v1.0: Seed prompts for retrieval and reranking.
- v1.1: Added profile-oriented generation prompts (`instruction_tuned`, `multi_hop_compact`, `expert_synthesis`).
