from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.db.models import Campaign, CampaignTemplate
from api.deps import get_db
from api.schemas import (
    CampaignOut, CampaignCreate, CampaignStatusUpdate, CampaignUpdate,
    TemplateOut, TemplateCreate,
)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("", response_model=list[CampaignOut])
def list_campaigns(db: Session = Depends(get_db), niche: str | None = None, status: str | None = None):
    q = db.query(Campaign)
    if niche:
        q = q.filter(Campaign.niche == niche)
    if status:
        q = q.filter(Campaign.status == status)
    return q.order_by(Campaign.created_at.desc()).all()


@router.post("", response_model=CampaignOut)
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)):
    campaign = Campaign(
        name=payload.name.strip(),
        niche=payload.niche,
        status="PAUSED",
        followup1_delay_days=payload.followup1_delay_days,
        followup2_delay_days=payload.followup2_delay_days,
        followup2_enabled=payload.followup2_enabled,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.patch("/{campaign_id}/status", response_model=CampaignOut)
def update_campaign_status(campaign_id: int, payload: CampaignStatusUpdate, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if payload.status not in ("ACTIVE", "PAUSED"):
        raise HTTPException(status_code=400, detail="status must be ACTIVE or PAUSED")
    campaign.status = payload.status
    db.commit()
    db.refresh(campaign)
    return campaign


@router.delete("/{campaign_id}")
def delete_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    db.delete(campaign)
    db.commit()
    return {"deleted": True}


@router.patch("/{campaign_id}", response_model=CampaignOut)
def update_campaign(campaign_id: int, payload: CampaignUpdate, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if payload.followup1_delay_days is not None:
        campaign.followup1_delay_days = payload.followup1_delay_days
    if payload.followup2_delay_days is not None:
        campaign.followup2_delay_days = payload.followup2_delay_days
    if payload.followup2_enabled is not None:
        campaign.followup2_enabled = payload.followup2_enabled
    db.commit()
    db.refresh(campaign)
    return campaign


@router.get("/{campaign_id}/templates", response_model=list[TemplateOut])
def list_templates(campaign_id: int, variant: str | None = None, db: Session = Depends(get_db)):
    """All versions, newest first. Pass ?variant=pixel_missing to filter to one variant
    (the frontend wants this for the 'current version' + version-history view)."""
    q = db.query(CampaignTemplate).filter(CampaignTemplate.campaign_id == campaign_id)
    if variant:
        q = q.filter(CampaignTemplate.variant == variant)
    return q.order_by(CampaignTemplate.updated_at.desc()).all()


@router.post("/{campaign_id}/templates", response_model=TemplateOut)
def create_template_version(campaign_id: int, payload: TemplateCreate, db: Session = Depends(get_db)):
    """Templates are NEVER edited in place — this always inserts a new version,
    exactly like the dashboard's 'Save as new version' button."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if not payload.body.strip():
        raise HTTPException(status_code=400, detail="Template body can't be empty")
    template = CampaignTemplate(campaign_id=campaign_id, variant=payload.variant, body=payload.body)
    db.add(template)
    db.commit()
    db.refresh(template)
    return template
