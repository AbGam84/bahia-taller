#!/usr/bin/env python3
"""Emitir licencia Katire para un taller (SOLO VENDOR — no entregar al cliente)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.license import issue_license  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Emitir clave de licencia Katire")
    p.add_argument("--shop", required=True, help="Nombre del taller, ej. Autorespuesto")
    p.add_argument("--expires", required=True, help="YYYY-MM-DD")
    p.add_argument("--seats", type=int, default=5)
    p.add_argument("--note", default="")
    args = p.parse_args()
    key = issue_license(args.shop, args.expires, seats=args.seats, note=args.note)
    print(key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
