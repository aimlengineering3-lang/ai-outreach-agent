from src.db.session import SessionLocal
from src.db.models import Lead
from src.research.website_analyzer import analyze_website_with_contact_fallback
from src.research.pixel_detector import detect_tech_static

s = SessionLocal()
lead = s.query(Lead).filter(Lead.business_name.ilike("%Dallas Commercial Roofing%")).first()

if not lead:
    print("Lead not found!")
else:
    print(f"Lead: {lead.business_name}")
    print(f"Website: {lead.website}")
    print(f"Current status: {lead.status}")
    print(f"Current email: {lead.email}")
    print("")

    facts = analyze_website_with_contact_fallback(lead.website)
    print(f"fetch_succeeded: {facts.fetch_succeeded}")
    print(f"emails found: {facts.emails}")

    tech = detect_tech_static(lead.website)
    print(f"tech detection succeeded: {tech.fetch_succeeded}")