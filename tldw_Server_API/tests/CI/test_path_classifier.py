from Helper_Scripts.ci.path_classifier import classify_paths


def test_ui_only_change_disables_backend_and_coverage() -> None:
    flags = classify_paths(
        [
            "apps/tldw-frontend/src/app/page.tsx",
            "apps/packages/ui/src/components/Option/Playground/Foo.tsx",
        ]
    )
    assert flags["backend_changed"] is False
    assert flags["coverage_required"] is False
    assert flags["frontend_changed"] is True
    assert flags["tldw_frontend_changed"] is True
    assert flags["admin_ui_changed"] is False
    assert flags["e2e_changed"] is True


def test_admin_ui_change_enables_frontend_without_e2e() -> None:
    flags = classify_paths(
        [
            "admin-ui/app/monitoring/page.tsx",
            "admin-ui/lib/api-client.ts",
        ]
    )
    assert flags["frontend_changed"] is True
    assert flags["admin_ui_changed"] is True
    assert flags["tldw_frontend_changed"] is False
    assert flags["e2e_changed"] is False


def test_api_schema_change_enables_e2e() -> None:
    flags = classify_paths(
        [
            "tldw_Server_API/app/api/v1/endpoints/chat.py",
            "tldw_Server_API/app/api/v1/schemas/chat.py",
        ]
    )
    assert flags["backend_changed"] is True
    assert flags["coverage_required"] is True
    assert flags["e2e_changed"] is True


def test_workflow_only_change_keeps_backend_gate_but_skips_coverage() -> None:
    flags = classify_paths(
        [
            ".github/workflows/e2e-required.yml",
        ]
    )
    assert flags["backend_changed"] is True
    assert flags["coverage_required"] is False


def test_emitter_writes_github_output(tmp_path, monkeypatch) -> None:
    out = tmp_path / "github_output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))

    from Helper_Scripts.ci.emit_ci_gate_flags import emit

    emit(["apps/tldw-frontend/src/app/page.tsx"])
    text = out.read_text(encoding="utf-8")
    assert "frontend_changed=true" in text
    assert "backend_changed=false" in text
