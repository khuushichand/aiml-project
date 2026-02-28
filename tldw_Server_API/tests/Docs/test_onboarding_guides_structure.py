from pathlib import Path

REQUIRED = ["## Prerequisites", "## Install", "## Run", "## Verify", "## Troubleshoot"]


def test_each_profile_has_required_sections() -> None:
    guides = [
        "Docs/Getting_Started/Profile_Local_Single_User.md",
        "Docs/Getting_Started/Profile_Docker_Single_User.md",
        "Docs/Getting_Started/Profile_Docker_Multi_User_Postgres.md",
    ]
    for guide in guides:
        text = Path(guide).read_text()
        for heading in REQUIRED:
            assert heading in text


def test_gpu_addon_has_prereq_verify_troubleshoot() -> None:
    text = Path("Docs/Getting_Started/GPU_STT_Addon.md").read_text()
    for heading in ["## Prerequisites", "## Verify", "## Troubleshoot"]:
        assert heading in text
