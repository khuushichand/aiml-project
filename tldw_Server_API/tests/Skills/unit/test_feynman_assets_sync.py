from __future__ import annotations

import re
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


F_KEY = "protocol-version"
PROMPT_KEY = "### PROTOCOL_VERSION ###"

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


def _extract_skill_protocol_version(content: str) -> str:
    match = re.search(r"(?mi)^protocol-version:\s*['\"]?([a-z0-9._-]+)['\"]?\s*$", content)
    assert match is not None, f"Missing '{F_KEY}' marker in SKILL.md frontmatter"  # nosec B101
    return match.group(1)


def _extract_prompt_protocol_version(content: str) -> str:
    marker = re.search(r"(?m)^### PROTOCOL_VERSION ###\s*$", content)
    assert marker is not None, f"Missing '{PROMPT_KEY}' section in prompt template"  # nosec B101

    following = content[marker.end() :].lstrip("\n")
    first_line = following.splitlines()[0].strip() if following else ""
    assert first_line, "Empty protocol version value in prompt template"  # nosec B101
    return first_line


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
    built_in_version = _extract_skill_protocol_version(BUILTIN_SKILL_PATH.read_text(encoding="utf-8"))
    importable_version = _extract_skill_protocol_version(IMPORTABLE_TEMPLATE_PATH.read_text(encoding="utf-8"))
    prompt_version = _extract_prompt_protocol_version(PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8"))

    assert built_in_version == importable_version == prompt_version  # nosec B101


def test_feynman_skill_artifacts_keep_supporting_files_flat() -> None:
    _assert_supporting_files_flat(BUILTIN_SKILL_PATH)
    _assert_supporting_files_flat(IMPORTABLE_TEMPLATE_PATH)
