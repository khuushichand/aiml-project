## Stage 1: Reproduce And Lock Regressions
**Goal**: Capture the Frieza retrieval miss in automated tests.
**Success Criteria**: Tests fail before implementation for harmful spell correction and typo-shaped late-chunk ranking.
**Tests**:
- `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_quick_wins_spell_check_compat.py -k frieza -v`
- `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_retrieval.py -k frieza -v`
**Status**: Complete

## Stage 2: Harden Retrieval Inputs
**Goal**: Prevent ambiguous spell corrections for corpus/entity names and improve typo tolerance in late-chunk rescoring.
**Success Criteria**: `frieza`/`goku` are not auto-corrected into unrelated terms, and `friezes new form` ranks the Frieza clip first in retrieval tests.
**Tests**:
- `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_quick_wins_spell_check_compat.py -k frieza -v`
- `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_retrieval.py -k frieza -v`
**Status**: Complete

## Stage 3: Verify Touched Scope
**Goal**: Confirm the fix passes targeted tests and introduces no new security findings.
**Success Criteria**: Targeted pytest passes and Bandit reports 0 new findings on touched files.
**Tests**:
- `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_quick_wins_spell_check_compat.py -v`
- `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_retrieval.py -v`
- `python -m bandit -r tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py tldw_Server_API/app/core/RAG/rag_service/quick_wins.py -f json -o /tmp/bandit_knowledge_frieza_retrieval.json`
**Status**: Complete
