from __future__ import annotations

import re
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


PROTOCOL_MARKER_KEY = "protocol_version"
LEGACY_SKILL_MARKER = "protocol-version:"
LEGACY_PROMPT_MARKER = "### PROTOCOL_VERSION ###"

BUILTIN_SKILL_PATH = (
    _repo_root()
    / "tldw_Server_API"
    / "app"
    / "core"
    / "Skills"
    / "builtin"
    / "feynman-technique"
    / "SKILL.md"
)
IMPORTABLE_TEMPLATE_PATH = (
    _repo_root() / "Docs" / "Prompts" / "Skills" / "feynman-technique-template" / "SKILL.md"
)
PROMPT_TEMPLATE_PATH = (
    _repo_root() / "Docs" / "Prompts" / "Academic-or-Studying" / "Feynman_Technique.md"
)


def _extract_protocol_version(content: str, source_label: str) -> str:
    match = re.search(r"(?mi)^protocol_version:\s*['\"]?([a-z0-9._-]+)['\"]?\s*$", content)
    assert match is not None, f"Missing '{PROTOCOL_MARKER_KEY}' marker in {source_label}"  # nosec B101
    return match.group(1)


def _assert_legacy_markers_absent(content: str, source_label: str) -> None:
    assert LEGACY_SKILL_MARKER not in content, (  # nosec B101
        f"Legacy marker '{LEGACY_SKILL_MARKER}' still present in {source_label}"
    )
    assert LEGACY_PROMPT_MARKER not in content, (  # nosec B101
        f"Legacy marker '{LEGACY_PROMPT_MARKER}' still present in {source_label}"
    )


def _assert_supporting_files_flat(skill_file: Path) -> None:
    skill_dir = skill_file.parent
    entries = [p for p in skill_dir.iterdir() if p.name != "SKILL.md"]
    nested_dirs = [p.name for p in entries if p.is_dir()]
    assert not nested_dirs, (  # nosec B101
        f"Expected flat supporting-file layout in {skill_dir}, "
        f"but found nested directories: {nested_dirs}"
    )


def test_feynman_assets_exist() -> None:
    assert BUILTIN_SKILL_PATH.exists(), f"Missing built-in skill file: {BUILTIN_SKILL_PATH}"  # nosec B101
    assert IMPORTABLE_TEMPLATE_PATH.exists(), f"Missing importable template file: {IMPORTABLE_TEMPLATE_PATH}"  # nosec B101
    assert PROMPT_TEMPLATE_PATH.exists(), f"Missing prompt template file: {PROMPT_TEMPLATE_PATH}"  # nosec B101


def test_feynman_protocol_version_synced_between_skill_and_prompt_assets() -> None:
    built_in_content = BUILTIN_SKILL_PATH.read_text(encoding="utf-8")
    importable_content = IMPORTABLE_TEMPLATE_PATH.read_text(encoding="utf-8")
    prompt_content = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")

    _assert_legacy_markers_absent(built_in_content, "built-in SKILL.md")
    _assert_legacy_markers_absent(importable_content, "importable SKILL.md")
    _assert_legacy_markers_absent(prompt_content, "prompt template")

    built_in_version = _extract_protocol_version(built_in_content, "built-in SKILL.md")
    importable_version = _extract_protocol_version(importable_content, "importable SKILL.md")
    prompt_version = _extract_protocol_version(prompt_content, "prompt template")

    assert built_in_version == importable_version == prompt_version  # nosec B101


def test_feynman_skill_artifacts_keep_supporting_files_flat() -> None:
    _assert_supporting_files_flat(BUILTIN_SKILL_PATH)
    _assert_supporting_files_flat(IMPORTABLE_TEMPLATE_PATH)
