"""Dispatcher de alertas SellerOS.

Aplica preferências do tenant, severidade mínima, tipos habilitados, quiet hours,
deduplicação e envio por provider sem bloquear o fluxo principal.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, time
import logging
from typing import Any

from sqlalchemy.orm import Session

from config.settings import ALERT_DEDUPE_WINDOW_MINUTES, EVOLUTION_API_KEY, EVOLUTION_API_URL, EVOLUTION_INSTANCE, TELEGRAM_BOT_TOKEN
from models.orm import AlertHistory, AlertSetting
from services.telegram_service import send_telegram_message
from services.whatsapp_service import send_whatsapp_message

log = logging.getLogger("msp.alerts.dispatcher")
SEVERITY_RANK = {"info": 1, "warning": 2, "critical": 3}
DEFAULT_ALERT_TYPES = [
    "LOW_STOCK", "OUT_OF_STOCK", "ACCOUNT_HEALTH_RISK", "BUYBOX_RISK", "BUYBOX_OPPORTUNITY",
    "QUESTION_PENDING_TOO_LONG", "PRICE_RISK", "SYNC_ERROR", "PRICE_ADJUSTMENT_RECOMMENDED",
    "STOCKOUT_RISK", "REORDER_RECOMMENDED",
    "RECONCILIATION_DIFFERENCE", "HIGH_FEES", "REFUND_SPIKE", "NEGATIVE_NET_REVENUE", "DATA_INCOMPLETE",
]


@dataclass
class DispatchResult:
    sent: bool
    skipped: bool
    provider_results: list[dict[str, Any]]
    reason: str | None = None


def severity_allowed(current: str, minimum: str) -> bool:
    return SEVERITY_RANK.get(str(current or "warning").lower(), 2) >= SEVERITY_RANK.get(str(minimum or "warning").lower(), 2)


def _parse_hhmm(value: str | None) -> time | None:
    if not value:
        return None
    try:
        hh, mm = str(value).split(":")[:2]
        return time(int(hh), int(mm))
    except Exception:
        return None


def in_quiet_hours(settings: AlertSetting, now: datetime | None = None) -> bool:
    start = _parse_hhmm(settings.quiet_hours_start)
    end = _parse_hhmm(settings.quiet_hours_end)
    if not start or not end:
        return False
    current = (now or datetime.utcnow()).time()
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


def get_or_create_settings(db: Session, tenant_id: str) -> AlertSetting:
    row = db.query(AlertSetting).filter_by(tenant_id=tenant_id).first()
    if row:
        return row
    row = AlertSetting(
        tenant_id=tenant_id,
        telegram_enabled=False,
        whatsapp_enabled=False,
        enabled_alert_types_json=DEFAULT_ALERT_TYPES,
        min_severity="warning",
    )
    db.add(row)
    db.flush()
    return row


def provider_status() -> dict[str, Any]:
    return {
        "telegram": {"configured": bool(TELEGRAM_BOT_TOKEN), "recommended": True},
        "whatsapp": {"configured": bool(EVOLUTION_API_URL and EVOLUTION_API_KEY and EVOLUTION_INSTANCE), "requires": "Evolution API"},
    }


def _recent_duplicate(db: Session, tenant_id: str, alert_type: str, dedupe_key: str | None) -> bool:
    if not dedupe_key:
        return False
    cutoff = datetime.utcnow() - timedelta(minutes=max(1, ALERT_DEDUPE_WINDOW_MINUTES))
    return bool(db.query(AlertHistory.id).filter(
        AlertHistory.tenant_id == tenant_id,
        AlertHistory.alert_type == alert_type,
        AlertHistory.dedupe_key == dedupe_key,
        AlertHistory.created_at >= cutoff,
        AlertHistory.status.in_(["sent", "skipped", "failed"]),
    ).first())


def _history(db: Session, *, tenant_id: str, alert_type: str, severity: str, title: str, message: str, provider: str, status: str, dedupe_key: str | None, error_message: str | None = None) -> AlertHistory:
    row = AlertHistory(
        tenant_id=tenant_id,
        alert_type=alert_type,
        severity=severity,
        title=title[:250],
        message=message[:3000],
        provider=provider,
        status=status,
        dedupe_key=dedupe_key,
        sent_at=datetime.utcnow() if status == "sent" else None,
        error_message=(error_message or "")[:500] or None,
    )
    db.add(row)
    return row


def dispatch_alert(db: Session, *, tenant_id: str, alert_type: str, severity: str, title: str, message: str, dedupe_key: str | None = None, force: bool = False) -> DispatchResult:
    settings = get_or_create_settings(db, tenant_id)
    alert_type = str(alert_type or "INFO").upper()
    severity = str(severity or "warning").lower()
    enabled_types = settings.enabled_alert_types_json or DEFAULT_ALERT_TYPES

    if not force and alert_type not in enabled_types:
        _history(db, tenant_id=tenant_id, alert_type=alert_type, severity=severity, title=title, message=message, provider="system", status="skipped", dedupe_key=dedupe_key, error_message="Tipo desabilitado")
        db.commit()
        return DispatchResult(False, True, [], "Tipo de alerta desabilitado.")
    if not force and not severity_allowed(severity, settings.min_severity):
        _history(db, tenant_id=tenant_id, alert_type=alert_type, severity=severity, title=title, message=message, provider="system", status="skipped", dedupe_key=dedupe_key, error_message="Severidade abaixo do mínimo")
        db.commit()
        return DispatchResult(False, True, [], "Severidade abaixo do mínimo configurado.")
    if not force and in_quiet_hours(settings):
        _history(db, tenant_id=tenant_id, alert_type=alert_type, severity=severity, title=title, message=message, provider="system", status="skipped", dedupe_key=dedupe_key, error_message="Quiet hours")
        db.commit()
        return DispatchResult(False, True, [], "Alerta suprimido por quiet hours.")
    if not force and _recent_duplicate(db, tenant_id, alert_type, dedupe_key):
        return DispatchResult(False, True, [], "Alerta duplicado na janela de deduplicação.")

    provider_results: list[dict[str, Any]] = []
    any_sent = False
    if settings.telegram_enabled:
        result = send_telegram_message(settings.telegram_chat_id, message)
        status = "sent" if result.get("ok") else result.get("status") or "failed"
        _history(db, tenant_id=tenant_id, alert_type=alert_type, severity=severity, title=title, message=message, provider="telegram", status=status, dedupe_key=dedupe_key, error_message=result.get("error"))
        provider_results.append({"provider": "telegram", **result})
        any_sent = any_sent or bool(result.get("ok"))
    if settings.whatsapp_enabled:
        result = send_whatsapp_message(settings.whatsapp_phone, message)
        status = "sent" if result.get("ok") else result.get("status") or "failed"
        _history(db, tenant_id=tenant_id, alert_type=alert_type, severity=severity, title=title, message=message, provider="whatsapp", status=status, dedupe_key=dedupe_key, error_message=result.get("error"))
        provider_results.append({"provider": "whatsapp", **result})
        any_sent = any_sent or bool(result.get("ok"))
    if not provider_results:
        _history(db, tenant_id=tenant_id, alert_type=alert_type, severity=severity, title=title, message=message, provider="system", status="skipped", dedupe_key=dedupe_key, error_message="Nenhum canal habilitado")
        db.commit()
        return DispatchResult(False, True, [], "Nenhum canal habilitado.")
    db.commit()
    return DispatchResult(any_sent, not any_sent, provider_results, None if any_sent else "Nenhum provider enviou a mensagem.")
