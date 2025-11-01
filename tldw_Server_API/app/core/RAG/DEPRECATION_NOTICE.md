# RAG Module Deprecation Notice

## Current Architecture (v4.0 - Unified Pipeline)

The RAG system now uses a single, unified pipeline where all features are controlled by explicit parameters. See `rag_service/unified_pipeline.py` and the `/api/v1/rag/*` endpoints.

### Active Modules (Keep These)

Located in `/app/core/RAG/rag_service/`:

1. **unified_pipeline.py** - Unified pipeline entry point
2. **table_serialization.py** - Table processing functionality
3. **query_expansion.py** - Query expansion strategies
4. **semantic_cache.py** - Semantic caching implementation
5. **advanced_reranking.py** - Document reranking strategies
6. **performance_monitor.py** - Performance monitoring
7. **chromadb_optimizer.py** - ChromaDB optimizations for 100k+ docs
8. **types.py** - Core type definitions
9. **config.py** - Configuration management

### Deprecated Modules (To Be Archived)

These modules are replaced by the functional pipeline and should be archived:

#### Object-Oriented Pipeline (replaced)
- **app.py** - Old RAGApplication class
- **integration.py** - Old RAGService class
- **pipeline_orchestrator.py** - Object-oriented pipeline (replaced by functional approach)

#### Old Retrieval/Processing (superseded)
- **retrieval.py** - Separate retriever classes
- **processing.py** - Separate processor classes
- **generation.py** - Separate generator classes

#### Duplicates/Old Implementations
- **cache.py** - Replaced by semantic_cache.py
- **metrics.py** - Replaced by performance_monitor.py
- **enhanced_chunking.py** - Functionality in table_serialization.py
- **connection_pool.py** - Not needed with functional approach
- **citation_retriever.py** - Not implemented in current pipeline
- **parent_retriever.py** - Not implemented in current pipeline

#### Example/Test Files
- **example_usage.py** - Old examples
- **tui_example.py** - Old TUI examples

### API Endpoints

#### Active
- `/api/v1/rag/search` - Unified search
- `/api/v1/rag/batch` - Unified batch processing
- `/api/v1/rag/simple`, `/api/v1/rag/advanced`, `/api/v1/rag/features`, `/api/v1/rag/health/*`

#### Deprecated
- Legacy v1/v2 endpoints (retained temporarily)

### Migration Path

1. For API users
   - Move to `/api/v1/rag/search` and pass features as request parameters
   - Use `/api/v1/rag/batch` for multi-query processing

2. For direct module users
   ```python
   from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import unified_rag_pipeline
   result = await unified_rag_pipeline(query="your query", top_k=10, expand_query=True)
   ```

3. **Custom Pipeline Example:**
   ```python
   # Unified pipeline example
   from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import unified_rag_pipeline
   result = await unified_rag_pipeline(query, top_k=10, expand_query=True)
   ```

### Archive Structure

Move deprecated files to:
```
/app/core/RAG/ARCHIVE/deprecated_v2/
├── app.py
├── integration.py
├── retrieval.py
├── processing.py
├── generation.py
├── pipeline_orchestrator.py
├── cache.py
├── metrics.py
├── enhanced_chunking.py
├── connection_pool.py
├── citation_retriever.py
├── parent_retriever.py
├── example_usage.py
└── tui_example.py
```

### Timeline

- 2024-08-19: Functional pipeline implemented (v3)
- 2025-08-xx: Unified pipeline introduced (v4)
- 2025-Q4: Retire remaining deprecated endpoints

### Benefits of Unified Architecture

1. Simplicity: Single function, explicit parameters
2. Flexibility: Mix-and-match features per request
3. Transparency: No hidden configuration layers
4. Testability: Direct parameterization simplifies testing
5. Maintainability: Fewer surfaces, clearer contracts

### Contact

For questions about the migration, please contact the development team.
