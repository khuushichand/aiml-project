# PostgreSQL Support Implementation Plan

## ⚠️ ACTUAL IMPLEMENTATION STATUS ⚠️
**As of 2025-09-07 (revised 2025-XX-XX):**
- **Integration Progress**: 0% – Media/notes still hardcode SQLite; backend abstraction unused.
- **Functional PostgreSQL Support**: 0% – Endpoints continue to rely on SQLite-only code paths.
- **Tests Written**: 0 tests
- **Files Created**: Backend abstraction (~2200 LOC) lives under `app/core/DB_Management/backends/` and is tracked.
- **Git Status**: Backend modules are committed; no orphaned files.
- **Dependencies**: psycopg2 deps remain commented out in `requirements.txt` (opt-in only).
- **Configuration**: `config.txt` now exposes PostgreSQL fields (`pg_host`, `pg_database`, etc.) but runtime wiring is pending.
- **Main Issue**: `Media_DB_v2.py` and `ChaChaNotes_DB.py` still use sqlite3 directly, ignoring the abstraction work.

## Executive Summary
This document outlines the plan to add PostgreSQL support to the tldw_server RAG system while maintaining full SQLite compatibility. The implementation will allow users to choose their preferred database backend based on their needs.

## Current Status
- ✅ Created database backend abstraction base classes (NOT INTEGRATED)
- ✅ Implemented SQLite backend adapter (NOT INTEGRATED)
- ✅ Created backend factory with configuration support (NOT INTEGRATED)
- ✅ Implemented PostgreSQL backend adapter (NOT INTEGRATED)
- ✅ Created FTS query translator with bidirectional conversion (NOT INTEGRATED)
- ❌ Integration with existing code NOT STARTED
- ❌ Testing framework NOT CREATED
- ❌ Migration tools NOT CREATED

**CRITICAL NOTE**: While backend files exist (~2200 lines), they are completely disconnected from the application. Media_DB_v2.py still uses sqlite3 directly. Zero integration has occurred.

## Architecture Overview

### Design Principles
1. **Zero Breaking Changes**: Existing SQLite users unaffected
2. **Backend Agnostic**: Application code doesn't know which DB is used
3. **Feature Parity**: Core features work on both backends
4. **Graceful Degradation**: Backend-specific features documented
5. **Performance Optimized**: Each backend uses its strengths

### Component Structure
```
app/core/DB_Management/backends/
├── __init__.py           # Public API exports ✅
├── base.py               # Abstract base classes ✅
├── sqlite_backend.py     # SQLite implementation ✅
├── postgresql_backend.py # PostgreSQL implementation ✅
├── factory.py           # Backend factory ✅
├── fts_translator.py    # FTS query translation ✅
└── migration_tools.py   # Data migration utilities ⏳
```

## Implementation Phases

### Phase 1: Foundation (Current)
**Status**: INCOMPLETE - Files created but not integrated
**Timeline**: Day 1-3

Tasks:
- [x] Create abstract base classes (FILES EXIST, NOT INTEGRATED)
- [x] Implement SQLite backend adapter (FILES EXIST, NOT INTEGRATED)
- [x] Create backend factory (FILES EXIST, NOT INTEGRATED)
- [ ] Write unit tests for abstraction layer (NO TESTS EXIST)

Key Files:
- `backends/base.py` - Abstract interfaces ✅
- `backends/sqlite_backend.py` - SQLite implementation
- `backends/factory.py` - Factory pattern

### Phase 2: PostgreSQL Backend
**Status**: MISLEADING - Files exist but not functional
**Timeline**: Day 4-7

Tasks:
- [x] Implement PostgreSQL connection pooling (CODE EXISTS, NOT TESTED)
- [x] Create PostgreSQL schema converter (PARTIAL IMPLEMENTATION)
- [x] Implement FTS using tsvector/tsquery (CODE EXISTS, NOT TESTED)
- [x] Handle transaction differences (CODE EXISTS, NOT TESTED)
- [ ] Write PostgreSQL-specific tests (NO TESTS EXIST)
- [ ] Add psycopg2 to requirements.txt (MISSING)

Key Components:
```python
class PostgreSQLBackend(DatabaseBackend):
    def create_fts_table(self, table_name, source_table, columns):
        # Create tsvector column
        # Create GIN index
        # Set up triggers for auto-update
```

### Phase 3: Query Translation
**Status**: Not Started
**Timeline**: Day 8-10

