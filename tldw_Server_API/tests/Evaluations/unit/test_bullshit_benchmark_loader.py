import json

import pytest

from tldw_Server_API.app.core.Evaluations.benchmark_loaders import (
    BenchmarkDatasetLoader,
    load_benchmark_dataset,
)


def test_load_bullshit_benchmark_flattens_techniques(tmp_path):
    payload = {
        "techniques": [
            {
                "technique": "cross_domain_concept_stitching",
                "description": "stitches unrelated domains",
                "questions": [
                    {
                        "id": "cd_01",
                        "question": "Q?",
                        "nonsensical_element": "N",
                        "domain": "finance × marketing",
                    }
                ],
            }
        ]
    }
    dataset_path = tmp_path / "questions_v2.json"
    dataset_path.write_text(json.dumps(payload), encoding="utf-8")

    rows = BenchmarkDatasetLoader.load_bullshit_benchmark(str(dataset_path))

    assert rows[0]["id"] == "cd_01"
    assert rows[0]["technique"] == "cross_domain_concept_stitching"
    assert rows[0]["nonsensical_element"] == "N"


def test_load_bullshit_benchmark_rejects_missing_required_field(tmp_path):
    payload = {
        "techniques": [
            {
                "technique": "x",
                "questions": [{"id": "cd_01", "question": "Q?", "domain": "x"}],
            }
        ]
    }
    dataset_path = tmp_path / "questions_v2.json"
    dataset_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="nonsensical_element"):
        BenchmarkDatasetLoader.load_bullshit_benchmark(str(dataset_path))


def test_load_benchmark_dataset_maps_bullshit_benchmark(tmp_path):
    payload = {
        "techniques": [
            {
                "technique": "x",
                "questions": [
                    {
                        "id": "x_1",
                        "question": "Q?",
                        "nonsensical_element": "N",
                        "domain": "x",
                    }
                ],
            }
        ]
    }
    dataset_path = tmp_path / "questions_v2.json"
    dataset_path.write_text(json.dumps(payload), encoding="utf-8")

    rows = load_benchmark_dataset(
        "bullshit_benchmark",
        source=str(dataset_path),
        limit=1,
    )
    assert len(rows) == 1
    assert rows[0]["id"] == "x_1"


def test_load_benchmark_dataset_accepts_builtin_source_identifier():
    rows = load_benchmark_dataset(
        "bullshit_benchmark",
        source="builtin://bullshit_benchmark_v2",
        limit=1,
    )

    assert len(rows) == 1
    assert rows[0]["id"]
