import pytest


def test_sqlite_to_postgres_handles_hyphens_and_near():
    from tldw_Server_API.app.core.DB_Management.backends.fts_translator import FTSQueryTranslator

    # hyphenated word with wildcard
    q1 = "state-of-the-art*"
    out1 = FTSQueryTranslator.sqlite_to_postgres(q1)
    # Ensure wildcard is converted and hyphens preserved
    assert ":*" in out1
    assert "state-of-the-art" in out1

    # NEAR operator with hyphens
    q2 = "alpha-beta NEAR gamma-delta"
    out2 = FTSQueryTranslator.sqlite_to_postgres(q2)
    assert "<->" in out2
    assert "alpha-beta" in out2 and "gamma-delta" in out2


def test_sqlite_to_postgres_handles_quotes_and_parentheses():
    from tldw_Server_API.app.core.DB_Management.backends.fts_translator import FTSQueryTranslator

    q = '"exact phrase" (bonus)'
    out = FTSQueryTranslator.sqlite_to_postgres(q)
    # Phrase converted to parentheses and ANDs for spaces
    assert "(" in out and ")" in out
    assert "<->" in out or "&" in out


def test_fts_query_builder_hyphen_and_unicode():
    from tldw_Server_API.app.core.RAG.rag_service.database_retrievers import MediaDBRetriever
    r = MediaDBRetriever(db_path="/tmp/test.db")  # path used for constructing object only

    q1 = "state-of-the-art models"
    built1 = r._build_fts_query(q1)
    # Should be quoted phrase
    assert built1.startswith('"') and built1.endswith('"')

    q2 = "naïve café"
    built2 = r._build_fts_query(q2)
    assert built2.startswith('"') and built2.endswith('"')
