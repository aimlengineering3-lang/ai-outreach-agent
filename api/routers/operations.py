import queue as _queue_module
import asyncio

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from src.db.models import Campaign
from src.core.config import get_app_mode, set_app_mode
from api.deps import get_db
from api.schemas import SendRequest, SendJobCreated, SendByNicheRequest, CheckRepliesResult
from api import jobs

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("/mode")
def get_mode():
    return {"mode": get_app_mode()}


@router.post("/mode")
def set_mode(mode: str):
    if mode not in ("TEST", "PRODUCTION"):
        raise HTTPException(status_code=400, detail="mode must be TEST or PRODUCTION")
    set_app_mode(mode)
    return {"mode": mode}


@router.post("/send", response_model=SendJobCreated)
def start_send(payload: SendRequest, db: Session = Depends(get_db)):
    # Validate every campaign_id up front, before starting the thread,
    # so a bad id fails fast with a normal HTTP error instead of a job
    # that silently skips it.
    for campaign_id in payload.campaign_limits:
        exists = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not exists:
            raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")

    job_id, total_requested = jobs.create_job(payload.campaign_limits)
    return SendJobCreated(job_id=job_id, total_requested=total_requested)


@router.post("/send-by-niche", response_model=SendJobCreated)
def start_send_by_niche(payload: SendByNicheRequest, db: Session = Depends(get_db)):
    """
    Same as /send, but budgets are set per-NICHE (one number for
    'plumbing', spent across however many plumbing campaigns you pick,
    in order) instead of per-campaign — matches the old dashboard's
    'Send All Pending Now' grouping exactly.
    """
    for a in payload.assignments:
        for cid in a.campaign_ids:
            if not db.query(Campaign).filter(Campaign.id == cid).first():
                raise HTTPException(status_code=404, detail=f"Campaign {cid} not found")

    assignments = [a.model_dump() for a in payload.assignments]
    job_id, total_requested = jobs.create_niche_job(assignments)
    return SendJobCreated(job_id=job_id, total_requested=total_requested)


@router.post("/check-replies", response_model=CheckRepliesResult)
def check_replies():
    """
    Checks inbox for replies (stops follow-ups automatically) + checks
    for bounces. This runs synchronously — it's typically a few seconds,
    same as the old blocking-spinner button — so no job/websocket needed.
    """
    from src.replies.reply_detector import check_all_active_campaigns_captured
    from src.replies.bounce_detector import check_all_accounts_for_bounces
    from src.db.session import SessionLocal

    log = check_all_active_campaigns_captured()

    bounce_session = SessionLocal()
    try:
        bounce_result = check_all_accounts_for_bounces(bounce_session)
    finally:
        bounce_session.close()

    log += (
        f"\n\n--- Bounce check ---\n"
        f"Checked {bounce_result['checked']} message(s), "
        f"found {bounce_result['bounces_found']} new bounce(s)."
    )
    return CheckRepliesResult(log=log)


@router.websocket("/send/{job_id}/ws")
async def send_progress_ws(websocket: WebSocket, job_id: str):
    """
    Live progress feed for a batch send started via POST /operations/send.
    The browser connects right after getting job_id back, and gets one
    JSON message per email sent ({"type": "progress", "sent": N, ...}),
    then a final {"type": "done", ...} or {"type": "error", ...}.
    """
    await websocket.accept()
    q = jobs.get_job_queue(job_id)
    if q is None:
        await websocket.send_json({"type": "error", "message": "Unknown job_id"})
        await websocket.close()
        return

    loop = asyncio.get_event_loop()
    try:
        while True:
            try:
                # Blocking queue.get() runs in a thread pool executor so
                # it never blocks the asyncio event loop (which is what
                # serves every other request/websocket in this process).
                event = await loop.run_in_executor(None, q.get, True, 1.0)
            except _queue_module.Empty:
                # Nothing new in the last second — send a tiny heartbeat
                # so the browser's WebSocket connection doesn't look dead
                # during the 15-50s human-paced gap between sends.
                await websocket.send_json({"type": "heartbeat"})
                continue

            await websocket.send_json(event)
            if event["type"] in ("done", "error"):
                break
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
