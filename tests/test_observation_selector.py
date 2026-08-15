from src.personalization.observation_selector import select_observations
from src.research.website_analyzer import WebsiteFacts


def test_selects_observations_from_facts():
    facts = WebsiteFacts(
        fetch_succeeded=True,
        title="ABC Plumbing - Houston's Trusted Plumber",
        meta_description="24/7 emergency plumbing services in Houston, TX.",
        headings=["Emergency Plumbing Services", "Free Estimates"],
        has_emergency_language=True,
        cta_texts=["Book Now"],
    )
    observations = select_observations(facts)
    assert isinstance(observations, list)
    assert len(observations) <= 2
    for obs in observations:
        assert isinstance(obs, str)


def test_returns_empty_when_fetch_failed():
    facts = WebsiteFacts(fetch_succeeded=False)
    observations = select_observations(facts)
    assert observations == []


if __name__ == "__main__":
    test_selects_observations_from_facts()
    test_returns_empty_when_fetch_failed()
    print("All observation_selector tests passed.")