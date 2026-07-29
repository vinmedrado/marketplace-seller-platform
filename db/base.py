"""db/base.py — compatibilidade legada.

A partir do PATCH 3/10, a configuração real do engine/session fica em
config.database. Este módulo reexporta os mesmos símbolos para não quebrar
imports existentes.
"""
from config.database import Base, SessionLocal, check_database_connection, engine, get_db, session_scope

__all__ = ["Base", "SessionLocal", "engine", "get_db", "session_scope", "check_database_connection"]
