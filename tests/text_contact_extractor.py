from src.research.contact_extractor import extract_contact_name


def test_extracts_name_with_owner_context():
    html = "<p>Founded by owner: John Smith in 2005.</p>"
    assert extract_contact_name(html) == "John Smith"


def test_returns_none_when_no_context():
    html = "<p>We are a family business serving Houston since 1998.</p>"
    assert extract_contact_name(html) is None


if __name__ == "__main__":
    test_extracts_name_with_owner_context()
    test_returns_none_when_no_context()
    print("All contact_extractor tests passed.")