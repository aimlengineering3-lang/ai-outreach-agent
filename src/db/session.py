"""
Creates the SQLAlchemy engine and session factory — the connection
to our SQLite database.
"""

import os
from sqlalchemy import create_engine, event
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
        connect_args={
            "connect_timeout": 10,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3,
        },
    )

    # The "-c statement_timeout=..." startup option above was NOT
    # reliably taking effect — Supabase's pooler can silently drop
    # startup "options" depending on pooling mode, which is exactly
    # why queries were hanging forever instead of erroring after 15s.
    # Setting it explicitly via a real SQL command on every new
    # physical connection guarantees it actually applies, regardless
    # of pooler behavior: now any single query that doesn't get a
    # response within 10s gets killed BY POSTGRES ITSELF and raises a
    # clear error in Python — never another silent infinite hang.
    @event.listens_for(engine, "connect")
    def _force_statement_timeout(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("SET statement_timeout = 10000")
        cursor.close()

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