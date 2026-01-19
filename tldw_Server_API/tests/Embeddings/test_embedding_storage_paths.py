from pathlib import Path

import pytest

from tldw_Server_API.app.core.Embeddings.Embeddings_Server import Embeddings_Create as EC
from tldw_Server_API.app.core.exceptions import InvalidStoragePathError


def test_model_storage_base_dir_requires_allowlist_root():
    allow_root = EC._EMBEDDINGS_STORAGE_ALLOWLIST_ROOT
    candidate = allow_root / "embedding_models_data"

    normalized = EC._normalize_model_storage_base_dir(str(candidate))
    assert normalized == str(Path(candidate).resolve(strict=False))

    invalid_abs = allow_root.parent / "outside_models"
    with pytest.raises(InvalidStoragePathError):
        EC._normalize_model_storage_base_dir(str(invalid_abs))

    with pytest.raises(InvalidStoragePathError):
        EC._normalize_model_storage_base_dir("../outside_models")


def test_model_storage_subdir_rejects_traversal():
    allow_root = EC._EMBEDDINGS_STORAGE_ALLOWLIST_ROOT
    base_dir = EC._normalize_model_storage_base_dir(str(allow_root / "embedding_models_data"))

    resolved = EC._safe_model_storage_subdir(base_dir, "hf_cache", "hf_cache_dir_subpath")
    assert Path(resolved).resolve(strict=False).is_relative_to(
        Path(base_dir).resolve(strict=False)
    )

    with pytest.raises(InvalidStoragePathError):
        EC._safe_model_storage_subdir(base_dir, "../escape", "hf_cache_dir_subpath")

    with pytest.raises(InvalidStoragePathError):
        EC._safe_model_storage_subdir(base_dir, "/abs/escape", "hf_cache_dir_subpath")
