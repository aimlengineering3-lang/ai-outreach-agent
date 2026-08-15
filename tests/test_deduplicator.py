from src.discovery.deduplicator import is_likely_duplicate, normalize_domain, name_similarity


def test_domain_match():
    result = is_likely_duplicate(
        "ABC Plumbing LLC", "https://www.abcplumbing.com/", "Houston",
        "ABC Plumbing", "http://abcplumbing.com", "Houston",
    )
    assert result.is_duplicate is True
    assert result.reason == "domain_match"


def test_same_name_different_city_not_duplicate():
    result = is_likely_duplicate(
        "ABC Plumbing", None, "Houston",
        "ABC Plumbing", None, "Dallas",
    )
    assert result.is_duplicate is False


def test_different_businesses_not_duplicate():
    result = is_likely_duplicate(
        "ABC Plumbing", "https://abcplumbing.com", "Houston",
        "Elite HVAC Services", "https://elitehvac.com", "Houston",
    )
    assert result.is_duplicate is False


def test_normalize_domain():
    assert normalize_domain("https://www.abcplumbing.com/") == "abcplumbing.com"
    assert normalize_domain("abcplumbing.com") == "abcplumbing.com"
    assert normalize_domain(None) is None


if __name__ == "__main__":
    test_domain_match()
    test_same_name_different_city_not_duplicate()
    test_different_businesses_not_duplicate()
    test_normalize_domain()
    print("All deduplicator tests passed.")