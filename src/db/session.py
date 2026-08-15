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
engine = create_engine(DATABASE_URL, echo=False)

SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    """
    Creates all tables defined in models.py, if they don't already exist.
    Safe to call multiple times — it won't drop or overwrite existing data.
    """
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at: {DATABASE_URL}")