FlashRank Model Bundle
======================

This directory is the stable cache for FlashRank reranker assets.

Expected layout (default model):

- `models/flashrank/ms-marco-TinyBERT-L-2-v2/config.json`
- `models/flashrank/ms-marco-TinyBERT-L-2-v2/tokenizer.json`
- `models/flashrank/ms-marco-TinyBERT-L-2-v2/tokenizer_config.json`
- `models/flashrank/ms-marco-TinyBERT-L-2-v2/special_tokens_map.json`
- `models/flashrank/ms-marco-TinyBERT-L-2-v2/flashrank-TinyBERT-L-2-v2.onnx`

Configuration knobs:

- `RAG_FLASHRANK_CACHE_DIR` (env) / `flashrank_cache_dir` (`[RAG]` in `config.txt`)
- `RAG_FLASHRANK_MODEL_NAME` (env) / `flashrank_model_name` (`[RAG]` in `config.txt`)

Notes:

- If assets are missing, server RAG now falls back to retrieval order instead of failing.
- If you commit model binaries, use Git LFS for large files.
