"""Security-focused tests for scheduler payload service storage formats."""

import json
import pickle
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from ..base.exceptions import PayloadError
from ..config import SchedulerConfig
from ..services.payload_service import PayloadService


@pytest.fixture
def payload_service(tmp_path):
    """Create payload service with small threshold for easier test setup."""
    config = SchedulerConfig(
        database_url=f"sqlite:///{tmp_path}/test.db",
        base_path=tmp_path,
        payload_threshold_bytes=1024,
    )
    return PayloadService(backend=MagicMock(), config=config)


def _write_payload_file(service: PayloadService, payload_ref: str, header: dict, data: bytes) -> None:
    """Write a payload artifact with a valid framing header."""
    path = service.storage_path / payload_ref[:2] / f"{payload_ref}.payload"
    path.parent.mkdir(parents=True, exist_ok=True)
    header_raw = json.dumps(header).encode("utf-8")
    with open(path, "wb") as f:
        f.write(len(header_raw).to_bytes(4, "little"))
        f.write(header_raw)
        f.write(data)


@pytest.mark.asyncio
async def test_store_and_load_payload_json_round_trip(payload_service):
    payload = {"data": "x" * 4096, "tags": ["alpha", "beta"]}

    payload_ref = await payload_service.store_payload("task-1", payload)
    assert payload_ref is not None

    loaded = await payload_service.load_payload(payload_ref)
    assert loaded == payload


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload_ref",
    ["", "../evil", "abc/def", "ZZZZZZZZZZZZZZZZ", "abc", "a" * 65],
)
async def test_load_payload_rejects_malformed_reference(payload_service, payload_ref):
    with pytest.raises(PayloadError, match="Invalid payload reference format"):
        await payload_service.load_payload(payload_ref)


@pytest.mark.asyncio
async def test_load_payload_rejects_unsupported_format(payload_service):
    payload_ref = "a1b2c3d4e5f60789"
    header = {
        "task_id": "task-2",
        "format": "msgpack",
        "compressed": False,
        "size": 2,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_payload_file(payload_service, payload_ref, header, b"{}")

    with pytest.raises(PayloadError, match="Unknown payload format"):
        await payload_service.load_payload(payload_ref)


@pytest.mark.asyncio
async def test_legacy_pickle_payload_disabled_by_default(payload_service):
    payload_ref = "0f1e2d3c4b5a6978"
    legacy_payload = {"legacy": True, "value": 42}
    header = {
        "task_id": "task-legacy",
        "format": "pickle",
        "compressed": False,
        "size": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_payload_file(payload_service, payload_ref, header, pickle.dumps(legacy_payload))

    with pytest.raises(PayloadError, match="Legacy pickle payload loading is disabled"):
        await payload_service.load_payload(payload_ref)


@pytest.mark.asyncio
async def test_legacy_pickle_payload_can_be_loaded_when_compat_enabled(tmp_path):
    config = SchedulerConfig(
        database_url=f"sqlite:///{tmp_path}/test.db",
        base_path=tmp_path,
        payload_threshold_bytes=1024,
        allow_legacy_pickle_payloads=True,
    )
    service = PayloadService(backend=MagicMock(), config=config)

    payload_ref = "1122334455667788"
    legacy_payload = {"legacy": True, "value": 99}
    header = {
        "task_id": "task-legacy-ok",
        "format": "pickle",
        "compressed": False,
        "size": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_payload_file(service, payload_ref, header, pickle.dumps(legacy_payload))

    loaded = await service.load_payload(payload_ref)
    assert loaded == legacy_payload
