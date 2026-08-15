from src.research.email_validator import validate_email


def test_valid_email():
    result = validate_email("test@gmail.com")
    assert result.status == "valid"


def test_invalid_syntax():
    result = validate_email("not-an-email")
    assert result.status == "invalid"
    assert result.reason == "bad_syntax"


def test_invalid_no_mx():
    result = validate_email("test@this-domain-does-not-exist-xyz123.com")
    assert result.status == "invalid"
    assert result.reason == "no_mx_record"


if __name__ == "__main__":
    test_valid_email()
    test_invalid_syntax()
    test_invalid_no_mx()
    print("All email_validator tests passed.")