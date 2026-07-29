"""config/database.py — engine/session seguros para SQLite dev e PostgreSQL produção.

PATCH 3/10: centraliza criação do engine, valida ambiente crítico e evita
connection leaks com rollback automático no dependency provider.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config.logging_config import setup_logging
from config.settings import (
    API_SECRET_KEY,
    DATABASE_URL,
    ENABLE_DEMO_USER,
    ENV,
    FERNET_KEY,
    FRONTEND_URL,
    ML_CLIENT_ID,
    ML_CLIENT_SECRET,
    ML_REDIRECT_URI,
    CORS_ORIGINS,
)

log = setup_logging("database")


def normalize_database_url(url: str) -> str:
    """Normaliza URLs comuns de provedores cloud sem expor credenciais em logs."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://") :]
    return url


def is_sqlite_url(url: str | None = None) -> bool:
    return (url or DATABASE_URL).startswith("sqlite")


def is_postgres_url(url: str | None = None) -> bool:
    value = url or DATABASE_URL
    return value.startswith("postgresql") or value.startswith("postgres")


def database_kind(url: str | None = None) -> str:
    if is_postgres_url(url):
        return "postgresql"
    if is_sqlite_url(url):
        return "sqlite"
    return "unknown"


class Base(DeclarativeBase):
    pass


def _engine_kwargs(url: str) -> dict:
    if is_sqlite_url(url):
        return {
            "connect_args": {"check_same_thread": False},
            "pool_pre_ping": True,
            "future": True,
        }

    return {
        "pool_pre_ping": True,
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "1800")),
        "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
        "connect_args": {"connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10"))},
        "future": True,
    }


_NORMALIZED_DATABASE_URL = normalize_database_url(DATABASE_URL)
engine: Engine = create_engine(_NORMALIZED_DATABASE_URL, **_engine_kwargs(DATABASE_URL))

if is_sqlite_url(DATABASE_URL):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _record) -> None:  # pragma: no cover - evento runtime
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False, future=True)


def sanitize_database_url(url: str | None = None) -> str:
    value = url or DATABASE_URL
    if "://" not in value or "@" not in value:
        return value
    scheme, rest = value.split("://", 1)
    credentials, host = rest.split("@", 1)
    user = credentials.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"


def validate_runtime_environment() -> None:
    """Falha o startup quando produção estiver insegura."""
    env = (ENV or "development").lower()
    if env == "production":
        invalid_api_keys = {"", "dev-secret-change-in-prod", "troque-em-producao", "change-me", "changeme"}
        if API_SECRET_KEY in invalid_api_keys or len(API_SECRET_KEY or "") < 32:
            log.error("Secret inválida: API_SECRET_KEY de produção ausente/fraca.")
            raise RuntimeError("API_SECRET_KEY seguro é obrigatório em produção.")
        if not FERNET_KEY:
            log.error("Secret inválida: FERNET_KEY ausente em produção.")
            raise RuntimeError("FERNET_KEY é obrigatória em produção.")
        if is_sqlite_url(DATABASE_URL):
            log.error("DATABASE_URL SQLite não é permitido em produção.")
            raise RuntimeError("DATABASE_URL PostgreSQL é obrigatória em produção.")
        if not is_postgres_url(DATABASE_URL):
            log.error("DATABASE_URL de produção precisa usar PostgreSQL.")
            raise RuntimeError("DATABASE_URL inválida para produção.")
        if ENABLE_DEMO_USER:
            raise RuntimeError("ENABLE_DEMO_USER deve permanecer desativado em produção.")
        if not FRONTEND_URL.startswith("https://"):
            raise RuntimeError("FRONTEND_URL deve usar HTTPS em produção.")
        if ML_CLIENT_ID and not ML_REDIRECT_URI.startswith("https://"):
            raise RuntimeError("ML_REDIRECT_URI deve usar HTTPS em produção.")
        insecure_origins = [origin for origin in CORS_ORIGINS if "localhost" in origin or "127.0.0.1" in origin]
        if insecure_origins:
            raise RuntimeError("CORS_ORIGINS de produção não pode conter origens locais.")

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL não configurada.")

    if not ML_CLIENT_ID or not ML_CLIENT_SECRET or not ML_REDIRECT_URI:
        log.warning("Mercado Livre OAuth incompleto: configure ML_CLIENT_ID, ML_CLIENT_SECRET e ML_REDIRECT_URI.")

    log.info("Environment validado", extra={"env": env, "database": database_kind(DATABASE_URL)})


def check_database_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        log.info("PostgreSQL conectado" if is_postgres_url(DATABASE_URL) else "SQLite conectado")
        return True
    except SQLAlchemyError as exc:
        log.error("Erro ao validar conexão do banco", extra={"error": exc.__class__.__name__})
        raise RuntimeError("Banco de dados indisponível.") from exc


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        log.warning("Session rollback executado após erro.")
        raise
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        log.warning("Session rollback executado no session_scope.")
        raise
    finally:
        db.close()
