from tldw_Server_API.app.core.AuthNZ.input_validation import InputValidator


def test_username_with_confusable_chars_is_accepted():
    validator = InputValidator()
    ok, error = validator.validate_username("alice1")
    assert ok, error

    ok_two, error_two = validator.validate_username("coolguy90")
    assert ok_two, error_two


def test_username_with_repeated_specials_still_rejected():
    validator = InputValidator()
    ok, error = validator.validate_username("foo__bar")
    assert ok is False
    assert "consecutive special characters" in error.lower()
