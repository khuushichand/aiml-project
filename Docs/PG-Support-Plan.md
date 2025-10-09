# PostgreSQL Support Implementation Plan

## ⚠️ ACTUAL IMPLEMENTATION STATUS ⚠️
- **Integration Progress**: ~92% — MediaDatabase handles schema bootstrap, CRUD flows, and claims FTS/search through the backend abstraction; ChaChaNotes (including PostgreSQL FTS rebuild/search) and analytics feedback services now run on the shared backend; remaining SQLite-only utilities are limited to legacy maintenance jobs and schema migrations that still target SQLite semantics.
- **Functional PostgreSQL Support**: Partial — Postgres schema creation runs cleanly for Media, ChaChaNotes, and Analytics; CRUD/FTS paths execute via backend adapters; the migration utility copies SQLite content/ChaCha/analytics data into Postgres and resyncs sequences; DB_Manager factories prefer shared SQL backends, while media FTS maintenance triggers and upgrade migrations still require PostgreSQL implementations and live regression coverage.
- **Tests Written**: Unit coverage now includes ChaChaNotes PostgreSQL FTS flows plus dual-backend smoke tests for Media/analytics and the migration tooling (see `test_media_postgres_support.py`, `test_analytics_backend.py`, `test_migration_tools.py`); dual-backend integration suite still outstanding.
- **Files Created**: Backend modules and MediaDatabase refactor (tracked in repo).
- **Git Status**: Backend factory + content database wiring checked in; ongoing edits confined to Media_DB_v2/ChaChaNotes.
- **Dependencies**: psycopg2-binary enabled in `requirements.txt`; ensure environments install it before switching to Postgres.
- **Configuration**: Backend selection flows through `content_backend.py` and env/config plumbing; see `Docs/Deployment/Postgres_Migration_Guide.md` for rollout examples.
- **Main Issue**: Remaining blockers include vector/hybrid regressions that need live Postgres validation, production performance hardening, and broader end-to-end coverage before declaring parity.

## Executive Summary
This document outlines the plan to add PostgreSQL support to the tldw_server RAG system while maintaining full SQLite compatibility. The implementation will allow users to choose their preferred database backend based on their needs.

## Current Status
- ✅ Created database backend abstraction base classes (wired into MediaDatabase)
- ✅ Implemented SQLite backend adapter (actively used via factory)
- ✅ Created backend factory with configuration support (drives content DB selection)
- ✅ Implemented PostgreSQL backend adapter (exercised during schema bootstrap/tests)
- ✅ Created FTS query translator with bidirectional conversion (module implemented; wiring into search flows pending)
- 🔄 Integration with existing code IN PROGRESS (Media_DB_v2 backend parity ~90%; AnalyticsDatabase refactored; ChaChaNotes backend adapters + PostgreSQL bootstrap/migrations + FTS/search/rebuild live; RAG retrievers now invoke backend-aware helpers, leaving only legacy maintenance utilities to port)
- 🔄 Testing framework IN PROGRESS (unit coverage for ChaChaNotes PostgreSQL FTS plus new Media/analytics/migration helpers; a dedicated postgres CI job now runs targeted suites while full end-to-end matrices remain outstanding)
- ✅ Migration tooling INITIAL RELEASE (CLI copies content/ChaCha/analytics SQLite databases into Postgres and resyncs sequences; integration test compares row counts; large dataset dry-runs and automated validation still planned)

**CRITICAL NOTE**: Media_DB_v2 now routes schema setup, metadata search, trash, transcripts, keywords, and chunking templates through the backend abstraction; AnalyticsDatabase also uses the backend layer. ChaChaNotes connection/query execution and schema bootstrap now run on the backend abstraction, but FTS rebuild/search and several maintenance utilities still rely on SQLite-only SQL, and analytics_system helpers remain partially SQLite-bound.

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
└── migration_tools.py   # Data migration utilities ✅
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
**Status**: IN PROGRESS
**Timeline**: Day 8-10

Tasks:
- [x] Build FTS5 to PostgreSQL translator (module exists; integration pending)
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
**Status**: In Progress
**Timeline**: Day 11-14

Tasks:
- [~] Update Media_DB_v2 to use backend abstraction (schema bootstrap + trash/transcript/pagination + keywords/templates now backend-aware; claims/legacy rebuild paths still SQLite-only)
- [ ] Update RAG components (connection_pool.py, database_retrievers.py)
- [x] Update analytics_db.py
- [~] Migrate ChaChaNotes_DB to backend abstraction (connection + query helpers live; PostgreSQL schema migrations + FTS search/rebuild implemented — backup utilities still pending)
- [~] Migrate analytics_system and other analytics helpers to backend-aware calls (core feedback store migrated; legacy analytics utilities still SQLite-bound)
- [ ] Configuration system updates
- [ ] End-to-end testing

### Phase 5: Migration Tools
**Status**: Partial — CLI helper in place for SQLite→Postgres content/ChaCha/analytics migrations (see `migration_tools.py` and Postgres Migration Guide); reverse flows and automated validation remain.  
**Timeline**: Day 15-17

Tasks:
- [x] SQLite to PostgreSQL migrator
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
- [ ] PostgreSQL supports core RAG operations
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
1. Finish ChaChaNotes backend migration (schema bootstrap, CRUD/FTS parity, FTS/backup utilities) and close remaining SQLite guards.
2. Refactor analytics_system and feedback stores to consume AnalyticsDatabase/ChaCha backends instead of raw `sqlite3` connections.
3. Wire Media + ChaCha factories into downstream services (DB_Manager, RAG components) with backend-aware code paths.
4. Stand up dual-backend (SQLite/Postgres) regression tests and enable psycopg dependency/document DSN setup.
5. Draft migration tooling outline (SQLite → Postgres) and capture risk mitigations for data moves.

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
