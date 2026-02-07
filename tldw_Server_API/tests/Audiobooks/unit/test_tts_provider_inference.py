import sys

import pytest

if sys.version_info < (3, 10):
    pytest.skip("Audiobook TTS provider inference tests require Python 3.10+", allow_module_level=True)

from tldw_Server_API.app.services.audiobook_jobs_worker import _infer_tts_provider_from_model


@pytest.mark.parametrize(
    "model_name",
    ["supertonic2", "supertonic2-v1", "supertonic-2", "supertonic-2-v1", "tts-supertonic2-1"],
)
def test_infer_tts_provider_supertonic2_aliases(model_name: str) -> None:
    assert _infer_tts_provider_from_model(model_name) == "supertonic2"
