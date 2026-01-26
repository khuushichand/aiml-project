from datetime import datetime, timedelta

import pytest

from tldw_Server_API.app.core.Embeddings.request_signing import NonceManager


@pytest.mark.unit
def test_nonce_cleanup_uses_total_seconds():
    manager = NonceManager(ttl_seconds=1)

    old_nonce = "old"
    manager.used_nonces[old_nonce] = datetime.utcnow() - timedelta(seconds=10)
    manager.last_cleanup = datetime.utcnow() - timedelta(days=2)

    assert manager.is_valid_nonce("new") is True
    assert old_nonce not in manager.used_nonces
