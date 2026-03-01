from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def test_speech_docs_link_hygiene_script_passes() -> None:
    script = Path("Helper_Scripts/docs/check_speech_docs_link_hygiene.py")
    spec = spec_from_file_location("check_speech_docs_link_hygiene", script)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main() == 0
