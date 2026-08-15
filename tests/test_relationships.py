"""
Verifies foreign keys and relationships work correctly across
the newly added tables.
"""

from src.db.session import SessionLocal, init_db
from src.db.models import Lead, Campaign, CampaignTemplate, SenderAccount, EmailEvent


def test_relationships():
    init_db()
    session = SessionLocal()

    # Reuse the lead created in Phase 1's first test, or create one if missing
    lead = session.query(Lead).filter(Lead.business_name == "ABC Plumbing").first()
    assert lead is not None, "Run tests/test_models.py first to create the test lead"

    campaign = Campaign(name="HVAC Q1", niche="plumbing", status="ACTIVE")
    session.add(campaign)
    session.commit()

    template = CampaignTemplate(
        campaign_id=campaign.id,
        variant="pixel_missing",
        body="Hi {business_name} team, noticed you might be missing Meta Pixel...",
    )
    session.add(template)
    session.commit()

    sender = SenderAccount(
        email="marketingwithusman9@gmail.com", provider="gmail", daily_limit=50
    )
    session.add(sender)
    session.commit()

    event = EmailEvent(
        lead_id=lead.id,
        campaign_id=campaign.id,
        sender_account_id=sender.id,
        event_type="SENT",
        template_used_id=template.id,
    )
    session.add(event)
    session.commit()

    # Test the relationship navigation, not just raw inserts
    fetched_lead = session.query(Lead).filter(Lead.id == lead.id).first()
    assert len(fetched_lead.email_events) == 1
    assert fetched_lead.email_events[0].event_type == "SENT"
    assert fetched_lead.email_events[0].template_used.variant == "pixel_missing"

    session.close()
    print("test_relationships passed — foreign keys and relationships working correctly.")


if __name__ == "__main__":
    test_relationships()