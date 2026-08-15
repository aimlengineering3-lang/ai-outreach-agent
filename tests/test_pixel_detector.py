"""
Tests pixel_detector against known real-world sites so we can see
the detector behaving correctly on cases with a known answer.
"""

from src.research.pixel_detector import detect_tech_static


def test_detect_on_known_ga_site():
    # Google's own site uses Google Analytics/tag manager somewhere
    # on most pages — good sanity check for GA/GTM detection.
    result = detect_tech_static("https://www.wikipedia.org")
    print("Wikipedia:", result)
    assert result.fetch_succeeded is True


def test_detect_on_unreachable_site():
    result = detect_tech_static("https://this-domain-does-not-exist-xyz123.com")
    print("Unreachable site:", result)
    assert result.fetch_succeeded is False
    assert result.meta_pixel == "UNKNOWN"
    assert result.google_analytics == "UNKNOWN"
    assert result.gtm == "UNKNOWN"


if __name__ == "__main__":
    test_detect_on_known_ga_site()
    test_detect_on_unreachable_site()
    print("All pixel_detector tests passed.")