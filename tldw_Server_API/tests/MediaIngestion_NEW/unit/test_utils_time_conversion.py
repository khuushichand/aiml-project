import pytest

from tldw_Server_API.app.core.Utils.Utils import convert_to_seconds


@pytest.mark.unit
@pytest.mark.parametrize(
    "input_value, expected",
    [
        ("30", 30),
        ("1.5", 2),
        ("00:03:15.5", 196),
        ("1:02:03.4", 3723),
        ("  45.49  ", 45),
    ],
)
def test_convert_to_seconds_accepts_decimal_inputs(input_value, expected):
    assert convert_to_seconds(input_value) == expected


@pytest.mark.unit
def test_convert_to_seconds_rejects_negative_values():
    with pytest.raises(ValueError):
        convert_to_seconds("-1")


@pytest.mark.unit
def test_convert_to_seconds_rejects_invalid_format():
    with pytest.raises(ValueError):
        convert_to_seconds("1:2:3:4")
