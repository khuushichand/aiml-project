Embedding and Vector Store Configuration (Unified RAG)

Overview
- Unified RAG uses a vector store (e.g., ChromaDB) and an embedding configuration to enable vector search and hybrid retrieval.
- Configuration is sourced from `Config_Files/config.txt` and `.env`. The loader maps sections to `settings`.

Quick Steps
1) Enable ChromaDB as the vector store

   In `tldw_Server_API/Config_Files/config.txt`:

   [RAG]
   vector_store_type = chromadb

2) Configure embeddings via [Embeddings]

   The app supports a section named `Embeddings` in `config.txt` (mapped to `settings['EMBEDDING_CONFIG']`). Example for OpenAI:

   [Embeddings]
   default_provider = openai
   default_model_id = text-embedding-3-small
   embedding_dimension = 1536

   # Optional model overrides
   # models.text-embedding-3-small.provider = openai
   # models.text-embedding-3-small.dimensions = 1536

   If you prefer HuggingFace sentence-transformers:

   [Embeddings]
   default_provider = huggingface
   default_model_id = sentence-transformers/all-MiniLM-L6-v2
   embedding_dimension = 384

3) Add secrets to `.env`

   Put secrets in `tldw_Server_API/Config_Files/.env` (do not hardcode in `config.txt`). For OpenAI:

   OPENAI_API_KEY=sk-...

   The loader picks up `.env` automatically at startup.

4) Verify
- Start the app; logs will show which sections and providers are loaded.
- You can exercise the vector store endpoints: `POST /vector_stores`, `POST /vector_stores/{store_id}/vectors`, `POST /vector_stores/create_from_media`.
- Unified vector search: `POST /api/v1/rag/search` with `search_mode="vector"`.

Notes
- The retriever expects a per-user media collection named `user_{user_id}_media_embeddings` (for single-user mode, typically `user_1_media_embeddings`).
- The tests include guarded vector-mode checks that upsert vectors and query `/rag/search` with `search_mode="vector"`. These run automatically when ChromaDB and embeddings are configured.

