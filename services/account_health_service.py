"""PATCH 7/10 — Saúde da Conta ML em Tempo Real.

Score interno MarketPlace Seller Platform baseado em dados reais disponíveis na conexão Mercado Livre
+ catálogo sincronizado. Não representa score oficial Mercado Livre.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean
from typing import Any

import requests
from sqlalchemy.orm import Session

from config.settings import ML_BASE_URL
from models.orm import AccountHealthSnapshot, MarketplaceConnection, OperationalEvent, Product
from services.ml_token_service import MLTokenServiceError, get_connection, get_valid_access_token

log = logging.getLogger("msp.account_health")
MARKETPLACE = "mercadolivre"


class AccountHealthServiceError(Exception):
    pass


def _iso(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        return value
    return value.replace(microsecond=0).isoformat() + "Z"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct_from_reputation_metric(metric: Any) -> float | None:
    """Extrai taxa de métricas do seller_reputation quando disponível.

    A API pode retornar estruturas diferentes por site/conta. Este parser aceita:
    - {"rate": 0.01}
    - {"value": 0.01}
    - {"period": "...", "excluded": {...}, "value": ...}
    Se nada vier, retorna None para não inventar métrica.
    """
    if metric is None:
        return None
    if isinstance(metric, (int, float, str)):
        return _safe_float(metric)
    if isinstance(metric, dict):
        for key in ("rate", "value", "percentage", "percent"):
            parsed = _safe_float(metric.get(key))
            if parsed is not None:
                return parsed
        # Algumas respostas têm value dentro de subobjetos.
        for nested in metric.values():
            if isinstance(nested, dict):
                parsed = _pct_from_reputation_metric(nested)
                if parsed is not None:
                    return parsed
    return None


def _status_from_score(score: int) -> str:
    if score >= 90:
        return "EXCELENTE"
    if score >= 75:
        return "BOA"
    if score >= 60:
        return "ATENÇÃO"
    if score >= 40:
        return "RISCO"
    return "CRÍTICA"


def _reputation_component(level_id: str | None) -> float:
    if not level_id:
        return 72.0  # neutro quando indisponível; sinalizado no payload como null.
    normalized = str(level_id).lower()
    if "green" in normalized:
        return 100.0
    if "yellow" in normalized:
        return 72.0
    if "orange" in normalized:
        return 52.0
    if "red" in normalized:
        return 25.0
    return 70.0


def _rate_component(rate: float | None, *, warning: float, critical: float) -> float:
    if rate is None:
        return 75.0
    # APIs costumam retornar 0.02 para 2%; se vier 2, normaliza para 2%.
    r = rate / 100 if rate > 1 else rate
    if r <= warning:
        return 100.0
    if r >= critical:
        return 20.0
    span = max(critical - warning, 0.0001)
    return max(20.0, 100.0 - ((r - warning) / span) * 80.0)


def _quality_component(products: list[Product]) -> float:
    if not products:
        return 75.0
    total = len(products)
    paused = sum(1 for p in products if (p.status or "").lower() == "paused")
    out = sum(1 for p in products if int(p.available_quantity or p.estoque or 0) <= 0)
    poor = sum(1 for p in products if _safe_float(p.health) is not None and float(p.health) < 0.55)
    penalty = min(70.0, (paused / total) * 30 + (out / total) * 25 + (poor / total) * 35)
    return max(25.0, 100.0 - penalty)


def _score(level_id: str | None, cancellations_rate: float | None, claims_rate: float | None, delayed_rate: float | None, products: list[Product]) -> int:
    rep = _reputation_component(level_id)
    canc = _rate_component(cancellations_rate, warning=0.015, critical=0.06)
    claims = _rate_component(claims_rate, warning=0.02, critical=0.07)
    delayed = _rate_component(delayed_rate, warning=0.04, critical=0.12)
    quality = _quality_component(products)
    score = rep * 0.35 + canc * 0.20 + claims * 0.20 + delayed * 0.15 + quality * 0.10
    return int(round(max(0, min(100, score))))


def _record_event(db: Session, tenant_id: str, event_type: str, title: str, description: str = "", *, severity: str = "info", throttle_seconds: int = 0) -> None:
    if throttle_seconds:
        cutoff = datetime.utcnow() - timedelta(seconds=throttle_seconds)
        exists = db.query(OperationalEvent.id).filter(
            OperationalEvent.tenant_id == tenant_id,
            OperationalEvent.event_type == event_type,
            OperationalEvent.created_at >= cutoff,
        ).first()
        if exists:
            return
    db.add(OperationalEvent(
        tenant_id=tenant_id,
        event_type=event_type,
        category="account_health",
        severity=severity,
        title=title,
        description=description[:600],
    ))


def _build_alerts(*, score: int, status: str, level_id: str | None, cancellations_rate: float | None, claims_rate: float | None, delayed_rate: float | None, active: int, paused: int, out: int, poor: int) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    now = _iso(datetime.utcnow())

    def add(type_: str, severity: str, title: str, description: str, recommendation: str, value: Any, threshold: Any):
        alerts.append({
            "type": type_,
            "severity": severity,
            "title": title,
            "description": description,
            "recommendation": recommendation,
            "metric_value": value,
            "threshold": threshold,
            "created_at": now,
        })

    if score < 40:
        add("ACCOUNT_CRITICAL", "critical", "Saúde da conta crítica", "O score interno MarketPlace Seller Platform ficou abaixo de 40.", "Priorize reclamações, cancelamentos e atrasos antes de expandir catálogo.", score, 40)
    elif score < 60:
        add("ACCOUNT_RISK", "warning", "Conta em faixa de risco", "O score interno MarketPlace Seller Platform indica risco operacional.", "Revise os principais alertas e atue nos anúncios com pior saúde.", score, 60)

    if level_id and "red" in str(level_id).lower():
        add("REPUTATION_LOW", "critical", "Reputação Mercado Livre baixa", f"A reputação retornada pela API está em {level_id}.", "Investigue rapidamente reclamações, cancelamentos e atrasos recentes.", level_id, "yellow_or_green")
    elif level_id and "orange" in str(level_id).lower():
        add("REPUTATION_ATTENTION", "warning", "Reputação Mercado Livre em atenção", f"A reputação retornada pela API está em {level_id}.", "Acompanhe métricas de experiência e evite novas ocorrências negativas.", level_id, "green")

    if cancellations_rate is not None and cancellations_rate > 0.03:
        add("CANCELLATION_RATE_HIGH", "warning" if cancellations_rate < 0.06 else "critical", "Cancelamentos acima do limite interno", "A taxa de cancelamento disponível está alta para o padrão operacional definido.", "Revise estoque, prazo e disponibilidade antes de aceitar novas vendas.", cancellations_rate, 0.03)
    if claims_rate is not None and claims_rate > 0.03:
        add("CLAIMS_RATE_HIGH", "warning" if claims_rate < 0.07 else "critical", "Reclamações acima do limite interno", "A taxa de reclamações disponível está elevada.", "Atue nos pedidos com maior risco e revise comunicação/pós-venda.", claims_rate, 0.03)
    if delayed_rate is not None and delayed_rate > 0.06:
        add("DELAYED_HANDLING_RISK", "warning" if delayed_rate < 0.12 else "critical", "Risco de atraso de expedição", "A métrica de atraso disponível está acima do limite interno.", "Priorize separação e expedição dos pedidos mais antigos.", delayed_rate, 0.06)
    if paused > 0:
        add("PAUSED_PRODUCTS", "warning", "Produtos pausados no catálogo", f"Existem {paused} produtos pausados entre os anúncios sincronizados.", "Revise motivo da pausa e reative apenas anúncios com estoque/preço corretos.", paused, 0)
    if out > 0:
        add("OUT_OF_STOCK_PRODUCTS", "warning", "Produtos sem estoque", f"Existem {out} produtos sem estoque no catálogo sincronizado.", "Reponha estoque ou pause anúncios para evitar frustração do comprador.", out, 0)
    if poor > 0:
        add("POOR_LISTING_HEALTH", "warning", "Anúncios com saúde baixa", f"Existem {poor} produtos com health baixo quando a API retornou essa métrica.", "Melhore imagens, título, atributos e completude do anúncio.", poor, 0)
    if active == 0 and (paused > 0 or out > 0):
        add("NO_ACTIVE_CATALOG", "critical", "Catálogo sem anúncios ativos saudáveis", "Nenhum produto ativo foi identificado no catálogo sincronizado.", "Sincronize novamente e revise estoque/status dos anúncios.", active, 1)
    return alerts


def _trend(db: Session, tenant_id: str, current_score: int) -> dict[str, Any]:
    previous = db.query(AccountHealthSnapshot).filter(
        AccountHealthSnapshot.tenant_id == tenant_id,
    ).order_by(AccountHealthSnapshot.generated_at.desc()).limit(2).all()
    # A chamada ocorre antes do commit do snapshot atual, então previous[0] é o último histórico anterior.
    if not previous:
        return {"improving": False, "worsening": False, "stable": True, "delta": 0, "previous_score": None}
    prev_score = int(previous[0].score or current_score)
    delta = current_score - prev_score
    return {
        "improving": delta >= 3,
        "worsening": delta <= -3,
        "stable": abs(delta) < 3,
        "delta": delta,
        "previous_score": prev_score,
    }


def _fetch_user_payload(token: str, seller_id: str) -> dict[str, Any]:
    try:
        resp = requests.get(f"{ML_BASE_URL}/users/{seller_id}", headers=_headers(token), timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        log.warning("account_health_user_fetch_failed", extra={"event": "account_health_user_fetch_failed", "seller_id": str(seller_id), "error_type": type(exc).__name__})
        raise AccountHealthServiceError("Não foi possível consultar a reputação do seller no Mercado Livre agora.") from exc


def get_account_health(db: Session, tenant_id: str) -> dict[str, Any]:
    conn: MarketplaceConnection | None = get_connection(db, tenant_id)
    if not conn:
        raise AccountHealthServiceError("Conecte uma conta Mercado Livre antes de consultar saúde da conta.")
    if not conn.seller_id:
        raise AccountHealthServiceError("Conexão Mercado Livre sem seller_id.")

    try:
        token = get_valid_access_token(db, tenant_id)
    except MLTokenServiceError as exc:
        raise AccountHealthServiceError(str(exc)) from exc

    log.info("account_health_started", extra={"event": "account_health_started", "tenant_id": str(tenant_id), "seller_id": str(conn.seller_id)})
    user_payload = _fetch_user_payload(token, str(conn.seller_id))
    seller_rep = user_payload.get("seller_reputation") or {}
    metrics_payload = seller_rep.get("metrics") or {}
    level_id = seller_rep.get("level_id")

    cancellations_rate = _pct_from_reputation_metric(metrics_payload.get("cancellations") or seller_rep.get("cancellations"))
    claims_rate = _pct_from_reputation_metric(metrics_payload.get("claims") or seller_rep.get("claims"))
    delayed_rate = _pct_from_reputation_metric(metrics_payload.get("delayed_handling_time") or seller_rep.get("delayed_handling_time"))

    products = db.query(Product).filter(
        Product.cliente_id == tenant_id,
        Product.marketplace == MARKETPLACE,
    ).all()
    active_products = sum(1 for p in products if (p.status or "").lower() == "active")
    paused_products = sum(1 for p in products if (p.status or "").lower() == "paused")
    out_of_stock_products = sum(1 for p in products if int(p.available_quantity or p.estoque or 0) <= 0)
    poor_health_products = sum(1 for p in products if _safe_float(p.health) is not None and float(p.health) < 0.55)

    score = _score(level_id, cancellations_rate, claims_rate, delayed_rate, products)
    status = _status_from_score(score)
    alerts = _build_alerts(
        score=score,
        status=status,
        level_id=level_id,
        cancellations_rate=cancellations_rate,
        claims_rate=claims_rate,
        delayed_rate=delayed_rate,
        active=active_products,
        paused=paused_products,
        out=out_of_stock_products,
        poor=poor_health_products,
    )
    trends = _trend(db, tenant_id, score)

    snapshot = AccountHealthSnapshot(
        tenant_id=tenant_id,
        marketplace_connection_id=conn.id,
        score=score,
        status=status,
        reputation_level=level_id,
        cancellations_rate=cancellations_rate,
        claims_rate=claims_rate,
        delayed_rate=delayed_rate,
        active_products=active_products,
        paused_products=paused_products,
        poor_health_products=poor_health_products,
        raw_payload_json={
            "mercadolivre_user": user_payload,
            "metrics_available": {
                "cancellations_rate": cancellations_rate is not None,
                "claims_rate": claims_rate is not None,
                "delayed_rate": delayed_rate is not None,
            },
            "out_of_stock_products": out_of_stock_products,
            "alerts": alerts,
        },
        generated_at=datetime.utcnow(),
    )
    db.add(snapshot)

    _record_event(db, tenant_id, "account_health_generated", "Saúde da conta gerada", f"Score interno MarketPlace Seller Platform: {score} ({status}).", throttle_seconds=180)
    if any(a["severity"] == "critical" for a in alerts):
        _record_event(db, tenant_id, "account_health_critical", "Risco crítico na saúde da conta", "Alertas críticos foram detectados no monitoramento da conta.", severity="critical", throttle_seconds=3600)
    elif alerts:
        _record_event(db, tenant_id, "account_health_warning", "Alertas de saúde da conta", "Alertas preventivos foram detectados no monitoramento da conta.", severity="warning", throttle_seconds=1800)
    if level_id and trends.get("worsening"):
        _record_event(db, tenant_id, "reputation_drop_detected", "Possível queda de saúde operacional", "O score interno caiu em relação ao snapshot anterior.", severity="warning", throttle_seconds=3600)
    if delayed_rate is not None and delayed_rate > 0.06:
        _record_event(db, tenant_id, "shipping_risk_detected", "Risco de expedição detectado", "Atraso operacional acima do limite interno.", severity="warning", throttle_seconds=3600)

    if status in {"RISCO", "CRÍTICA"}:
        try:
            from services.alerts_service import create_alert
            create_alert(
                db,
                tenant_id,
                alert_type="ACCOUNT_HEALTH_RISK",
                severity="critical" if status == "CRÍTICA" else "warning",
                title=f"Saúde da conta em {status}",
                message=f"Score interno MarketPlace Seller Platform: {score}/100. Revise reclamações, cancelamentos, expedição e qualidade dos anúncios.",
                dedupe_key=f"account:{tenant_id}:ACCOUNT_HEALTH_RISK",
            )
        except Exception:
            log.warning("account_health_alert_failed_soft", extra={"event": "account_health_alert_failed_soft", "tenant_id": str(tenant_id)})

    db.commit()
    db.refresh(snapshot)

    response = {
        "score": score,
        "status": status,
        "score_label": "Score interno MarketPlace Seller Platform",
        "official_score": False,
        "reputation_level": level_id,
        "metrics": {
            "cancellations_rate": cancellations_rate,
            "claims_rate": claims_rate,
            "delayed_rate": delayed_rate,
            "active_products": active_products,
            "paused_products": paused_products,
            "out_of_stock_products": out_of_stock_products,
            "poor_health_products": poor_health_products,
        },
        "alerts": alerts,
        "trends": trends,
        "seller": {
            "seller_id": conn.seller_id,
            "nickname": conn.nickname,
            "country_id": conn.country_id,
        },
        "data_availability": {
            "cancellations_rate": cancellations_rate is not None,
            "claims_rate": claims_rate is not None,
            "delayed_rate": delayed_rate is not None,
            "listing_health_from_catalog": bool(products),
        },
        "generated_at": _iso(snapshot.generated_at),
    }
    log.info("account_health_completed", extra={"event": "account_health_completed", "tenant_id": str(tenant_id), "score": score, "status": status})
    return response
