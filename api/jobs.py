"""
In-memory background-job + WebSocket progress mechanism for batch sends.

Why a thread + queue instead of just `async def` the whole thing:
run_send_cycle() (in app/run_agent.py) is a BLOCKING function — it does
real SQLAlchemy queries and time.sleep(15-50) between sends. Running it
directly inside an async request handler would freeze the entire API
(every other request, including the WebSocket) for the whole batch.

So: POST /operations/send starts a normal background thread running the
real send_cycle code UNCHANGED, and returns a job_id immediately. The
thread pushes progress events onto a plain thread-safe queue.Queue. The
WebSocket endpoint (separate connection) reads off that same queue and
forwards each event to the browser in real time. This is local-only and
single-process, which matches exactly how this app is actually run
(uvicorn, one process, on your own machine) — no Redis/Celery needed.
"""

import threading
import queue
import uuid
from datetime import datetime, timezone

from src.db.session import SessionLocal
from src.db.models import Campaign
from app.run_agent import run_send_cycle

# job_id -> {"queue": queue.Queue, "done": bool, "created_at": datetime}
_jobs: dict[str, dict] = {}


def create_job(campaign_limits: dict[int, int]) -> tuple[str, int]:
    """Starts the background thread, returns (job_id, total_requested)."""
    job_id = str(uuid.uuid4())
    total_requested = sum(campaign_limits.values())
    _jobs[job_id] = {
        "queue": queue.Queue(),
        "done": False,
        "created_at": datetime.now(timezone.utc),
    }

    thread = threading.Thread(
        target=_run_send_job, args=(job_id, campaign_limits, total_requested), daemon=True,
    )
    thread.start()
    return job_id, total_requested


def get_job_queue(job_id: str) -> queue.Queue | None:
    job = _jobs.get(job_id)
    return job["queue"] if job else None


# -----------------------------------------------------------------
# Pipeline-run jobs (discover -> research -> queue).
# run_pipeline_captured() has no progress callback — it only returns a
# single log string once it's fully done — so unlike the send job above
# there's nothing to stream. The point of making this a background job
# at all is purely so the API request returns instantly and the rest of
# the UI stays responsive while scraping/research runs (several seconds
# to a few minutes); the frontend polls GET /pipeline/run/{job_id}
# every couple of seconds until status flips to "done" or "error".
# -----------------------------------------------------------------
_pipeline_jobs: dict[str, dict] = {}


def create_pipeline_job(niche: str, city: str, state: str) -> str:
    from app.run_agent import run_pipeline_captured

    job_id = str(uuid.uuid4())
    _pipeline_jobs[job_id] = {"status": "running", "log": None, "error": None}

    def _run():
        try:
            log = run_pipeline_captured(niche, city, state, campaign_id=None)
            # The old dashboard also appended every run to pipeline_log.txt.
            try:
                with open("pipeline_log.txt", "a", encoding="utf-8") as f:
                    f.write(f"\n--- {datetime.now()} ---\n{log}\n")
            except OSError:
                pass
            _pipeline_jobs[job_id] = {"status": "done", "log": log, "error": None}
        except Exception as e:
            _pipeline_jobs[job_id] = {"status": "error", "log": None, "error": str(e)}

    threading.Thread(target=_run, daemon=True).start()
    return job_id


def get_pipeline_job(job_id: str) -> dict | None:
    return _pipeline_jobs.get(job_id)


def create_niche_job(assignments: list[dict]) -> tuple[str, int]:
    """
    assignments: [{"niche": "plumbing", "limit": 20, "campaign_ids": [1, 2]}, ...]
    Mirrors the old Streamlit "Send All Pending Now" behaviour exactly:
    the niche's budget is spent against its campaigns IN ORDER, each
    campaign taking as much of the remaining budget as it can before the
    next campaign in that niche gets a turn.
    """
    job_id = str(uuid.uuid4())
    total_requested = sum(a["limit"] for a in assignments)
    _jobs[job_id] = {"queue": queue.Queue(), "done": False, "created_at": datetime.now(timezone.utc)}
    thread = threading.Thread(
        target=_run_send_job_by_niche, args=(job_id, assignments, total_requested), daemon=True,
    )
    thread.start()
    return job_id, total_requested


def _run_send_job_by_niche(job_id: str, assignments: list[dict], total_requested: int) -> None:
    q = _jobs[job_id]["queue"]
    session = SessionLocal()

    skipped_keys = [
        "skipped_no_capacity", "skipped_outside_window",
        "skipped_no_template", "skipped_suppressed",
    ]
    totals = {k: 0 for k in skipped_keys}
    totals["sent"] = 0
    per_niche_sent: dict[str, int] = {}

    try:
        for a in assignments:
            niche, budget, campaign_ids = a["niche"], a["limit"], a["campaign_ids"]
            if budget <= 0:
                continue
            sent_here = 0
            for cid in campaign_ids:
                left = budget - sent_here
                if left <= 0:
                    break
                campaign = session.query(Campaign).filter(Campaign.id == cid).first()
                if not campaign:
                    continue

                base_count = totals["sent"] + sent_here

                def on_progress(n_this_call, _base=base_count, _camp=campaign, _niche=niche):
                    q.put({
                        "type": "progress", "sent": _base + n_this_call, "total": total_requested,
                        "campaign_id": _camp.id, "campaign_name": _camp.name, "niche": _niche,
                    })

                result = run_send_cycle(session, campaign, max_sends=left, on_progress=on_progress)
                sent_here += max(result.get("sent", 0), 0)
                for k in skipped_keys:
                    v = result.get(k, 0)
                    if v and v > 0:
                        totals[k] += v
            per_niche_sent[niche] = sent_here
            totals["sent"] += sent_here

        q.put({"type": "done", "summary": totals, "per_niche_sent": per_niche_sent})
    except Exception as e:
        q.put({"type": "error", "message": str(e)})
    finally:
        session.close()
        _jobs[job_id]["done"] = True


def _run_send_job(job_id: str, campaign_limits: dict[int, int], total_requested: int) -> None:
    q = _jobs[job_id]["queue"]
    session = SessionLocal()

    skipped_keys = [
        "skipped_no_capacity", "skipped_outside_window",
        "skipped_no_template", "skipped_suppressed",
    ]
    totals = {k: 0 for k in skipped_keys}
    totals["sent"] = 0
    per_campaign_sent: dict[int, int] = {}

    try:
        for campaign_id, budget in campaign_limits.items():
            if budget <= 0:
                continue
            campaign = session.query(Campaign).filter(Campaign.id == campaign_id).first()
            if not campaign:
                continue

            base_count = totals["sent"]

            def on_progress(n_this_call, _base=base_count, _camp=campaign):
                q.put({
                    "type": "progress",
                    "sent": _base + n_this_call,
                    "total": total_requested,
                    "campaign_id": _camp.id,
                    "campaign_name": _camp.name,
                })

            result = run_send_cycle(session, campaign, max_sends=budget, on_progress=on_progress)
            sent_here = max(result.get("sent", 0), 0)
            per_campaign_sent[campaign_id] = sent_here
            totals["sent"] += sent_here
            for k in skipped_keys:
                v = result.get(k, 0)
                if v and v > 0:
                    totals[k] += v

        q.put({
            "type": "done",
            "summary": totals,
            "per_campaign_sent": per_campaign_sent,
            "total_requested": total_requested,
        })
    except Exception as e:
        q.put({"type": "error", "message": str(e)})
    finally:
        session.close()
        _jobs[job_id]["done"] = True
