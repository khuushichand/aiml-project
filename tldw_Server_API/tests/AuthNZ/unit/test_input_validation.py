from tldw_Server_API.app.core.AuthNZ.input_validation import InputValidator


def test_username_with_common_patterns_is_accepted():


     """Common usernames with visually distinct characters should be allowed."""
    validator = InputValidator()
    # 'l' and '1' are visually distinct - allow
    ok, error = validator.validate_username("alice1")
    assert ok, error

    # 'o' and '0' (lowercase o and zero) - one is not uppercase O, allow
    ok_two, error_two = validator.validate_username("coolguy90")
    assert ok_two, error_two

    # Normal names with numbers
    ok_three, error_three = validator.validate_username("user123")
    assert ok_three, error_three


def test_username_with_truly_confusing_chars_is_rejected():


     """Usernames with truly confusing character pairs should be rejected."""
    validator = InputValidator()

    # 'l' (lowercase L) and 'I' (uppercase I) - nearly identical, reject
    ok, error = validator.validate_username("alIce")
    assert ok is False
    assert "confusing" in error.lower()

    # 'O' (uppercase O) and '0' (zero) - very similar, reject
    ok_two, error_two = validator.validate_username("bOb0")
    assert ok_two is False
    assert "confusing" in error_two.lower()


def test_username_with_repeated_specials_still_rejected():


     validator = InputValidator()
    ok, error = validator.validate_username("foo__bar")
    assert ok is False
    assert "consecutive special characters" in error.lower()