Tasks:
- [ ] Build FTS5 to PostgreSQL translator
- [ ] Handle PRAGMA to PostgreSQL config mapping
- [ ] Create query optimization layer
- [ ] Test query compatibility

Translation Examples:
```sql
-- SQLite FTS5
SELECT * FROM media_fts WHERE media_fts MATCH 'python'

-- PostgreSQL
SELECT * FROM media 
WHERE to_tsvector('english', content) @@ to_tsquery('english', 'python')
```

### Phase 4: Integration
**Status**: Not Started
**Timeline**: Day 11-14

Tasks:
- [ ] Update Media_DB_v2 to use backend abstraction
- [ ] Update RAG components (connection_pool.py, database_retrievers.py)
- [ ] Update analytics_db.py
- [ ] Configuration system updates
- [ ] End-to-end testing

### Phase 5: Migration Tools
**Status**: Not Started  
**Timeline**: Day 15-17

Tasks:
- [ ] SQLite to PostgreSQL migrator
- [ ] PostgreSQL to SQLite migrator
- [ ] Schema synchronization validator
- [ ] Performance benchmarking tools

## Technical Challenges & Solutions

### Challenge 1: FTS Compatibility
**Problem**: SQLite FTS5 and PostgreSQL full-text search have different syntax and capabilities

**Solution**:
- Abstract FTS operations in base class
- Implement query translator for each backend
- Provide unified FTSQuery object

### Challenge 2: Connection Pooling
**Problem**: SQLite uses thread-local connections, PostgreSQL needs real pooling

**Solution**:
- Abstract ConnectionPool interface
- SQLite: Thread-local pool (current behavior)
- PostgreSQL: Use psycopg2 pool or SQLAlchemy

### Challenge 3: Transaction Handling
**Problem**: Different transaction semantics between databases

**Solution**:
- Unified transaction context manager
- Backend-specific implementations
- Clear documentation of differences

### Challenge 4: Data Types
**Problem**: SQLite and PostgreSQL have different type systems

**Solution**:
- Type mapping layer in backends
- Automatic conversion where possible
- Warning logs for incompatible types

## Configuration Design

### Configuration File Structure
```yaml
# config.txt additions
database:
  backend: "sqlite"  # or "postgresql"
  
  sqlite:
    path: "./databases/media.db"
    wal_mode: true
    foreign_keys: true
    journal_mode: "WAL"
    synchronous: "NORMAL"
    
  postgresql:
    host: "localhost"
    port: 5432
    database: "tldw"
    user: "tldw_user"
    password: "${DB_PASSWORD}"  # Environment variable
    sslmode: "prefer"
    pool_size: 20
    max_overflow: 40
```

### Environment Variables
```bash
# PostgreSQL connection
TLDW_PG_HOST=localhost
TLDW_PG_PORT=5432
TLDW_PG_DATABASE=tldw
TLDW_PG_USER=tldw_user
TLDW_PG_PASSWORD=secure_password
```

## Testing Strategy

### Unit Tests
- Test each backend in isolation
- Mock database connections
- Verify interface compliance

### Integration Tests
- Run same test suite against both backends
- Compare results for consistency
- Performance benchmarks

### Test Matrix
| Feature | SQLite | PostgreSQL |
|---------|--------|------------|
| Basic CRUD | ✅ | ⏳ |
| FTS Search | ✅ | ⏳ |
| Transactions | ✅ | ⏳ |
| Connection Pool | ✅ | ⏳ |
| Schema Migration | ✅ | ⏳ |

## Performance Considerations

### SQLite Optimizations
- WAL mode enabled
- Connection reuse via thread-local storage
- Minimal overhead for single-user scenarios

### PostgreSQL Optimizations
- Connection pooling (pgbouncer compatible)
- Prepared statements
- Batch operations
- Index optimization

### Benchmarks to Track
1. Connection acquisition time
2. FTS query performance
3. Bulk insert speed
4. Concurrent request handling
5. Memory usage

## Risk Assessment

### High Risk Items
1. **FTS Query Translation**: Complex edge cases
   - Mitigation: Extensive test cases, fallback to simple queries
   
2. **Data Migration**: Potential data loss
   - Mitigation: Backup before migration, validation checksums

### Medium Risk Items
1. **Performance Regression**: PostgreSQL overhead for small datasets
   - Mitigation: Clear guidance on when to use each backend
   
2. **Configuration Complexity**: More settings to manage
   - Mitigation: Sensible defaults, configuration wizard

