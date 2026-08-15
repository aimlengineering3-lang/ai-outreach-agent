"""
Basic sanity test: can we create a Lead, save it, and read it back?
"""

from src.db.session import SessionLocal, init_db
from src.db.models import Lead


def test_create_and_read_lead():
    init_db()  # ensure tables exist
    session = SessionLocal()

    new_lead = Lead(
        business_name="ABC Plumbing",
        niche="plumbing",
        city="Houston",
        state="TX",
        timezone="America/Chicago",
        source="manual",
    )
    session.add(new_lead)
    session.commit()

    fetched = session.query(Lead).filter(Lead.business_name == "ABC Plumbing").first()

    assert fetched is not None
    assert fetched.city == "Houston"
    assert fetched.contact_name is None  # confirms no name was fabricated

    session.close()
    print("test_create_and_read_lead passed:", fetched)


if __name__ == "__main__":
    test_create_and_read_lead()