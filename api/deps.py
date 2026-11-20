"""
DB session dependency — reuses the EXACT same engine/session factory the
Streamlit app and run_agent.py already use. Nothing about src/ changes.
"""

from src.db.session import SessionLocal


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
