"""Serviço de tokens Mercado Livre reais com criptografia e refresh automático."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import requests
from sqlalchemy.orm import Session

from config.settings import ML_BASE_URL, ML_CLIENT_ID, ML_CLIENT_SECRET
from models.orm import MarketplaceConnection
from services.security.token_crypto import decrypt_token, encrypt_token

log = logging.getLogger("msp.ml.token")
MARKETPLACE = "mercadolivre"
TOKEN_ENDPOINT = f"{ML_BASE_URL}/oauth/token"


class MLTokenServiceError(Exception):
    pass


def get_connection(db: Session, tenant_id: str) -> MarketplaceConnection | None:
    return db.query(MarketplaceConnection).filter_by(
        tenant_id=tenant_id, marketplace=MARKETPLACE, is_active=True
    ).first()


def get_valid_access_token(db: Session, tenant_id: str) -> str:
    conn = get_connection(db, tenant_id)
    if not conn:
        raise MLTokenServiceError("Seller Mercado Livre não conectado.")

    now = datetime.utcnow()
    if conn.token_expires_at and now >= conn.token_expires_at - timedelta(minutes=5):
        conn = refresh_access_token(db, tenant_id)

    if not conn.access_token_encrypted:
        raise MLTokenServiceError("Conexão Mercado Livre sem access_token armazenado.")
    return decrypt_token(conn.access_token_encrypted)


def refresh_access_token(db: Session, tenant_id: str) -> MarketplaceConnection:
    conn = get_connection(db, tenant_id)
    if not conn or not conn.refresh_token_encrypted:
        raise MLTokenServiceError("Sem refresh_token para renovar Mercado Livre.")

    payload = {
        "grant_type": "refresh_token",
        "client_id": ML_CLIENT_ID,
        "client_secret": ML_CLIENT_SECRET,
        "refresh_token": decrypt_token(conn.refresh_token_encrypted),
    }
    try:
        response = requests.post(TOKEN_ENDPOINT, data=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        log.exception("Erro OAuth", extra={"event": "Erro OAuth", "tenant_id": str(tenant_id), "marketplace": MARKETPLACE})
        raise MLTokenServiceError(f"Erro ao renovar token Mercado Livre: {exc}") from exc

    access_token = data.get("access_token")
    if not access_token:
        raise MLTokenServiceError(f"Mercado Livre não retornou access_token no refresh: {data}")

    conn.access_token_encrypted = encrypt_token(access_token)
    if data.get("refresh_token"):
        conn.refresh_token_encrypted = encrypt_token(data["refresh_token"])
    conn.token_expires_at = datetime.utcnow() + timedelta(seconds=int(data.get("expires_in") or 21600))
    conn.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(conn)
    log.info("Token renovado", extra={"event": "Token renovado", "tenant_id": str(tenant_id), "seller_id": conn.seller_id})
    return conn


def upsert_connection(
    db: Session,
    tenant_id: str,
    token_data: dict[str, Any],
    seller_data: dict[str, Any],
) -> MarketplaceConnection:
    seller_id = str(seller_data.get("id") or token_data.get("user_id") or "")
    if not seller_id:
        raise MLTokenServiceError("Não foi possível identificar seller_id Mercado Livre.")

    conn = db.query(MarketplaceConnection).filter_by(tenant_id=tenant_id, marketplace=MARKETPLACE).first()
    now = datetime.utcnow()
    if not conn:
        conn = MarketplaceConnection(tenant_id=tenant_id, marketplace=MARKETPLACE, connected_at=now)
        db.add(conn)

    conn.seller_id = seller_id
    conn.nickname = seller_data.get("nickname")
    conn.country_id = seller_data.get("country_id") or seller_data.get("site_id")
    conn.access_token_encrypted = encrypt_token(token_data["access_token"])
    if token_data.get("refresh_token"):
        conn.refresh_token_encrypted = encrypt_token(token_data["refresh_token"])
    conn.token_expires_at = now + timedelta(seconds=int(token_data.get("expires_in") or 21600))
    conn.account_metadata = {
        "user_id": token_data.get("user_id"),
        "site_id": seller_data.get("site_id"),
        "email": seller_data.get("email"),
        "first_name": seller_data.get("first_name"),
        "last_name": seller_data.get("last_name"),
        "permalink": seller_data.get("permalink"),
        "raw_status": seller_data.get("status"),
    }
    conn.is_active = True
    conn.updated_at = now
    db.commit()
    db.refresh(conn)
    log.info("Seller conectado", extra={"event": "Seller conectado", "tenant_id": str(tenant_id), "seller_id": seller_id})
    return conn
