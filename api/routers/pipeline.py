from fastapi import APIRouter, HTTPException

from api.schemas import PipelineRunRequest, JobCreated
from api import jobs

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/run", response_model=JobCreated)
def run_pipeline(payload: PipelineRunRequest):
    """
    Starts discover -> research -> queue for one niche/city in the
    background and returns immediately. Does NOT send anything — same
    boundary as the old "Run Pipeline Now" button.
    """
    job_id = jobs.create_pipeline_job(payload.niche, payload.city, payload.state)
    return JobCreated(job_id=job_id)


@router.get("/run/{job_id}")
def get_pipeline_status(job_id: str):
    """
    Poll this every ~2s from the frontend. status is "running", "done"
    or "error"; log/error are populated once status is no longer
    "running".
    """
    job = jobs.get_pipeline_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    return job
