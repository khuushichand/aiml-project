EXPECTED_EMPTY_INPUT_CONTRACT = {
    "/api/v1/media/process-videos": (
        400,
        "No valid media sources supplied",
    ),
    "/api/v1/media/process-audios": (
        400,
        "No valid media sources supplied",
    ),
    "/api/v1/media/process-pdfs": (
        400,
        "No valid media sources supplied",
    ),
    "/api/v1/media/process-documents": (
        400,
        "At least one 'url' in the 'urls' list or one 'file' in the 'files' list must be provided.",
    ),
    "/api/v1/media/process-ebooks": (
        400,
        "At least one 'url' in the 'urls' list or one 'file' in the 'files' list must be provided.",
    ),
    "/api/v1/media/process-emails": (
        400,
        "At least one EML file must be uploaded.",
    ),
}


def test_empty_input_contract_matrix_includes_all_target_endpoints():
    assert set(EXPECTED_EMPTY_INPUT_CONTRACT.keys()) == {
        "/api/v1/media/process-videos",
        "/api/v1/media/process-audios",
        "/api/v1/media/process-pdfs",
        "/api/v1/media/process-documents",
        "/api/v1/media/process-ebooks",
        "/api/v1/media/process-emails",
    }


def test_empty_input_contract_matrix_values_are_non_empty():
    for endpoint, (status_code, detail_fragment) in EXPECTED_EMPTY_INPUT_CONTRACT.items():
        assert endpoint.startswith("/api/v1/media/process-")
        assert status_code == 400
        assert isinstance(detail_fragment, str) and detail_fragment.strip()

