from pathlib import Path

import yaml


def test_published_has_same_profile_pages_as_manifest() -> None:
    manifest = yaml.safe_load(Path("Docs/Getting_Started/onboarding_manifest.yaml").read_text())
    for _, meta in manifest["profiles"].items():
        published = Path("Docs/Published") / meta["published_path"]
        assert published.exists(), f"Missing published mirror: {published}"
