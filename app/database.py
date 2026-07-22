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
    """Add columns introduced after first install (SQLite y Postgres)."""
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    is_pg = DATABASE_URL.startswith("postgres")

    def col_names(table: str) -> set[str]:
        return {c["name"] for c in inspect(engine).get_columns(table)}

    with engine.begin() as conn:
        if "receptions" in tables:
            cols = col_names("receptions")
            if "public_token" not in cols:
                conn.execute(text("ALTER TABLE receptions ADD COLUMN public_token VARCHAR(64) DEFAULT ''"))
            if "customer_accepted" not in cols:
                default = "FALSE" if is_pg else "0"
                conn.execute(text(f"ALTER TABLE receptions ADD COLUMN customer_accepted BOOLEAN DEFAULT {default}"))
            if "customer_signature_name" not in col_names("receptions"):
                conn.execute(
                    text("ALTER TABLE receptions ADD COLUMN customer_signature_name VARCHAR(160) DEFAULT ''")
                )
            if "tenant_id" not in col_names("receptions"):
                conn.execute(text("ALTER TABLE receptions ADD COLUMN tenant_id INTEGER DEFAULT 1"))
        if "work_orders" in tables:
            if "payment_status" not in col_names("work_orders"):
                conn.execute(
                    text("ALTER TABLE work_orders ADD COLUMN payment_status VARCHAR(30) DEFAULT 'pendiente'")
                )
        if "shop_settings" in tables:
            scols = col_names("shop_settings")
            if "sinpe_phone" not in scols:
                conn.execute(text("ALTER TABLE shop_settings ADD COLUMN sinpe_phone VARCHAR(40) DEFAULT ''"))
            if "sinpe_name" not in col_names("shop_settings"):
                conn.execute(text("ALTER TABLE shop_settings ADD COLUMN sinpe_name VARCHAR(160) DEFAULT ''"))
            if "tenant_id" not in col_names("shop_settings"):
                conn.execute(text("ALTER TABLE shop_settings ADD COLUMN tenant_id INTEGER DEFAULT 1"))
        if "suppliers" in tables:
            adds = {
                "kind": "VARCHAR(30) DEFAULT 'tienda'",
                "website": "VARCHAR(255) DEFAULT ''",
                "whatsapp": "VARCHAR(40) DEFAULT ''",
                "search_url": "VARCHAR(400) DEFAULT ''",
                "specialty": "VARCHAR(200) DEFAULT ''",
                "tenant_id": "INTEGER DEFAULT 1",
            }
            for name, ddl in adds.items():
                if name not in col_names("suppliers"):
                    conn.execute(text(f"ALTER TABLE suppliers ADD COLUMN {name} {ddl}"))
        if "parts" in tables:
            if "barcode" not in col_names("parts"):
                conn.execute(text("ALTER TABLE parts ADD COLUMN barcode VARCHAR(80) DEFAULT ''"))
                conn.execute(text("UPDATE parts SET barcode = sku WHERE barcode IS NULL OR barcode = ''"))
            if "tenant_id" not in col_names("parts"):
                conn.execute(text("ALTER TABLE parts ADD COLUMN tenant_id INTEGER DEFAULT 1"))
        for table in (
            "users",
            "customers",
            "service_catalog",
            "appointments",
            "issuer_profiles",
        ):
            if table in tables and "tenant_id" not in col_names(table):
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN tenant_id INTEGER DEFAULT 1"))
