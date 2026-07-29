"""Aplica a política de retenção. Por padrão apenas informa o que seria removido."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.base import SessionLocal
from services.privacy_service import cleanup_expired_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Descarte seguro de registros expirados")
    parser.add_argument("--apply", action="store_true", help="Efetiva as exclusões")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        print(cleanup_expired_data(db, apply=args.apply))
    finally:
        db.close()


if __name__ == "__main__":
    main()
