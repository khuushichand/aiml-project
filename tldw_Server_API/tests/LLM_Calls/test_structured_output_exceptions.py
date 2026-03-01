import pytest

from tldw_Server_API.app.core.LLM_Calls.structured_output import (
    StructuredOutputNoPayloadError,
    StructuredOutputParseError,
    StructuredOutputSchemaError,
    extract_items,
    parse_structured_output,
)
from tldw_Server_API.app.core.exceptions import (
    StructuredOutputNoPayloadError as CoreStructuredOutputNoPayloadError,
    StructuredOutputParseError as CoreStructuredOutputParseError,
    StructuredOutputSchemaError as CoreStructuredOutputSchemaError,
)


def test_structured_output_exceptions_are_centralized():
    assert StructuredOutputParseError is CoreStructuredOutputParseError  # nosec B101
    assert StructuredOutputNoPayloadError is CoreStructuredOutputNoPayloadError  # nosec B101
    assert StructuredOutputSchemaError is CoreStructuredOutputSchemaError  # nosec B101


def test_structured_output_raises_centralized_exceptions():
    with pytest.raises(CoreStructuredOutputNoPayloadError):
        parse_structured_output(None)

    with pytest.raises(CoreStructuredOutputSchemaError):
        extract_items("not a list or object", strict=True)
