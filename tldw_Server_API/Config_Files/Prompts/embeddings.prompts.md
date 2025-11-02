# Embeddings Module Prompts

## Situate Context Prompt (per-chunk)
```
Please give a short succinct context to situate this chunk within the overall document
for the purposes of improving search retrieval of the chunk.
Answer only with the succinct context and nothing else.
```

Notes:
- The code wraps this with document and chunk tags.

## Document Outline Prompt
```
Produce a brief outline of the document with 5-10 bullets. Each bullet should have a
short section title and a one-line summary.
```

Changelog:
- v1.0: Initial default prompts for outline/situating.
