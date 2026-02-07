from tldw_Server_API.app.core.Storage import generated_file_helpers


def test_generate_filename_sanitizes_prefix_and_extension():
    filename = generated_file_helpers._generate_filename("voice/evil name..", "mp3../")
    assert "/" not in filename
    assert "\\" not in filename
    assert " " not in filename
    assert filename.endswith(".mp3")
