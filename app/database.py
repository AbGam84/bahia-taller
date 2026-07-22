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
    tables = set(insp.get_table_names())
    with engine.begin() as conn:
        if "receptions" in tables:
            cols = {c["name"] for c in insp.get_columns("receptions")}
            if "public_token" not in cols:
                conn.execute(text("ALTER TABLE receptions ADD COLUMN public_token VARCHAR(64) DEFAULT ''"))
            if "customer_accepted" not in cols:
                conn.execute(text("ALTER TABLE receptions ADD COLUMN customer_accepted BOOLEAN DEFAULT 0"))
            if "customer_signature_name" not in cols:
                conn.execute(
                    text("ALTER TABLE receptions ADD COLUMN customer_signature_name VARCHAR(160) DEFAULT ''")
                )
        if "work_orders" in tables:
            wcols = {c["name"] for c in insp.get_columns("work_orders")}
            if "payment_status" not in wcols:
                conn.execute(
                    text("ALTER TABLE work_orders ADD COLUMN payment_status VARCHAR(30) DEFAULT 'pendiente'")
                )
        if "shop_settings" in tables:
            scols = {c["name"] for c in insp.get_columns("shop_settings")}
            if "sinpe_phone" not in scols:
                conn.execute(text("ALTER TABLE shop_settings ADD COLUMN sinpe_phone VARCHAR(40) DEFAULT ''"))
            if "sinpe_name" not in scols:
                conn.execute(text("ALTER TABLE shop_settings ADD COLUMN sinpe_name VARCHAR(160) DEFAULT ''"))
        if "suppliers" in tables:
            scols = {c["name"] for c in insp.get_columns("suppliers")}
            adds = {
                "kind": "VARCHAR(30) DEFAULT 'tienda'",
                "website": "VARCHAR(255) DEFAULT ''",
                "whatsapp": "VARCHAR(40) DEFAULT ''",
                "search_url": "VARCHAR(400) DEFAULT ''",
                "specialty": "VARCHAR(200) DEFAULT ''",
            }
            for name, ddl in adds.items():
                if name not in scols:
                    conn.execute(text(f"ALTER TABLE suppliers ADD COLUMN {name} {ddl}"))
