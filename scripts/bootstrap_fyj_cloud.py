#!/usr/bin/env python3
"""Ejecutar tras deploy: crea/actualiza FyJ Automotriz en la DB local o Render disk."""

from app.bootstrap_clients import ensure_fyj_automotriz_ready
from app.database import Base, SessionLocal, engine, migrate_schema


def main() -> None:
    Base.metadata.create_all(bind=engine)
    migrate_schema()
    db = SessionLocal()
    try:
        out = ensure_fyj_automotriz_ready(db)
        print(out)
    finally:
        db.close()


if __name__ == "__main__":
    main()
