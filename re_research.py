from src.db.session import SessionLocal
from src.db.models import Lead
from app.run_agent import research_lead

s = SessionLocal()
no_email_leads = s.query(Lead).filter(Lead.status == "RESEARCHED", Lead.email.is_(None)).all()
print(f"Re-researching {len(no_email_leads)} lead(s) with no email...")

found_count = 0
for lead in no_email_leads:
    old_email = lead.email
    research_lead(s, lead)
    if lead.email and lead.email != old_email:
        found_count += 1
        print(f"  FOUND: {lead.business_name} -> {lead.email}")

print(f"Done. Found {found_count} new email(s) out of {len(no_email_leads)}.")