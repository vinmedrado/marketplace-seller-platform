"""Marketplace operational dashboard service.

PATCH 4/10 — consolida seller status, catálogo real, sync status e Action
Intelligence sem mock/fake data. Todas as consultas são filtradas por tenant.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.orm import MarketplaceConnection, OperationalEvent, Product
from services.action_intelligence_service import generate_marketplace_intelligence

MARKETPLACE = "mercadolivre"


def _iso(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        return value
    return value.replace(microsecond=0).isoformat() + "Z"


def _count_flag(db: Session, tenant_id: str, flag: str) -> int:
    rows = db.query(Product.health_flags_json).filter(Product.cliente_id == tenant_id, Product.marketplace == MARKETPLACE).all()
    total = 0
    for (flags,) in rows:
        if isinstance(flags, list) and flag in flags:
            total += 1
    return total


def _recent_event(db: Session, tenant_id: str, event_types: list[str]) -> OperationalEvent | None:
    return (
        db.query(OperationalEvent)
        .filter(OperationalEvent.tenant_id == tenant_id, OperationalEvent.event_type.in_(event_types))
        .order_by(OperationalEvent.created_at.desc())
        .first()
    )


def record_operational_event(db: Session, tenant_id: str, event_type: str, title: str, description: str = "", *, category: str = "marketplace_dashboard", severity: str = "info") -> None:
    """Registra eventos de leitura com throttling simples para evitar spam."""
    cutoff = datetime.utcnow() - timedelta(minutes=5)
    exists = (
        db.query(OperationalEvent.id)
        .filter(
            OperationalEvent.tenant_id == tenant_id,
            OperationalEvent.event_type == event_type,
            OperationalEvent.category == category,
            OperationalEvent.created_at >= cutoff,
        )
        .first()
    )
    if exists:
        return
    db.add(OperationalEvent(tenant_id=tenant_id, event_type=event_type, category=category, severity=severity, title=title, description=description))


def build_marketplace_summary(db: Session, tenant_id: str) -> dict[str, Any]:
    conn = (
        db.query(MarketplaceConnection)
        .filter_by(tenant_id=tenant_id, marketplace=MARKETPLACE, is_active=True)
        .order_by(MarketplaceConnection.updated_at.desc().nullslast())
        .first()
    )

    base = db.query(Product).filter(Product.cliente_id == tenant_id, Product.marketplace == MARKETPLACE)
    total = base.count()
    active = base.filter(Product.status == "active").count()
    paused = base.filter(Product.status == "paused").count()
    out_of_stock = base.filter(Product.available_quantity <= 0).count()
    low_stock = _count_flag(db, tenant_id, "LOW_STOCK")
    poor_health = _count_flag(db, tenant_id, "POOR_HEALTH")
    avg_price = db.query(func.avg(Product.price)).filter(Product.cliente_id == tenant_id, Product.marketplace == MARKETPLACE, Product.price > 0).scalar()
    total_units = db.query(func.coalesce(func.sum(Product.available_quantity), 0)).filter(Product.cliente_id == tenant_id, Product.marketplace == MARKETPLACE).scalar()
    last_synced_at = db.query(func.max(Product.last_synced_at)).filter(Product.cliente_id == tenant_id, Product.marketplace == MARKETPLACE).scalar()

    last_sync_event = _recent_event(db, tenant_id, ["catalog_synced", "sync_error"])
    error_event = _recent_event(db, tenant_id, ["sync_error"])
    intelligence = generate_marketplace_intelligence(db, tenant_id)
    top_risks = (intelligence.get("critical") or [])[:3] + (intelligence.get("warnings") or [])[:2]

    record_operational_event(db, tenant_id, "dashboard_summary_requested", "Resumo Marketplace consultado", "Dashboard operacional carregado com dados reais.")
    record_operational_event(db, tenant_id, "sync_status_read", "Status de sync consultado", "Status de sincronização exibido no cockpit.")
    db.commit()

    return {
        "seller": {
            "connected": bool(conn),
            "seller_id": conn.seller_id if conn else None,
            "nickname": conn.nickname if conn else None,
            "country_id": conn.country_id if conn else None,
            "connected_at": _iso(conn.connected_at) if conn else None,
            "token_expires_at": _iso(conn.token_expires_at) if conn else None,
            "last_sync_at": _iso(last_synced_at),
        },
        "catalog": {
            "total_products": total,
            "active_products": active,
            "paused_products": paused,
            "out_of_stock_products": out_of_stock,
            "low_stock_products": low_stock,
            "poor_health_products": poor_health,
            "avg_price": float(avg_price or 0),
            "total_inventory_units": int(total_units or 0),
        },
        "sync": {
            "last_synced_at": _iso(last_synced_at),
            "last_sync_status": "error" if error_event and (not last_sync_event or error_event.created_at >= last_sync_event.created_at) else ("success" if last_sync_event else "never_synced"),
            "last_sync_total": _extract_sync_total(last_sync_event.description if last_sync_event else ""),
            "last_sync_errors": 1 if error_event and (not last_sync_event or error_event.created_at >= last_sync_event.created_at) else 0,
        },
        "intelligence": {
            "critical_alerts_count": intelligence.get("summary", {}).get("critical", 0),
            "warnings_count": intelligence.get("summary", {}).get("warnings", 0),
            "opportunities_count": intelligence.get("summary", {}).get("opportunities", 0),
            "top_risks": top_risks,
            "message": intelligence.get("message"),
        },
    }


def _extract_sync_total(description: str) -> int | None:
    if not description:
        return None
    for token in description.split():
        if token.isdigit():
            return int(token)
    return None
