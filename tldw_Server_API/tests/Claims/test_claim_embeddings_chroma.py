import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
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
            pass
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
        try:
            shutil.rmtree(base_dir, ignore_errors=True)
        except Exception:
            pass