### Low Risk Items
1. **Code Maintenance**: Two backends to maintain
   - Mitigation: Shared abstraction reduces duplication

## Success Criteria

### Must Have
- [ ] SQLite continues working exactly as before
- [ ] PostgreSQL supports core RAG, Media, and embedding operations
- [ ] Configuration-based backend selection
- [ ] Basic migration tools

### Should Have
- [ ] Performance parity for common operations
- [ ] Comprehensive test coverage
- [ ] Migration validation tools
- [ ] Performance benchmarking

### Nice to Have
- [ ] Hot-swapping backends
- [ ] Automatic optimization suggestions
- [ ] GUI configuration tool
- [ ] Real-time sync between backends

## Timeline Summary
- **Week 1**: Foundation & SQLite adapter
- **Week 2**: PostgreSQL implementation
- **Week 3**: Integration & testing
- **Total**: 3 weeks for MVP, 5 weeks for full implementation

## Next Steps
1. Complete SQLite backend adapter
2. Set up PostgreSQL test environment
3. Begin PostgreSQL implementation
4. Create integration tests

## Critical Issues Identified & Solutions

### Issue 1: ChromaDB Vector Store Compatibility
**Problem**: ChromaDB may have different behavior with PostgreSQL backend
**Solution**: Keep ChromaDB separate, only migrate textual/metadata storage

### Issue 2: Multiple Database Dependencies
**Problem**: ChaChaNotes_DB, Prompts_DB, and Evaluations_DB also use SQLite
**Solution**: Phase approach - start with Media_DB_v2, then migrate others

### Issue 3: FTS5 Ranking Functions
**Problem**: SQLite's BM25 ranking differs from PostgreSQL's ts_rank
**Solution**: Implement ranking normalization layer to ensure consistent results

### Issue 4: Concurrent Testing
**Problem**: Running tests against both backends simultaneously may cause conflicts
**Solution**: Use separate test databases with unique names/schemas

## Open Questions
1. Should we support MySQL/MariaDB in the future?
   - **Decision**: Not in initial implementation, architecture allows future addition
2. How to handle PostgreSQL-specific features (arrays, JSON)?
   - **Decision**: Use feature flags, graceful degradation for SQLite
3. Should we use SQLAlchemy Core for abstraction?
   - **Decision**: No, maintain lightweight custom abstraction for better control
4. Connection pool library preference (psycopg2 vs SQLAlchemy)?
   - **Decision**: psycopg2-pool for simplicity, can migrate later if needed

## Change Log
- 2024-01-XX: Initial plan created
- 2024-01-XX: Created base abstraction classes (backends/base.py)
- 2024-01-XX: Implemented SQLite backend adapter (backends/sqlite_backend.py)
- 2024-01-XX: Created backend factory with env/config support (backends/factory.py)
- 2024-01-XX: Identified critical issues and solutions
- 2024-01-XX: Implemented PostgreSQL backend adapter (backends/postgresql_backend.py)
- 2024-01-XX: Created FTS query translator with rank normalization (backends/fts_translator.py)
- [Updates will be added as implementation progresses]

## Completed Components

### Database Abstraction Layer ✅
- **base.py**: Defines `DatabaseBackend` abstract class with all required methods
- **Features**: Connection pooling, transactions, FTS, schema management, data migration

### SQLite Backend ✅
- **sqlite_backend.py**: Complete SQLite implementation maintaining current behavior
- **Features**: Thread-local connections, FTS5 support, WAL mode, all optimizations

### PostgreSQL Backend ✅
- **postgresql_backend.py**: Full PostgreSQL implementation with feature parity
- **Features**: Connection pooling, tsvector/tsquery FTS, triggers for FTS updates
- **Note**: Requires psycopg2 installation

### Backend Factory ✅
- **factory.py**: Dynamic backend selection based on configuration
- **Features**: Environment variables, config files, singleton pattern, auto-registration

### FTS Query Translator ✅
- **fts_translator.py**: Bidirectional query translation between FTS5 and tsquery
- **Features**: Query normalization, rank normalization, term extraction
- **Handles**: Phrases, wildcards, proximity, boolean operators

## Next Steps

1. **Integration Phase**:
   - Update Media_DB_v2 to optionally use backend abstraction
   - Modify RAG components to use abstraction layer
   - Update configuration loading

2. **Testing Phase**:
   - Create test suite that runs against both backends
   - Performance benchmarking
   - Migration testing

3. **Documentation Phase**:
   - User guide for backend selection
   - Migration guide
   - Performance tuning guide
