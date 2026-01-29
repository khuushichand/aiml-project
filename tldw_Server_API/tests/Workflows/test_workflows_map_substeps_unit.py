import asyncio

import pytest

from tldw_Server_API.app.core.Workflows.adapters import run_map_adapter
from tldw_Server_API.app.core.exceptions import AdapterError


pytestmark = pytest.mark.unit


def test_map_adapter_unsupported_substep():
    cfg = {
        "items": [1, 2],
        "step": {"type": "unsupported_step", "config": {}},
    }
    with pytest.raises(AdapterError):
        asyncio.run(run_map_adapter(cfg, {}))
