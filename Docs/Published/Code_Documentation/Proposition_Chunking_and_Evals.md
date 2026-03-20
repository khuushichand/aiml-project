# Proposition Chunking and Evaluation

This document describes the propositional chunking method and the accompanying evaluation capabilities.

## Proposition Chunking

Method name: `propositions`

Engines:
- `heuristic` (default): Fast, zero-dependency heuristics splitting by punctuation, subordinate markers, and coordination
- `spacy`: Uses spaCy dependency cues (`mark`, `cc`/`conj`) when spaCy + model are available
- `llm`: Uses your configured LLM to extract atomic claims via controlled prompts
- `auto`: Attempts `spacy` first, falls back to `heuristic` if unavailable

Prompt profiles (LLM engine):
- `generic`: General-purpose atomic proposition extraction
- `claimify`: Guidance aligned with high-quality factual claims (verifiable, no pronouns, precise)
- `gemma_aps`: Atomic Proposition Simplification style (APS)

Options (request-level):
- `proposition_engine`: one of `heuristic|spacy|llm|auto`
- `proposition_aggressiveness`: `0..2` (how aggressively to split within sentences)
- `proposition_min_proposition_length`: minimum chars for a proposition before merging small ones
- `proposition_prompt_profile`: `generic|claimify|gemma_aps` (used for LLM engine)

Chunk sizing semantics:
- For `method="propositions"`, `max_size` and `overlap` are counts of propositions per chunk (not characters/tokens). The stride is `max(1, max_size - overlap)`.

LLM usage:
- Only the `llm` engine variant requires an LLM. `heuristic` and `spacy` do not. Some capability listings may show `propositions` as “LLM-required” because it optionally supports an LLM engine.

Example (API chunking):
```json
{
  "text_content": "Alice founded Acme Corp in 2020 and Bob joined in 2021.",
  "options": {
    "method": "propositions",
    "max_size": 3,
    "overlap": 1,
    "proposition_engine": "auto",
    "proposition_aggressiveness": 2,
    "proposition_prompt_profile": "claimify"
  }
}
```

### System Defaults (config.txt)
In `tldw_Server_API/Config_Files/config.txt` `[Chunking]` section:

```
[Chunking]
proposition_engine=heuristic        # heuristic | spacy | llm | auto
proposition_prompt_profile=generic  # generic | claimify | gemma_aps
proposition_aggressiveness=1        # 0..2
proposition_min_proposition_length=15
```

These defaults are applied when `method='propositions'` is used in media ingestion and are also loaded into the module-level defaults for chunking APIs.

Note: spaCy is optional. If you plan to use `spacy` engine:
- Install spaCy: `pip install spacy`
- Download model: `python -m spacy download en_core_web_sm`

## Proposition Evaluation API

Endpoint: `POST /api/v1/evaluations/propositions`

Request:
```json
{
  "extracted": ["Alice founded Acme in 2020", "Bob joined Acme in 2021"],
  "reference": ["Alice founded Acme in 2020", "Carol raised funding for Acme in 2022"],
  "method": "semantic",  // or "jaccard"
  "threshold": 0.7
}
```

Response:
```json
{
  "precision": 0.5,
  "recall": 0.5,
  "f1": 0.5,
  "matched": 1,
  "total_extracted": 2,
  "total_reference": 2,
  "claim_density_per_100_tokens": 12.0,
  "avg_prop_len_tokens": 8.5,
  "dedup_rate": 0.0,
  "details": {"threshold": 0.7, "method": 1.0},
  "metadata": {"evaluation_id": "eval_proposition_extraction_..."}
}
```

Matching methods:
- `semantic`: TF-IDF cosine similarity (falls back to Jaccard if scikit-learn unavailable)
- `jaccard`: token-based Jaccard similarity

Notes:
- When `semantic` is selected but scikit-learn is unavailable, matching falls back to Jaccard with a default threshold of 0.6.

The service stores results in the evaluations database with type `proposition_extraction`.

### Run-Managed Evaluations

You can define an evaluation with `eval_type="proposition_extraction"` and provide an inline dataset of samples where each sample contains:

```json
{
  "input": {
    "extracted": ["A is B", "C is D"],
    "reference": ["A is B"]
  },
  "expected": {}
}
```

Create a run via `POST /api/v1/evaluations/{eval_id}/runs`, then poll `GET /api/v1/evaluations/runs/{run_id}` until status is `completed`.

Outputs include per-sample metrics (precision, recall, F1) and counts, with pass/fail determined by F1 threshold.
