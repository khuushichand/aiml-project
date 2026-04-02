from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Evaluations.recipes.dataset_snapshot import (
    build_dataset_content_hash,
)


def test_build_dataset_content_hash_rejects_unsupported_types() -> None:
    with pytest.raises(TypeError, match="not JSON serializable"):
        build_dataset_content_hash(
            {
                "sample_id": "sample-1",
                "created_at": object(),
            }
        )
