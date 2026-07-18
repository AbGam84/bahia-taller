import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _env(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


DATA_DIR = Path(_env("BAHIA_DATA_DIR", str(ROOT / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = _env("DATABASE_URL", f"sqlite:///{DATA_DIR / 'tallerpro.db'}")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)

SECRET_KEY = _env("BAHIA_SECRET_KEY") or _env("SECRET_KEY") or "bahia-dev-local-only"
ACCESS_TOKEN_HOURS = int(_env("BAHIA_TOKEN_HOURS", "12"))

ADMIN_USERNAME = _env("BAHIA_ADMIN_USER", "admin")
ADMIN_PASSWORD = _env("BAHIA_ADMIN_PASSWORD", "admin123")
ADMIN_NAME = _env("BAHIA_ADMIN_NAME", "Administrador")

# Acceso de demostración para el cliente (no es dueño)
DEMO_USERNAME = _env("KATIRE_DEMO_USER", "cliente")
DEMO_PASSWORD = _env("KATIRE_DEMO_PASSWORD", "VerKatire2026")
DEMO_NAME = _env("KATIRE_DEMO_NAME", "Cliente demo")

HOST = _env("HOST", "0.0.0.0")
PORT = int(_env("PORT", "8096"))
PUBLIC_BASE_URL = (
    _env("PUBLIC_BASE_URL")
    or _env("RENDER_EXTERNAL_URL")
    or _env("RAILWAY_PUBLIC_DOMAIN")
    or ""
).rstrip("/")
if PUBLIC_BASE_URL and not PUBLIC_BASE_URL.startswith("http"):
    PUBLIC_BASE_URL = f"https://{PUBLIC_BASE_URL}"
ENVIRONMENT = _env("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT.lower() in {"production", "prod", "cloud"}
