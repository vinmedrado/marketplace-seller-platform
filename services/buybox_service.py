"""PATCH 8/10 — Buy Box Probability Score service.

Gera score interno SellerOS por produto com base em catálogo sincronizado,
última saúde da conta e referência pública de mercado quando disponível.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from ml.models.buybox_scorer import score_buybox
from models.orm import (
    AccountHealthSnapshot,
    ActionRecommendation,
    BuyBoxScoreSnapshot,
    OperationalEvent,
    Product,
)

log = logging.getLogger("msp.buybox")


class BuyBoxServiceError(Exception):
    pass


def _iso(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        return value
    return value.replace(microsecond=0).isoformat() + "Z"


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _product_to_dict(product: Product) -> dict[str, Any]:
    return {
        "id": str(product.id),
        "external_product_id": product.external_product_id,
        "title": product.title or product.titulo,
        "price": _float(product.price or product.preco_base, 0),
        "preco_base": _float(product.preco_base or product.price, 0),
        "cost": _float(product.custo, 0) if product.custo is not None else None,
        "available_quantity": int(product.available_quantity or product.estoque or 0),
        "sold_quantity": int(product.sold_quantity or 0),
        "status": product.status,
        "health": _float(product.health, None) if product.health is not None else None,
        "free_shipping": bool(product.free_shipping),
        "listing_type_id": product.listing_type_id,
        "thumbnail": product.thumbnail,
        "permalink": product.permalink,
        "health_flags": product.health_flags_json or [],
    }


def _latest_health(db: Session, tenant_id: str) -> dict[str, Any] | None:
    row = db.query(AccountHealthSnapshot).filter_by(tenant_id=tenant_id).order_by(AccountHealthSnapshot.generated_at.desc()).first()
    if not row:
        return None
    return {
        "score": row.score,
        "status": row.status,
        "reputation_level": row.reputation_level,
        "generated_at": _iso(row.generated_at),
    }


def _market_reference(product: Product) -> dict[str, Any]:
    """Consulta referência pública de mercado com fallback nulo.

    A falha do scanner não deve impedir o score: apenas reduz confiança no scorer.
    """
    title = (product.title or product.titulo or "").strip()
    if len(title) < 3:
        return {"available": False, "reason": "Título insuficiente para consulta pública."}
    try:
        from services.pricing_intelligence_service import market_scan
        result = market_scan(title[:90], None)
        dist = result.get("price_distribution") or {}
        return {
            "available": bool(result.get("analyzed_count")),
            "source": "mercadolivre_public_search",
            "analyzed_count": result.get("analyzed_count", 0),
            "median": dist.get("median"),
            "p25": dist.get("p25"),
            "p75": dist.get("p75"),
            "avg": dist.get("avg"),
            "top_competitors": result.get("top_competitors", [])[:5],
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("buybox_market_reference_unavailable", extra={"event": "buybox_market_reference_unavailable", "reason": type(exc).__name__})
        return {"available": False, "reason": "Referência pública de mercado indisponível no momento."}


def _record_event(db: Session, tenant_id: str, event_type: str, title: str, description: str = "", *, severity: str = "info", product_id: str | None = None, throttle_seconds: int = 0) -> None:
    if throttle_seconds:
        cutoff = datetime.utcnow() - timedelta(seconds=throttle_seconds)
        exists = db.query(OperationalEvent.id).filter(
            OperationalEvent.tenant_id == tenant_id,
            OperationalEvent.event_type == event_type,
            OperationalEvent.related_product_id == product_id,
            OperationalEvent.created_at >= cutoff,
        ).first()
        if exists:
            return
    db.add(OperationalEvent(
        tenant_id=tenant_id,
        event_type=event_type,
        category="buybox",
        severity=severity,
        title=title,
        description=description[:700],
        related_product_id=product_id,
    ))


def _create_action_if_needed(db: Session, tenant_id: str, product: Product, result: dict[str, Any]) -> None:
    probability = float(result.get("current_probability") or 0)
    best = result.get("best_scenario") or {}
    if probability >= 65 and not (best.get("variation_percent", 0) < 0 and best.get("estimated_probability", 0) - probability >= 8):
        return
    if probability < 45:
        action_type = "BUYBOX_RISK"
        priority = "HIGH"
        title = f"Risco de Buy Box: {product.title or product.titulo}"
        explanation = "Score interno SellerOS indica baixa probabilidade estimada de Buy Box no preço atual."
    elif best.get("variation_percent", 0) < 0:
        action_type = "PRICE_ADJUSTMENT_RECOMMENDED"
        priority = "MEDIUM"
        title = f"Ajuste de preço sugerido: {product.title or product.titulo}"
        explanation = f"Simulação interna indica que ajustar {abs(best.get('variation_percent', 0))}% pode elevar o score estimado."
    else:
        action_type = "BUYBOX_OPPORTUNITY"
        priority = "MEDIUM"
        title = f"Oportunidade de Buy Box: {product.title or product.titulo}"
        explanation = "Há sinais operacionais que podem melhorar competitividade do anúncio."
    existing = db.query(ActionRecommendation.id).filter(
        ActionRecommendation.tenant_id == tenant_id,
        ActionRecommendation.product_id == product.id,
        ActionRecommendation.category == "buybox",
        ActionRecommendation.status == "pending",
    ).first()
    if existing:
        return
    db.add(ActionRecommendation(
        tenant_id=tenant_id,
        product_id=product.id,
        category="buybox",
        priority=priority,
        origin="Buy Box Probability Score",
        title=title,
        explanation=explanation,
        recommended_action=result.get("recommendation"),
        next_best_action="Ver simulação Buy Box",
        expected_impact=0,
        confidence=(float(result.get("confidence") or 0) / 100),
        status="pending",
    ))
    _record_event(db, tenant_id, action_type, title, explanation, severity="warning" if priority != "HIGH" else "critical", product_id=str(product.id), throttle_seconds=3600)


def get_product_buybox_score(db: Session, tenant_id: str, product_id: str, *, refresh_market: bool = True) -> dict[str, Any]:
    product = db.query(Product).filter(Product.id == product_id, Product.cliente_id == tenant_id).first()
    if not product:
        raise BuyBoxServiceError("Produto não encontrado para este tenant.")
    product_payload = _product_to_dict(product)
    account_health = _latest_health(db, tenant_id)
    market_ref = _market_reference(product) if refresh_market else {"available": False, "reason": "Consulta de mercado desativada."}
    cost = product_payload.get("cost") if product_payload.get("cost") and product_payload.get("cost") > 0 else None
    score = score_buybox(product_payload, account_health=account_health, market_reference=market_ref, cost=cost)
    now = datetime.utcnow()
    payload = {
        "product_id": str(product.id),
        "external_product_id": product.external_product_id,
        "title": product.title or product.titulo,
        "current_price": product_payload["price"],
        "current_probability": score["probability"],
        "confidence": score["confidence"],
        "factors": score["factors"],
        "positive_factors": score["positive_factors"],
        "negative_factors": score["negative_factors"],
        "simulated_prices": score["simulated_prices"],
        "best_scenario": score["best_scenario"],
        "recommendation": score["recommendation"],
        "market_reference": market_ref,
        "account_health": account_health,
        "disclaimer": score["disclaimer"],
        "generated_at": _iso(now),
    }
    db.add(BuyBoxScoreSnapshot(
        tenant_id=tenant_id,
        product_id=product.id,
        external_product_id=product.external_product_id,
        current_price=payload["current_price"],
        current_probability=payload["current_probability"],
        confidence=payload["confidence"],
        recommendation=payload["recommendation"],
        factors_json=payload["factors"],
        simulations_json=payload["simulated_prices"],
        generated_at=now,
    ))
    _create_action_if_needed(db, tenant_id, product, payload)
    probability = float(payload.get("current_probability") or 0)
    try:
        from services.alerts_service import create_alert
        if probability < 45:
            create_alert(db, tenant_id, alert_type="BUYBOX_RISK", severity="warning", title="Risco de Buy Box", message=f"{product.title or product.titulo} está com probabilidade interna estimada baixa ({probability:.0f}%). Veja simulações antes de ajustar preço.", dedupe_key=f"product:{product.id}:BUYBOX_RISK")
        elif (payload.get("best_scenario") or {}).get("variation_percent", 0) < 0 and ((payload.get("best_scenario") or {}).get("estimated_probability", 0) - probability) >= 8:
            create_alert(db, tenant_id, alert_type="BUYBOX_OPPORTUNITY", severity="info", title="Oportunidade de Buy Box", message=f"{product.title or product.titulo} tem uma simulação de ajuste com melhora relevante no score interno.", dedupe_key=f"product:{product.id}:BUYBOX_OPPORTUNITY")
    except Exception:
        log.warning("buybox_alert_failed_soft", extra={"event": "buybox_alert_failed_soft", "tenant_id": str(tenant_id), "product_id": str(product.id)})
    _record_event(db, tenant_id, "buybox_score_generated", "Buy Box Score gerado", f"Score interno gerado para {product.external_product_id or product.id}.", product_id=str(product.id), throttle_seconds=900)
    db.commit()
    return payload


def buybox_overview(db: Session, tenant_id: str, *, limit: int = 30) -> dict[str, Any]:
    products = db.query(Product).filter(Product.cliente_id == tenant_id).order_by(Product.updated_at.desc()).limit(max(1, min(limit, 50))).all()
    items: list[dict[str, Any]] = []
    for product in products:
        try:
            # Overview usa referência interna sem bater API pública para não gerar volume excessivo.
            product_payload = _product_to_dict(product)
            account_health = _latest_health(db, tenant_id)
            score = score_buybox(product_payload, account_health=account_health, market_reference={"available": False}, cost=product_payload.get("cost"))
            best = score.get("best_scenario") or {}
            items.append({
                "product_id": str(product.id),
                "external_product_id": product.external_product_id,
                "title": product.title or product.titulo,
                "thumbnail": product.thumbnail,
                "current_price": product_payload["price"],
                "current_probability": score["probability"],
                "confidence": score["confidence"],
                "recommendation": score["recommendation"],
                "best_adjustment_percent": best.get("variation_percent"),
                "best_adjustment_price": best.get("price"),
                "best_adjustment_probability": best.get("estimated_probability"),
                "risk_level": "alto" if score["probability"] < 45 else "médio" if score["probability"] < 65 else "baixo",
            })
        except Exception as exc:  # noqa: BLE001
            log.warning("buybox_overview_item_failed", extra={"event": "buybox_overview_item_failed", "product_id": str(product.id), "reason": type(exc).__name__})
    high_risk = [i for i in items if i["current_probability"] < 45]
    opportunities = [i for i in items if (i.get("best_adjustment_probability") or 0) - i["current_probability"] >= 5]
    best_adjustment = max(items, key=lambda i: ((i.get("best_adjustment_probability") or 0) - i["current_probability"]), default=None)
    _record_event(db, tenant_id, "buybox_overview_requested", "Overview Buy Box consultado", "Resumo de probabilidade interna de Buy Box solicitado.", throttle_seconds=600)
    db.commit()
    return {
        "summary": {
            "products_analyzed": len(items),
            "high_risk": len(high_risk),
            "opportunities": len(opportunities),
            "lowest_probability": min([i["current_probability"] for i in items], default=None),
            "best_adjustment_suggested": best_adjustment,
        },
        "items": sorted(items, key=lambda i: i["current_probability"]),
        "high_risk": sorted(high_risk, key=lambda i: i["current_probability"]),
        "opportunities": sorted(opportunities, key=lambda i: (i.get("best_adjustment_probability") or 0) - i["current_probability"], reverse=True),
        "disclaimer": "Score interno SellerOS. Não é métrica oficial do Mercado Livre.",
        "generated_at": _iso(datetime.utcnow()),
    }
