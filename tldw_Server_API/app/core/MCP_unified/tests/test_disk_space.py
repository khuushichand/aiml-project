from collections import namedtuple

import pytest

import tldw_Server_API.app.core.MCP_unified.modules.disk_space as disk_space_module
from tldw_Server_API.app.core.MCP_unified.modules.disk_space import get_free_disk_space_gb


def test_get_free_disk_space_gb_uses_statvfs(monkeypatch):
    statvfs_result = namedtuple("statvfs_result", ["f_bavail", "f_frsize"])
    monkeypatch.setattr(
        disk_space_module.os,
        "statvfs",
        lambda _path: statvfs_result(1024, 4096),
    )

    free_gb = get_free_disk_space_gb("/tmp")

    assert free_gb == pytest.approx((1024 * 4096) / (1024 ** 3))


def test_get_free_disk_space_gb_falls_back_to_disk_usage(monkeypatch):
    usage_result = namedtuple("usage_result", ["total", "used", "free"])

    def _raise_attr_error(_path):
        raise AttributeError("statvfs unavailable")

    monkeypatch.setattr(disk_space_module.os, "statvfs", _raise_attr_error)
    monkeypatch.setattr(
        disk_space_module.shutil,
        "disk_usage",
        lambda _path: usage_result(100, 40, 60 * (1024 ** 3)),
    )

    free_gb = get_free_disk_space_gb("C:/temp")

    assert free_gb == pytest.approx(60.0)
