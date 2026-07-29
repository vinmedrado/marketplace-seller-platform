"""Serviço de alertas operacionais SellerOS.

PATCH 9/10 — configurações, histórico, dedupe e disparos para Telegram e
WhatsApp/Evolution API sem acoplar hard-fail aos módulos de marketplace.
"""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from sqlalchemy.orm import Session

from models.orm import AlertHistory, AlertSetting
from services.alert_dispatcher import DEFAULT_ALERT_TYPES, dispatch_alert, get_or_create_settings, provider_status

log = logging.getLogger("msp.alerts")
SEVERITIES = {"info", "warning", "critical"}
ALERT_TYPES = set(DEFAULT_ALERT_TYPES)


def _iso(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        return value
    return value.replace(microsecond=0).isoformat() + "Z"


def _clean_str(value: Any, max_len: int = 255) -> str | None:
    text = " ".join(str(value or "").replace("\x00", " ").split())
    return text[:max_len] if text else None


def _serialize_settings(row: AlertSetting) -> dict[str, Any]:
    return {
        "telegram_enabled": bool(row.telegram_enabled),
        "telegram_chat_id": row.telegram_chat_id,
        "whatsapp_enabled": bool(row.whatsapp_enabled),
        "whatsapp_phone": row.whatsapp_phone,
        "enabled_alert_types": row.enabled_alert_types_json or DEFAULT_ALERT_TYPES,
        "min_severity": row.min_severity or "warning",
        "quiet_hours_start": row.quiet_hours_start,
        "quiet_hours_end": row.quiet_hours_end,
        "providers": provider_status(),
        "updated_at": _iso(row.updated_at),
    }


def get_alert_settings(db: Session, tenant_id: str) -> dict[str, Any]:
    row = get_or_create_settings(db, tenant_id)
    db.commit()
    return _serialize_settings(row)


def update_alert_settings(db: Session, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    row = get_or_create_settings(db, tenant_id)
    enabled_types = payload.get("enabled_alert_types", payload.get("enabled_alert_types_json", row.enabled_alert_types_json or DEFAULT_ALERT_TYPES))
    if not isinstance(enabled_types, list):
        enabled_types = DEFAULT_ALERT_TYPES
    enabled_types = [str(t).upper() for t in enabled_types if str(t).upper() in ALERT_TYPES]
    row.telegram_enabled = bool(payload.get("telegram_enabled", row.telegram_enabled))
    row.telegram_chat_id = _clean_str(payload.get("telegram_chat_id", row.telegram_chat_id), 255)
    row.whatsapp_enabled = bool(payload.get("whatsapp_enabled", row.whatsapp_enabled))
    row.whatsapp_phone = _clean_str(payload.get("whatsapp_phone", row.whatsapp_phone), 64)
    row.enabled_alert_types_json = enabled_types or DEFAULT_ALERT_TYPES
    min_severity = str(payload.get("min_severity", row.min_severity or "warning")).lower()
    row.min_severity = min_severity if min_severity in SEVERITIES else "warning"
    row.quiet_hours_start = _clean_str(payload.get("quiet_hours_start", row.quiet_hours_start), 8)
    row.quiet_hours_end = _clean_str(payload.get("quiet_hours_end", row.quiet_hours_end), 8)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _serialize_settings(row)


def list_alert_history(db: Session, tenant_id: str, *, page: int = 1, page_size: int = 50) -> dict[str, Any]:
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 50), 100))
    q = db.query(AlertHistory).filter(AlertHistory.tenant_id == tenant_id).order_by(AlertHistory.created_at.desc())
    total = q.count()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [{
            "id": str(r.id),
            "alert_type": r.alert_type,
            "severity": r.severity,
            "title": r.title,
            "message": r.message,
            "provider": r.provider,
            "status": r.status,
            "dedupe_key": r.dedupe_key,
            "sent_at": _iso(r.sent_at),
            "error_message": r.error_message,
            "created_at": _iso(r.created_at),
        } for r in rows],
        "pagination": {"page": page, "page_size": page_size, "total": total},
        "providers": provider_status(),
    }


def format_alert_message(*, alert_type: str, severity: str, title: str, message: str) -> str:
    icon = "🚨" if severity == "critical" else "⚠️" if severity == "warning" else "ℹ️"
    label = "Crítico" if severity == "critical" else "Atenção" if severity == "warning" else "Informativo"
    return f"{icon} <b>SellerOS — Alerta {label}</b>\nTipo: {alert_type}\nTítulo: {title}\n\n{message}"[:3900]


def create_alert(db: Session, tenant_id: str, *, alert_type: str, severity: str = "warning", title: str, message: str, dedupe_key: str | None = None, force: bool = False) -> dict[str, Any]:
    alert_type = str(alert_type or "INFO").upper()
    severity = str(severity or "warning").lower()
    if severity not in SEVERITIES:
        severity = "warning"
    rendered = format_alert_message(alert_type=alert_type, severity=severity, title=title, message=message)
    try:
        result = dispatch_alert(db, tenant_id=tenant_id, alert_type=alert_type, severity=severity, title=title, message=rendered, dedupe_key=dedupe_key, force=force)
        log.info("alert_dispatch_completed", extra={"event": "alert_dispatch_completed", "tenant_id": str(tenant_id), "alert_type": alert_type, "severity": severity, "sent": result.sent, "skipped": result.skipped})
        return {"sent": result.sent, "skipped": result.skipped, "reason": result.reason, "provider_results": result.provider_results}
    except Exception as exc:  # noqa: BLE001
        # Segurança: alertas nunca derrubam fluxo de negócio.
        db.rollback()
        log.warning("alert_dispatch_failed_soft", extra={"event": "alert_dispatch_failed_soft", "tenant_id": str(tenant_id), "alert_type": alert_type, "error_type": type(exc).__name__})
        return {"sent": False, "skipped": True, "reason": "Falha não bloqueante no dispatcher de alertas.", "provider_results": []}


def send_test_alert(db: Session, tenant_id: str) -> dict[str, Any]:
    return create_alert(
        db,
        tenant_id,
        alert_type="SYNC_ERROR",
        severity="info",
        title="Alerta teste SellerOS",
        message="Este é um alerta teste. Se você recebeu, o canal está configurado corretamente.",
        dedupe_key=f"test:{tenant_id}:{int(datetime.utcnow().timestamp())}",
        force=True,
    )
