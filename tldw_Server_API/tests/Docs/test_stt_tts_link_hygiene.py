from pathlib import Path


def test_readme_tts_onboarding_path_points_to_webui_extension() -> None:
    text = Path("README.md").read_text()
    assert "Docs/User_Guides/WebUI_Extension/Getting-Started-STT_and_TTS.md" in text
    assert "Docs/User_Guides/WebUI_Extension/TTS_Getting_Started.md" in text
    assert "Docs/User_Guides/WebUI_Extension/TTS-SETUP-GUIDE.md" in text
    assert "Docs/User_Guides/TTS_Getting_Started.md" not in text


def test_tts_getting_started_avoids_legacy_absolute_docs_links() -> None:
    legacy_stt_tts = "https://github.com/rmusser01/tldw_server/blob/main/Docs/Getting-Started-STT_and_TTS.md"
    legacy_stt_tts_runbooks = "https://github.com/rmusser01/tldw_server/blob/main/Docs/STT-TTS/"
    for path in [
        "Docs/User_Guides/WebUI_Extension/TTS_Getting_Started.md",
        "Docs/Published/User_Guides/WebUI_Extension/TTS_Getting_Started.md",
    ]:
        text = Path(path).read_text()
        assert legacy_stt_tts not in text
        assert legacy_stt_tts_runbooks not in text
        assert "./Getting-Started-STT_and_TTS.md" in text
