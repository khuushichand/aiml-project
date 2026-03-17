import os
import shutil
import tempfile
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from tldw_Server_API.app.core.Claims_Extraction import ingestion_claims
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.Embeddings import ChromaDB_Library as cdl
from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import ChromaDBManager


def test_optional_claim_embeddings_with_chroma(monkeypatch):


     # Enable flags
    from tldw_Server_API.app.core.config import settings as app_settings
    orig_enable = app_settings.get("ENABLE_INGESTION_CLAIMS")
    orig_embed = app_settings.get("CLAIMS_EMBED")
    try:
        app_settings["ENABLE_INGESTION_CLAIMS"] = True
        app_settings["CLAIMS_EMBED"] = True

        # Temp DB with a media row
        temp_dir = tempfile.mkdtemp(prefix="claims_embed_")
        db_path = os.path.join(temp_dir, "media.db")
        db = MediaDatabase(db_path=db_path, client_id="test_client")
        db.initialize_db()
        content = "Python 3.11 was released in 2022. It includes performance improvements."
        media_id, _, _ = db.add_media_with_keywords(title="Py", media_type="text", content=content, keywords=None)

        # Patch embeddings and chroma collection
        with patch('tldw_Server_API.app.core.Embeddings.ChromaDB_Library.create_embeddings_batch') as mock_embeds:
            mock_embeds.return_value = [[0.1, 0.2, 0.3]]
            mock_coll = MagicMock()
            mock_client = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_coll

            # Create manager with mocked client via constructor injection
            base_dir = tempfile.mkdtemp(prefix="chroma_user_base_")
            manager = ChromaDBManager(
                user_id="test_user",
                user_embedding_config={
                    "USER_DB_BASE_DIR": base_dir,
                    "embedding_config": {"default_model_id": "unused", "models": {}},
                    # Avoid persistent client in this unit test
                    "chroma_client_settings": {"backend": "stub"},
                },
                client=mock_client,
            )
            manager.db_path = db_path

            # Run with embeddings off to skip doc embedding, but claim embedding on via flag
            manager.process_and_store_content(
                content=content,
                media_id=media_id,
                file_name="py.txt",
                create_embeddings=False,
            )

            # Assert claim embeddings upserted into collection
            assert mock_client.get_or_create_collection.called
            assert mock_coll.upsert.called
    finally:
        # Restore flags
        if orig_enable is not None:
            app_settings["ENABLE_INGESTION_CLAIMS"] = orig_enable
        if orig_embed is not None:
            app_settings["CLAIMS_EMBED"] = orig_embed
        # Cleanup temp resources
        try:
            db.close_connection()
        except Exception:
            _ = None
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            _ = None
        try:
            shutil.rmtree(base_dir, ignore_errors=True)
        except Exception:
            _ = None


def test_ingestion_claim_store_uses_managed_media_database(monkeypatch):
    from tldw_Server_API.app.core.config import settings as app_settings

    orig_enable = app_settings.get("ENABLE_INGESTION_CLAIMS")
    orig_embed = app_settings.get("CLAIMS_EMBED")
    orig_server_client_id = app_settings.get("SERVER_CLIENT_ID")
    base_dir = tempfile.mkdtemp(prefix="claims_embed_base_")

    captured = {}
    sentinel_db = object()

    try:
        app_settings["ENABLE_INGESTION_CLAIMS"] = True
        app_settings["CLAIMS_EMBED"] = False
        app_settings["SERVER_CLIENT_ID"] = "claims-server-client"

        mock_coll = MagicMock()
        mock_coll.name = "claims-test"
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_coll

        manager = ChromaDBManager(
            user_id="test_user",
            user_embedding_config={
                "USER_DB_BASE_DIR": base_dir,
                "embedding_config": {"default_model_id": "unused", "models": {}},
                "chroma_client_settings": {"backend": "stub"},
            },
            client=mock_client,
        )
        manager.db_path = "/tmp/claims-ingest-media.db"

        monkeypatch.setattr(
            cdl,
            "chunk_for_embedding",
            lambda *_args, **_kwargs: [
                {
                    "text": "Python 3.11 was released in 2022.",
                    "metadata": {"chunk_index": 0},
                }
            ],
        )

        @contextmanager
        def _fake_managed_media_database(client_id, **kwargs):
            captured["client_id"] = client_id
            captured.update(kwargs)
            yield sentinel_db

        monkeypatch.setattr(cdl, "managed_media_database", _fake_managed_media_database)
        monkeypatch.setattr(
            ingestion_claims,
            "extract_claims_for_chunks",
            lambda chunks, **_kwargs: [{"chunk_index": 0, "claim_text": "Python 3.11 was released in 2022."}],
        )

        def _fake_store_claims(db, **kwargs):
            captured["store_claims_db"] = db
            captured["store_claims_kwargs"] = kwargs
            return 1

        monkeypatch.setattr(ingestion_claims, "store_claims", _fake_store_claims)

        manager.process_and_store_content(
            content="Python 3.11 was released in 2022.",
            media_id=123,
            file_name="claims.txt",
            create_embeddings=False,
        )

        assert captured["client_id"] == "claims-server-client"
        assert captured["db_path"] == "/tmp/claims-ingest-media.db"
        assert captured["initialize"] is False
        assert captured["suppress_close_exceptions"] is cdl._CHROMA_NONCRITICAL_EXCEPTIONS
        assert captured["store_claims_db"] is sentinel_db
        assert captured["store_claims_kwargs"]["media_id"] == 123
    finally:
        if orig_enable is not None:
            app_settings["ENABLE_INGESTION_CLAIMS"] = orig_enable
        else:
            app_settings.pop("ENABLE_INGESTION_CLAIMS", None)
        if orig_embed is not None:
            app_settings["CLAIMS_EMBED"] = orig_embed
        else:
            app_settings.pop("CLAIMS_EMBED", None)
        if orig_server_client_id is not None:
            app_settings["SERVER_CLIENT_ID"] = orig_server_client_id
        else:
            app_settings.pop("SERVER_CLIENT_ID", None)
        shutil.rmtree(base_dir, ignore_errors=True)
