from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL, DATA_DIR, UPLOADS_DIR

# Re-export for existing imports
__all__ = ["Base", "SessionLocal", "engine", "get_db", "migrate_schema", "DATA_DIR", "UPLOADS_DIR"]

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_schema() -> None:
    """Add columns introduced after first install (SQLite)."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    insp = inspect(engine)
    if "receptions" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("receptions")}
    with engine.begin() as conn:
        if "public_token" not in cols:
            conn.execute(text("ALTER TABLE receptions ADD COLUMN public_token VARCHAR(64) DEFAULT ''"))
        if "work_orders" in insp.get_table_names():
            wcols = {c["name"] for c in insp.get_columns("work_orders")}
            if "payment_status" not in wcols:
                conn.execute(
                    text("ALTER TABLE work_orders ADD COLUMN payment_status VARCHAR(30) DEFAULT 'pendiente'")
                )
