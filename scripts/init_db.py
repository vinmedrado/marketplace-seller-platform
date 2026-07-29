"""Inicializa ou atualiza o banco exclusivamente pelas migrations Alembic."""
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def main():
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    print("Banco atualizado para a migration mais recente.")


if __name__ == "__main__":
    main()
