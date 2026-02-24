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


def test_api_schema_change_enables_e2e() -> None:
    flags = classify_paths(
        [
            "tldw_Server_API/app/api/v1/endpoints/chat.py",
            "tldw_Server_API/app/api/v1/schemas/chat.py",
        ]
    )
    assert flags["backend_changed"] is True
    assert flags["e2e_changed"] is True
