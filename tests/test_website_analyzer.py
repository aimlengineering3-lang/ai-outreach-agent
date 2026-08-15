from src.research.website_analyzer import analyze_website


def test_analyze_known_site():
    result = analyze_website("https://www.example.com")
    print(result)
    assert result.fetch_succeeded is True
    assert result.title is not None


def test_analyze_unreachable_site():
    result = analyze_website("https://this-domain-does-not-exist-xyz123.com")
    assert result.fetch_succeeded is False
    assert result.headings == []
    assert result.phone_numbers == []


if __name__ == "__main__":
    test_analyze_known_site()
    test_analyze_unreachable_site()
    print("All website_analyzer tests passed.")