from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session, joinedload

from src.db.models import Lead, EmailEvent
from api.deps import get_db
from api.schemas import LeadOut, LeadCreate, LeadDetailOut, LeadResearchOut, EmailEventOut, NicheStat

router = APIRouter(prefix="/leads", tags=["leads"])

LEADS_PAGE_LIMIT = 500

def _tri_state(value) -> str:
    """bool/None -> PRESENT/MISSING/UNKNOWN, same as the old dashboard's CSV export."""
    return "PRESENT" if value else "MISSING" if value is not None else "UNKNOWN"


@router.get("", response_model=list[LeadOut])
def list_leads(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, description="Matches business name, email, or website"),
    niche: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    has_email: Optional[bool] = Query(None, description="true = Has Email tab, false = Manual Review tab"),
    limit: int = Query(LEADS_PAGE_LIMIT, le=LEADS_PAGE_LIMIT),
):
    q = db.query(Lead).options(joinedload(Lead.research))
    if search:
        q = q.filter(
            (Lead.business_name.ilike(f"%{search}%"))
            | (Lead.email.ilike(f"%{search}%"))
            | (Lead.website.ilike(f"%{search}%"))
        )
    if niche:
        q = q.filter(Lead.niche == niche)
    if city:
        q = q.filter(Lead.city == city)
    if state:
        q = q.filter(Lead.state == state)

    rows = q.order_by(Lead.created_at.desc()).limit(limit).all()

    if has_email is True:
        rows = [l for l in rows if l.email]
    elif has_email is False:
        rows = [l for l in rows if not l.email]

    out = []
    for l in rows:
        out.append(
            LeadOut(
                id=l.id, business_name=l.business_name, niche=l.niche, city=l.city,
                state=l.state, status=l.status, email=l.email, email_status=l.email_status,
                phone=l.phone, contact_name=l.contact_name, website=l.website,
                meta_pixel=(l.research.meta_pixel if l.research else None),
                google_analytics=_tri_state(l.research.google_analytics if l.research else None),
                gtm=_tri_state(l.research.gtm if l.research else None),
                created_at=l.created_at,
            )
        )
    return out


@router.get("/filter-options")
def filter_options(db: Session = Depends(get_db)):
    niches = [n[0] for n in db.query(Lead.niche).distinct().all()]
    cities = sorted(set(c[0] for c in db.query(Lead.city).filter(Lead.city.isnot(None)).distinct().all()))
    states = sorted(set(v[0] for v in db.query(Lead.state).filter(Lead.state.isnot(None)).distinct().all()))
    return {"niches": niches, "cities": cities, "states": states}


@router.get("/niche-stats", response_model=list[NicheStat])
def niche_stats(db: Session = Depends(get_db)):
    from app.run_agent import get_niche_stats
    stats = get_niche_stats(db)
    return [
        NicheStat(niche=n, new_pending=s["new_pending"], followup_pending=s["followup_pending"], sent_today=s["sent_today"])
        for n, s in sorted(stats.items())
    ]


@router.post("", response_model=LeadOut)
def create_lead(payload: LeadCreate, db: Session = Depends(get_db)):
    if not payload.business_name.strip():
        raise HTTPException(status_code=400, detail="Business name is required")
    lead = Lead(
        business_name=payload.business_name.strip(), niche=payload.niche,
        city=payload.city or None, state=payload.state or None,
        website=payload.website or None, email=payload.email or None,
        source="manual",
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return LeadOut(
        id=lead.id, business_name=lead.business_name, niche=lead.niche, city=lead.city,
        state=lead.state, status=lead.status, email=lead.email, email_status=lead.email_status,
        phone=lead.phone, contact_name=lead.contact_name, website=lead.website,
        meta_pixel=None, google_analytics="UNKNOWN", gtm="UNKNOWN", created_at=lead.created_at,
    )


@router.get("/{lead_id}", response_model=LeadDetailOut)
def get_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).options(joinedload(Lead.research)).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    events = (
        db.query(EmailEvent)
        .filter(EmailEvent.lead_id == lead_id)
        .order_by(EmailEvent.scheduled_for)
        .all()
    )
    research_out = None
    if lead.research:
        r = lead.research
        gtm_display = "PRESENT" if r.gtm else "MISSING" if r.gtm is not None else "UNKNOWN"
        research_out = LeadResearchOut(meta_pixel=r.meta_pixel, google_analytics=r.google_analytics, gtm=gtm_display)
    return LeadDetailOut(
        id=lead.id, business_name=lead.business_name, niche=lead.niche, city=lead.city,
        state=lead.state, status=lead.status, email=lead.email, email_status=lead.email_status,
        phone=lead.phone, contact_name=lead.contact_name, website=lead.website,
        meta_pixel=(lead.research.meta_pixel if lead.research else None),
        created_at=lead.created_at, research=research_out,
        events=[EmailEventOut(event_type=e.event_type, scheduled_for=e.scheduled_for, sent_at=e.sent_at) for e in events],
    )
