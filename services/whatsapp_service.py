"""WhatsApp/Evolution API provider opcional para alertas MarketPlace Seller Platform.

A integração fica preparada/configurável. Sem envs, retorna provider_unavailable
sem interromper o fluxo principal.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from config.settings import EVOLUTION_API_KEY, EVOLUTION_API_URL, EVOLUTION_INSTANCE

log = logging.getLogger("msp.alerts.whatsapp")
REQUEST_TIMEOUT = 15


def _sanitize_phone(phone: str | None) -> str:
    return "".join(ch for ch in str(phone or "") if ch.isdigit())


def send_whatsapp_message(phone: str | None, message: str) -> dict[str, Any]:
    if not (EVOLUTION_API_URL and EVOLUTION_API_KEY and EVOLUTION_INSTANCE):
        return {"ok": False, "status": "provider_unavailable", "error": "Evolution API não configurada."}
    number = _sanitize_phone(phone)
    if len(number) < 10:
        return {"ok": False, "status": "destination_missing", "error": "Telefone WhatsApp inválido ou ausente."}
    base = EVOLUTION_API_URL.rstrip("/")
    # Endpoint compatível com Evolution API v2 mais comum.
    url = f"{base}/message/sendText/{EVOLUTION_INSTANCE}"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    payload = {"number": number, "text": message[:3900]}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        if response.status_code >= 400:
            log.warning("whatsapp_send_failed", extra={"event": "whatsapp_send_failed", "status_code": response.status_code})
            return {"ok": False, "status": "failed", "error": f"Evolution HTTP {response.status_code}"}
        return {"ok": True, "status": "sent", "provider_response": response.json() if response.content else {}}
    except Exception as exc:  # noqa: BLE001
        log.warning("whatsapp_send_exception", extra={"event": "whatsapp_send_exception", "error_type": type(exc).__name__})
        return {"ok": False, "status": "failed", "error": type(exc).__name__}
