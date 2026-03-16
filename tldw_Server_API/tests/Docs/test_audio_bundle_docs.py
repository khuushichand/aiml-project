from Helper_Scripts.generate_audio_bundle_docs import generate_bundle_docs_text


def test_generated_bundle_docs_reference_all_v1_bundle_ids() -> None:
    content = generate_bundle_docs_text()

    assert "cpu_local" in content
    assert "apple_silicon_local" in content
    assert "nvidia_local" in content
    assert "hosted_plus_local_backup" in content
    assert "Offline runtime after provisioning" in content
    assert "Guided prerequisites" in content
    assert "Default STT" in content
    assert "Default TTS" in content
