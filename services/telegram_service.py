"""Telegram provider para alertas operacionais SellerOS.

PATCH 9/10 — provider opcional. Falhas de Telegram nunca devem quebrar o
fluxo principal de negócio.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from config.settings import TELEGRAM_BOT_TOKEN

log = logging.getLogger("msp.alerts.telegram")
REQUEST_TIMEOUT = 12


def _sanitize_error(exc: Exception) -> str:
    return type(exc).__name__


def send_telegram_message(chat_id: str | None, message: str) -> dict[str, Any]:
    if not TELEGRAM_BOT_TOKEN:
        return {"ok": False, "status": "provider_unavailable", "error": "Telegram não configurado."}
    if not chat_id:
        return {"ok": False, "status": "destination_missing", "error": "Chat ID não configurado."}
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": str(chat_id), "text": message[:3900], "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code >= 400:
            log.warning("telegram_send_failed", extra={"event": "telegram_send_failed", "status_code": response.status_code})
            return {"ok": False, "status": "failed", "error": f"Telegram HTTP {response.status_code}"}
        return {"ok": True, "status": "sent", "provider_response": response.json() if response.content else {}}
    except Exception as exc:  # noqa: BLE001
        log.warning("telegram_send_exception", extra={"event": "telegram_send_exception", "error_type": type(exc).__name__})
        return {"ok": False, "status": "failed", "error": _sanitize_error(exc)}
