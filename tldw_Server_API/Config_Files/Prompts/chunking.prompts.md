# Chunking Module Prompts

## Structure-aware Contextual Header
Guideline for deriving headers when enabled:
```
Compose a short header with the document title and the nearest section header.
Do not include additional text. Format: "Doc: <Title> | Section: <Header>".
```

## Rolling Summarization (Optional)
```
Provide a concise summary of the text below. Maintain continuity with the previous
context. Focus on main points; avoid duplication. Output 3-5 sentences.
```

Changelog:
- v1.0: Added guidance for contextual headers and rolling summaries.
