"""
Creates the SQLAlchemy engine and session factory — the connection
to our SQLite database.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from src.db.models import Base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/outreach.db")

# echo=False keeps the terminal clean; set True temporarily if you want to
# see every SQL statement SQLAlchemy generates (useful for learning/debugging)
if DATABASE_URL.startswith("sqlite"):
    # SQLite-specific settings: wait if briefly locked, and use WAL
    # mode so the dashboard, background worker, and scripts can all
    # read/write without "database is locked" errors.
    engine = create_engine(DATABASE_URL, echo=False, connect_args={"timeout": 30})
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
else:
    # PostgreSQL (Supabase) doesn't use SQLite-only options, but long-
    # running jobs (scraping, research loops) leave connections idle
    # long enough for Supabase's pooler to close them server-side.
    # pool_pre_ping tests each connection with a lightweight query
    # before using it and transparently replaces dead ones instead of
    # erroring; pool_recycle proactively retires connections before
    # the pooler's own idle timeout gets to them first.
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=300,
        # Without a timeout, a "zombie" connection (looks alive locally
        # but the server or a router/NAT in between has silently
        # dropped it) can make a query wait forever with no error and
        # no CPU usage — exactly the symptom of a stuck-but-idle
        # dashboard. This forces any single query to fail after 15s
        # instead of hanging indefinitely, so the app can recover
        # (get a fresh connection) instead of freezing.
        connect_args={"connect_timeout": 10, "options": "-c statement_timeout=15000"},
    )

# expire_on_commit=False: by default, every session.commit() marks all
# already-loaded ORM objects as "expired," so the next attribute access
# on any of them (e.g. lead.website for the NEXT lead in a loop) fires
# an implicit refresh query. In loops that commit once per item and then
# do slow I/O (Playwright scraping, website research, sending email),
# that implicit query checks out a fresh DB connection right before the
# slow I/O starts — and it doesn't get released until that item's own
# commit(), so the connection sits open, idle, for the entire slow step.
# Turning this off removes the implicit refresh; every value written by
# this app is set in Python before commit (no server-side defaults or
# triggers we depend on reading back), so nothing here relies on a
# post-commit reload.
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    """
    Creates all tables defined in models.py, if they don't already exist.
    Safe to call multiple times — it won't drop or overwrite existing data.
    """
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at: {DATABASE_URL}")