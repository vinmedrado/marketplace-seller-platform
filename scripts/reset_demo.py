"""Recria o banco local de demonstração com confirmação explícita."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Apaga e recria o banco local de demonstração.")
    parser.add_argument("--yes", action="store_true", help="Confirma a remoção de todas as tabelas.")
    args = parser.parse_args()

    from config.settings import ENV
    if ENV == "production":
        raise RuntimeError("reset_demo é bloqueado em produção.")
    if not args.yes:
        raise SystemExit("Operação destrutiva não executada. Use --yes para confirmar.")

    from db.base import Base, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("Demo resetado. Rode: python scripts/seed_demo.py")


if __name__ == "__main__":
    main()
