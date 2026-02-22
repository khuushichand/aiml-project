from Helper_Scripts.common.model_container_cycle import parse_csv, stop_all_except, swap_containers


def test_parse_csv_splits_and_trims():
    assert parse_csv(" llm , tts ,, redis ") == ["llm", "tts", "redis"]


def test_stop_all_except_uses_exclusion_list(monkeypatch):
    stopped: list[str] = []

    monkeypatch.setattr(
        "Helper_Scripts.common.model_container_cycle.list_running_containers",
        lambda: ["llm", "tts", "redis"],
    )
    monkeypatch.setattr(
        "Helper_Scripts.common.model_container_cycle.stop_container",
        lambda name, dry_run=False: stopped.append(name),
    )

    stop_all_except(["redis"])
    assert stopped == ["llm", "tts"]


def test_swap_containers_orders_operations(monkeypatch):
    calls: list[tuple] = []

    monkeypatch.setattr(
        "Helper_Scripts.common.model_container_cycle.stop_all_except",
        lambda excluded, dry_run=False: calls.append(("stop_all_except", tuple(excluded), dry_run)),
    )
    monkeypatch.setattr(
        "Helper_Scripts.common.model_container_cycle.start_container",
        lambda name, boot_wait=0.0, dry_run=False: calls.append(("start", name, boot_wait, dry_run)),
    )
    monkeypatch.setattr(
        "Helper_Scripts.common.model_container_cycle.stop_container",
        lambda name, dry_run=False: calls.append(("stop", name, dry_run)),
    )

    swap_containers(
        first_container="llm",
        second_container="tts",
        excluded=["postgres", "redis"],
        first_boot_wait=3.0,
        second_boot_wait=5.0,
        dry_run=False,
    )

    assert calls == [
        ("stop_all_except", ("postgres", "redis"), False),
        ("start", "llm", 3.0, False),
        ("stop", "llm", False),
        ("start", "tts", 5.0, False),
    ]
