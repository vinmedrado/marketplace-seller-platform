"""OAuth2 real Mercado Livre com callback correto e tokens criptografados."""
from __future__ import annotations

import logging
import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests
from sqlalchemy.orm import Session

from config.settings import API_SECRET_KEY, ML_BASE_URL, ML_CLIENT_ID, ML_CLIENT_SECRET, ML_REDIRECT_URI
from services.ml_token_service import get_valid_access_token, refresh_access_token, upsert_connection

log = logging.getLogger("msp.ml.auth")
AUTH_URL = "https://auth.mercadolibre.com/authorization"
TOKEN_URL = f"{ML_BASE_URL}/oauth/token"


class MLAuthError(Exception):
    pass


def _is_expired(value: datetime) -> bool:
    now = datetime.now(value.tzinfo) if value.tzinfo else datetime.utcnow()
    return value < now


def _validate_credentials() -> None:
    missing = [name for name, value in {
        "ML_CLIENT_ID": ML_CLIENT_ID,
        "ML_CLIENT_SECRET": ML_CLIENT_SECRET,
        "ML_REDIRECT_URI": ML_REDIRECT_URI,
    }.items() if not value]
    if missing:
        raise MLAuthError(f"Credenciais Mercado Livre ausentes: {', '.join(missing)}")


def _encode_state(cliente_id: str) -> str:
    payload = {
        "tenant_id": str(cliente_id),
        "exp": int(time.time()) + 600,
        "nonce": secrets.token_urlsafe(18),
    }
    body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).rstrip(b"=").decode("ascii")
    signature = hmac.new(API_SECRET_KEY.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def validate_oauth_state(state: str, db: Session | None = None) -> str:
    try:
        body, signature = state.split(".", 1)
        expected = hmac.new(API_SECRET_KEY.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        decoded = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        payload = json.loads(decoded)
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("expired")
        tenant_id = str(payload["tenant_id"])
        if not tenant_id:
            raise ValueError("tenant")
        if db is not None:
            from models.orm import OAuthState
            state_hash = hashlib.sha256(state.encode("utf-8")).hexdigest()
            row = db.query(OAuthState).filter_by(state_hash=state_hash, tenant_id=tenant_id).first()
            if not row or row.consumed_at or _is_expired(row.expires_at):
                raise ValueError("nonce")
            row.consumed_at = datetime.utcnow()
            db.commit()
        return tenant_id
    except Exception as exc:
        raise MLAuthError("Estado OAuth inválido ou expirado.") from exc


def generate_auth_link(cliente_id: str, db: Session | None = None) -> str:
    _validate_credentials()
    state = _encode_state(cliente_id)
    if db is not None:
        from models.orm import OAuthState
        db.add(OAuthState(
            tenant_id=str(cliente_id),
            state_hash=hashlib.sha256(state.encode("utf-8")).hexdigest(),
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        ))
        db.commit()
    params = {
        "response_type": "code",
        "client_id": ML_CLIENT_ID,
        "redirect_uri": ML_REDIRECT_URI,
        "state": state,
    }
    link = f"{AUTH_URL}?{urlencode(params)}"
    log.info("OAuth iniciado", extra={"event": "OAuth iniciado", "tenant_id": str(cliente_id), "marketplace": "mercadolivre"})
    return link


def exchange_code(db: Session, cliente_id: str, code: str):
    _validate_credentials()
    payload = {
        "grant_type": "authorization_code",
        "client_id": ML_CLIENT_ID,
        "client_secret": ML_CLIENT_SECRET,
        "code": code,
        "redirect_uri": ML_REDIRECT_URI,
    }
    try:
        response = requests.post(TOKEN_URL, data=payload, timeout=15)
        response.raise_for_status()
        token_data = response.json()
    except Exception as exc:
        log.exception("Erro OAuth", extra={"event": "Erro OAuth", "tenant_id": str(cliente_id), "marketplace": "mercadolivre"})
        raise MLAuthError(f"Erro ao trocar code Mercado Livre: {exc}") from exc

    access_token = token_data.get("access_token")
    if not access_token:
        raise MLAuthError(f"Mercado Livre não retornou access_token: {token_data}")

    seller_data = _fetch_seller_profile(access_token)
    conn = upsert_connection(db, cliente_id, token_data, seller_data)
    log.info("OAuth concluído", extra={"event": "OAuth concluído", "tenant_id": str(cliente_id), "seller_id": conn.seller_id})
    return {
        "status": "ok",
        "seller_id": conn.seller_id,
        "nickname": conn.nickname,
        "country_id": conn.country_id,
        "token_expires_at": conn.token_expires_at.isoformat() if conn.token_expires_at else None,
    }


def refresh_token(db: Session, cliente_id: str) -> dict:
    conn = refresh_access_token(db, cliente_id)
    return {"status": "ok", "seller_id": conn.seller_id, "token_expires_at": conn.token_expires_at.isoformat() if conn.token_expires_at else None}


def get_valid_token(db: Session, cliente_id: str) -> str:
    return get_valid_access_token(db, cliente_id)


def _fetch_seller_profile(access_token: str) -> dict:
    try:
        response = requests.get(
            f"{ML_BASE_URL}/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        raise MLAuthError(f"Erro ao buscar perfil do seller Mercado Livre: {exc}") from exc
