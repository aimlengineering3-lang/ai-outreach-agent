"""
FastAPI entrypoint. Run from the project root with:
    uvicorn api.main:app --reload --port 8000

This file must sit inside your existing project root (same level as
app/, src/, scripts/), as a new `api/` folder, so `from src... / from
app...` imports keep working exactly like they already do in
app/run_agent.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.db.session import init_db
from api.routers import (
    leads, campaigns, sender_accounts, overview, operations,
    pipeline, suppression, settings,
)

app = FastAPI(title="AI Outreach Agent API")

# Local Next.js dev server runs on localhost:3000 by default.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_origin_regex=r"https://.*\.trycloudflare\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(leads.router)
app.include_router(campaigns.router)
app.include_router(sender_accounts.router)
app.include_router(overview.router)
app.include_router(operations.router)
app.include_router(pipeline.router)
app.include_router(suppression.router)
app.include_router(settings.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}
