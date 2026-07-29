"""PATCH 11/15 — Previsão de Demanda + Ponto de Recompra.

Heurística estatística inicial, sem ML fake. Usa somente dados reais já
persistidos no MarketPlace Seller Platform: estoque atual, sold_quantity, histórico de snapshots e
última sincronização do catálogo.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import isfinite
from statistics import median
from typing import Any

from sqlalchemy.orm import Session

from models.orm import (
    ActionRecommendation,
    DemandForecastSnapshot,
    OperationalEvent,
    Product,
)

log = logging.getLogger("msp.demand_forecast")

DEFAULT_LEAD_TIME_DAYS = 7
LOW_STOCK_DAYS = 14
CRITICAL_STOCK_DAYS = 7
SLOW_MOVING_DAILY_SALES = 0.05


class DemandForecastError(Exception):
    pass


def _now() -> datetime:
    return datetime.utcnow()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        result = float(value)
        return result if isfinite(result) else default
    except Exception:
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def _iso(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        return value
    return value.replace(microsecond=0).isoformat() + "Z"


def _product_title(product: Product) -> str:
    return product.title or product.titulo or product.external_product_id or str(product.id)


def _product_payload(product: Product) -> dict[str, Any]:
    return {
        "id": str(product.id),
        "external_product_id": product.external_product_id,
        "title": _product_title(product),
        "thumbnail": product.thumbnail,
        "permalink": product.permalink,
        "price": _float(product.price or product.preco_base),
        "available_quantity": _int(product.available_quantity or product.estoque),
        "sold_quantity": _int(product.sold_quantity),
        "status": product.status,
        "last_synced_at": _iso(product.last_synced_at),
    }


def _historical_snapshots(db: Session, tenant_id: str, product_id: str, limit: int = 8) -> list[DemandForecastSnapshot]:
    return list(
        db.query(DemandForecastSnapshot)
        .filter(
            DemandForecastSnapshot.tenant_id == tenant_id,
            DemandForecastSnapshot.product_id == product_id,
        )
        .order_by(DemandForecastSnapshot.generated_at.desc())
        .limit(limit)
        .all()
    )


def _estimate_window_days(product: Product, previous: list[DemandForecastSnapshot]) -> float:
    """Calcula janela conservadora para sold_quantity acumulado.

    Mercado Livre retorna sold_quantity acumulado do anúncio. Sem histórico longo,
    usamos uma janela operacional conservadora para não inflar demanda. Quando já
    existem snapshots, usamos idade entre snapshots para melhorar tendência.
    """
    if product.last_synced_at and previous:
        oldest = previous[-1].generated_at
        try:
            days = max(1.0, (_now() - oldest.replace(tzinfo=None)).total_seconds() / 86400)
            return min(max(days, 7.0), 90.0)
        except Exception:
            pass
    if product.criado_em:
        try:
            days = max(1.0, (_now() - product.criado_em.replace(tzinfo=None)).total_seconds() / 86400)
            return min(max(days, 14.0), 90.0)
        except Exception:
            pass
    return 30.0


def _avg_daily_sales(product: Product, previous: list[DemandForecastSnapshot]) -> tuple[float, str, float]:
    sold = _int(product.sold_quantity)
    window_days = _estimate_window_days(product, previous)
    base_rate = sold / window_days if window_days > 0 else 0.0

    if previous:
        recent_rates = [_float(s.avg_daily_sales) for s in previous[:4] if s.avg_daily_sales is not None]
        recent_rates = [r for r in recent_rates if r >= 0]
        if recent_rates:
            smoothed = (base_rate * 0.55) + (median(recent_rates) * 0.45)
            return round(smoothed, 4), "history_smoothed", min(0.86, 0.52 + (len(recent_rates) * 0.07))
    if sold <= 0:
        return 0.0, "no_sales_history", 0.35
    return round(base_rate, 4), "sold_quantity_window_estimate", 0.48


def _trend(current_rate: float, previous: list[DemandForecastSnapshot]) -> str:
    if len(previous) < 2:
        return "insufficient_history"
    recent = [_float(s.avg_daily_sales) for s in previous[:3] if s.avg_daily_sales is not None]
    older = [_float(s.avg_daily_sales) for s in previous[3:6] if s.avg_daily_sales is not None]
    if not recent or not older:
        return "insufficient_history"
    recent_avg = sum(recent) / len(recent)
    older_avg = sum(older) / len(older)
    baseline = max(older_avg, 0.01)
    delta = (recent_avg - older_avg) / baseline
    if delta > 0.18 or current_rate > older_avg * 1.25:
        return "increasing"
    if delta < -0.18 or current_rate < older_avg * 0.75:
        return "decreasing"
    return "stable"


def _risk(avg_daily_sales: float, available: int, days_remaining: float | None, trend: str) -> str:
    if available <= 0:
        return "critical"
    if avg_daily_sales <= 0:
        return "low"
    if days_remaining is not None and days_remaining <= CRITICAL_STOCK_DAYS:
        return "critical"
    if days_remaining is not None and days_remaining <= LOW_STOCK_DAYS:
        return "high" if trend == "increasing" else "medium"
    if trend == "increasing" and days_remaining is not None and days_remaining <= 21:
        return "medium"
    return "low"


def _alerts(product: Product, forecast: dict[str, Any]) -> list[dict[str, Any]]:
    title = _product_title(product)
    alerts: list[dict[str, Any]] = []
    risk = forecast["stock_risk"]
    days = forecast.get("estimated_days_remaining")
    avg = forecast.get("avg_daily_sales") or 0
    available = _int(product.available_quantity or product.estoque)
    if risk in {"critical", "high"}:
        alerts.append({
            "type": "STOCKOUT_RISK",
            "severity": "critical" if risk == "critical" else "warning",
            "title": "Risco de ruptura de estoque",
            "description": f"{title} pode ficar sem estoque em {days} dias." if days is not None else f"{title} está com estoque crítico.",
            "recommended_action": "Planeje reposição ou ajuste a exposição do anúncio antes da ruptura.",
        })
    if available <= forecast.get("reorder_point", 0) and avg > 0:
        alerts.append({
            "type": "REORDER_RECOMMENDED",
            "severity": "warning",
            "title": "Recompra recomendada",
            "description": "Estoque atual está abaixo do ponto de recompra calculado.",
            "recommended_action": f"Repor pelo menos {forecast.get('reorder_point')} unidades considerando lead time de {forecast.get('lead_time_days')} dias.",
        })
    if forecast.get("demand_trend") == "increasing" and avg > 0:
        alerts.append({
            "type": "HIGH_DEMAND_SURGE",
            "severity": "info",
            "title": "Demanda em crescimento",
            "description": "A velocidade estimada de vendas está acima dos snapshots anteriores.",
            "recommended_action": "Acompanhe estoque e preço para evitar perder tração comercial.",
        })
    if avg <= SLOW_MOVING_DAILY_SALES and available > 0:
        alerts.append({
            "type": "SLOW_MOVING_PRODUCT",
            "severity": "info",
            "title": "Produto com baixa velocidade de venda",
            "description": "O produto possui estoque, mas pouca ou nenhuma venda observada.",
            "recommended_action": "Revisar título, preço, exposição, frete e competitividade antes de recomprar.",
        })
    return alerts


def _recommendation(product: Product, forecast: dict[str, Any]) -> str:
    risk = forecast["stock_risk"]
    days = forecast.get("estimated_days_remaining")
    reorder = forecast.get("reorder_point")
    trend = forecast.get("demand_trend")
    if risk == "critical":
        return f"Prioridade alta: estoque pode acabar rapidamente. Recomenda-se recompra imediata e revisão do anúncio. Ponto de recompra: {reorder} unidades."
    if risk == "high":
        return f"Recompra recomendada: estoque estimado para {days} dias. Antecipe reposição antes de perder vendas."
    if trend == "increasing":
        return "Demanda em crescimento. Acompanhe estoque com frequência e considere elevar o lote de reposição."
    if forecast.get("avg_daily_sales", 0) <= SLOW_MOVING_DAILY_SALES:
        return "Produto lento. Evite recompra sem revisar preço, título, frete e competitividade."
    return "Estoque sem risco crítico no momento. Continue monitorando após novas sincronizações."


def _projected_stock_points(available: int, avg_daily_sales: float, days: int = 30) -> list[dict[str, Any]]:
    points = []
    for day in range(0, days + 1, 3):
        stock = max(0, available - (avg_daily_sales * day))
        points.append({"day": day, "projected_stock": round(stock, 2)})
    return points


def calculate_product_forecast(db: Session, tenant_id: str, product: Product, lead_time_days: int = DEFAULT_LEAD_TIME_DAYS, persist: bool = True) -> dict[str, Any]:
    previous = _historical_snapshots(db, tenant_id, str(product.id))
    available = _int(product.available_quantity or product.estoque)
    avg_daily, method, confidence = _avg_daily_sales(product, previous)
    days_remaining = None if avg_daily <= 0 else round(available / avg_daily, 1)
    reorder_point = int(round(max(0, avg_daily * max(1, lead_time_days))))
    trend = _trend(avg_daily, previous)
    risk = _risk(avg_daily, available, days_remaining, trend)

    confidence = confidence
    if trend == "insufficient_history":
        confidence = min(confidence, 0.55)
    if product.last_synced_at is None:
        confidence = min(confidence, 0.45)

    forecast = {
        "avg_daily_sales": round(avg_daily, 4),
        "estimated_days_remaining": days_remaining,
        "reorder_point": reorder_point,
        "lead_time_days": lead_time_days,
        "demand_trend": trend,
        "stock_risk": risk,
        "confidence": round(confidence, 2),
        "method": method,
        "projected_stock": _projected_stock_points(available, avg_daily),
    }
    alerts = _alerts(product, forecast)
    forecast["alerts_count"] = len(alerts)

    if persist:
        snapshot = DemandForecastSnapshot(
            tenant_id=tenant_id,
            product_id=str(product.id),
            avg_daily_sales=forecast["avg_daily_sales"],
            estimated_days_remaining=forecast["estimated_days_remaining"],
            reorder_point=forecast["reorder_point"],
            demand_trend=forecast["demand_trend"],
            stock_risk=forecast["stock_risk"],
            confidence=forecast["confidence"],
            raw_metrics_json={
                "available_quantity": available,
                "sold_quantity": _int(product.sold_quantity),
                "method": method,
                "lead_time_days": lead_time_days,
                "last_synced_at": _iso(product.last_synced_at),
                "previous_snapshots": len(previous),
                "projected_stock": forecast["projected_stock"],
            },
            generated_at=_now(),
        )
        db.add(snapshot)
        _persist_intelligence_signals(db, tenant_id, product, forecast, alerts)
        db.flush()
    return {"product": _product_payload(product), "forecast": forecast, "alerts": alerts, "recommendation": _recommendation(product, forecast), "generated_at": _iso(_now())}


def _persist_intelligence_signals(db: Session, tenant_id: str, product: Product, forecast: dict[str, Any], alerts: list[dict[str, Any]]) -> None:
    for alert in alerts:
        severity = alert.get("severity", "info")
        db.add(OperationalEvent(
            tenant_id=tenant_id,
            event_type=alert.get("type", "DEMAND_FORECAST_SIGNAL"),
            category="demand_forecast",
            severity=severity,
            title=alert.get("title", "Sinal de demanda"),
            description=alert.get("description"),
            related_product_id=str(product.id),
            impact_estimated=0,
        ))
        if alert.get("type") in {"STOCKOUT_RISK", "REORDER_RECOMMENDED"}:
            db.add(ActionRecommendation(
                tenant_id=tenant_id,
                product_id=str(product.id),
                category="inventory",
                priority="HIGH" if severity == "critical" else "MEDIUM",
                origin="Demand Forecast Engine",
                title=f"{alert.get('title')} — {_product_title(product)}",
                explanation=alert.get("description"),
                recommended_action=alert.get("recommended_action"),
                next_best_action=alert.get("recommended_action"),
                confidence=forecast.get("confidence", 0.5),
                status="pending",
            ))
    # alerta externo não deve quebrar previsão
    try:
        if forecast.get("stock_risk") in {"critical", "high"}:
            from services.alert_dispatcher import dispatch_alert
            dispatch_alert(
                db,
                tenant_id=tenant_id,
                alert_type="STOCKOUT_RISK",
                severity="critical" if forecast.get("stock_risk") == "critical" else "warning",
                title="Risco de ruptura de estoque",
                message=(
                    "🚨 MarketPlace Seller Platform — Risco de Estoque\n"
                    f"Produto: {_product_title(product)}\n"
                    f"Estoque atual: {_int(product.available_quantity or product.estoque)}\n"
                    f"Dias restantes estimados: {forecast.get('estimated_days_remaining')}\n"
                    f"Ação sugerida: recomprar ou ajustar exposição do anúncio."
                ),
                dedupe_key=f"product:{product.id}:STOCKOUT_RISK",
            )
    except Exception as exc:  # pragma: no cover
        log.warning("demand_forecast_alert_dispatch_failed", extra={"tenant_id": str(tenant_id), "error": type(exc).__name__})


def get_product_forecast(db: Session, tenant_id: str, product_id: str, lead_time_days: int = DEFAULT_LEAD_TIME_DAYS) -> dict[str, Any]:
    product = db.query(Product).filter(Product.id == product_id, Product.cliente_id == tenant_id).first()
    if not product:
        raise DemandForecastError("Produto não encontrado para este tenant.")
    return calculate_product_forecast(db, tenant_id, product, lead_time_days=lead_time_days, persist=False)


def forecast_overview(db: Session, tenant_id: str, limit: int = 80, lead_time_days: int = DEFAULT_LEAD_TIME_DAYS) -> dict[str, Any]:
    products = list(
        db.query(Product)
        .filter(Product.cliente_id == tenant_id)
        .order_by(Product.updated_at.desc().nullslast())
        .limit(max(1, min(limit, 150)))
        .all()
    )
    rows = [calculate_product_forecast(db, tenant_id, p, lead_time_days=lead_time_days, persist=False) for p in products]

    def days_key(row: dict[str, Any]) -> float:
        days = row["forecast"].get("estimated_days_remaining")
        return 999999 if days is None else float(days)

    high_risk = [r for r in rows if r["forecast"].get("stock_risk") in {"critical", "high"}]
    ending_soon = sorted([r for r in rows if r["forecast"].get("estimated_days_remaining") is not None], key=days_key)[:10]
    best_sellers = sorted(rows, key=lambda r: r["forecast"].get("avg_daily_sales") or 0, reverse=True)[:10]
    slow_movers = [r for r in rows if (r["forecast"].get("avg_daily_sales") or 0) <= SLOW_MOVING_DAILY_SALES and (r["product"].get("available_quantity") or 0) > 0]
    opportunities = [r for r in rows if r["forecast"].get("demand_trend") == "increasing"]

    return {
        "summary": {
            "products_analyzed": len(rows),
            "high_risk_count": len(high_risk),
            "ending_soon_count": len([r for r in rows if (r["forecast"].get("estimated_days_remaining") or 999999) <= LOW_STOCK_DAYS]),
            "reorder_recommended_count": len([r for r in rows if any(a.get("type") == "REORDER_RECOMMENDED" for a in r["alerts"])]),
            "increasing_demand_count": len(opportunities),
            "slow_moving_count": len(slow_movers),
            "lead_time_days": lead_time_days,
        },
        "products": rows,
        "high_risk": high_risk[:12],
        "ending_soon": ending_soon,
        "best_sellers": best_sellers,
        "slow_movers": slow_movers[:10],
        "opportunities": opportunities[:10],
        "generated_at": _iso(_now()),
        "disclaimer": "Previsão heurística interna MarketPlace Seller Platform baseada em dados disponíveis. Não é garantia de vendas futuras.",
    }


def refresh_forecast_snapshots(
    db: Session,
    tenant_id: str,
    limit: int = 80,
    lead_time_days: int = DEFAULT_LEAD_TIME_DAYS,
) -> dict[str, Any]:
    products = list(
        db.query(Product)
        .filter(Product.cliente_id == tenant_id)
        .order_by(Product.updated_at.desc().nullslast())
        .limit(max(1, min(limit, 150)))
        .all()
    )
    rows = [
        calculate_product_forecast(db, tenant_id, product, lead_time_days=lead_time_days, persist=True)
        for product in products
    ]
    db.add(OperationalEvent(
        tenant_id=tenant_id,
        event_type="demand_forecast_snapshots_refreshed",
        category="demand_forecast",
        severity="info",
        title="Snapshots de demanda atualizados",
        description=f"{len(rows)} produtos persistidos pelo comando explícito de atualização.",
    ))
    db.commit()
    return {"status": "ok", "processed": len(rows), "generated_at": _iso(_now())}
