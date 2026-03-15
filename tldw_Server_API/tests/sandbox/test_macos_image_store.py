from __future__ import annotations

from pathlib import Path

from tldw_Server_API.app.core.Sandbox.image_store import SandboxImageStore


def test_image_store_returns_run_clone_manifest_for_template(tmp_path: Path) -> None:
    store = SandboxImageStore(root_path=tmp_path)
    template_id = store.register_template(
        runtime="vz_linux",
        template_name="ubuntu-24.04",
        disk_paths=["/templates/ubuntu-24.04.img"],
    )

    manifest = store.prepare_run_clone(template_id=template_id, run_id="run-123")

    assert manifest.template_id == template_id
    assert manifest.run_id == "run-123"
    assert manifest.clone_items[0].source_path.endswith(".img")
    assert manifest.clone_items[0].mode == "clone"
