"""PATCH 12/15 — Reconciliação Financeira Mercado Livre.

MVP operacional que usa dados financeiros/pedidos disponíveis na API Mercado
Livre, sem inventar integração bancária. Quando a API não retorna uma métrica,
o campo permanece nulo e a qualidade dos dados explica a limitação.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from math import isfinite
from typing import Any

import requests
from sqlalchemy.orm import Session

from config.settings import ML_BASE_URL
from models.orm import (
    ActionRecommendation,
    FinancialReconciliationSnapshot,
    MarketplaceConnection,
    OperationalEvent,
)
from services.ml_token_service import MLTokenServiceError, get_connection, get_valid_access_token

log = logging.getLogger("msp.finance.reconciliation")

MAX_RANGE_DAYS = 92
ORDER_LIMIT = 50
MAX_PAGES = 8


class FinancialReconciliationError(Exception):
    pass


def _now() -> datetime:
    return datetime.utcnow()


def _iso(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    return value.replace(microsecond=0).isoformat() + "Z"


def _decimal(value: Any) -> Decimal | None:
    try:
        if value is None or value == "":
            return None
        d = Decimal(str(value))
        if not isfinite(float(d)):
            return None
        return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return None


def _float(value: Any) -> float | None:
    d = _decimal(value)
    return float(d) if d is not None else None


def _sum(values: list[Any]) -> Decimal | None:
    found = False
    total = Decimal("0.00")
    for value in values:
        d = _decimal(value)
        if d is not None:
            total += d
            found = True
    return total.quantize(Decimal("0.01")) if found else None


def _parse_date(value: str | date | None, *, fallback: date) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not value:
        return fallback
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except Exception as exc:
        raise FinancialReconciliationError("Data inválida. Use YYYY-MM-DD.") from exc


def _validate_period(start_date: str | date | None, end_date: str | date | None) -> tuple[date, date]:
    today = _now().date()
    end = _parse_date(end_date, fallback=today)
    start = _parse_date(start_date, fallback=end - timedelta(days=30))
    if end < start:
        raise FinancialReconciliationError("end_date não pode ser menor que start_date.")
    if (end - start).days > MAX_RANGE_DAYS:
        raise FinancialReconciliationError(f"Período máximo permitido neste MVP: {MAX_RANGE_DAYS} dias.")
    return start, end


def _safe_get(data: dict[str, Any], *keys: str) -> Any:
    cur: Any = data
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _ml_get(url: str, token: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, headers=headers, params=params or {}, timeout=18)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as exc:
        status = getattr(exc.response, "status_code", None)
        msg = "Erro ao consultar API Mercado Livre."
        if status in {401, 403}:
            msg = "Token Mercado Livre sem permissão para consultar dados financeiros/pedidos."
        raise FinancialReconciliationError(msg) from exc
    except Exception as exc:
        raise FinancialReconciliationError("Falha temporária ao consultar Mercado Livre.") from exc


def _fetch_orders(db: Session, tenant_id: str, conn: MarketplaceConnection, start: date, end: date) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    token = get_valid_access_token(db, tenant_id)
    start_dt = datetime.combine(start, time.min).isoformat() + ".000-00:00"
    # ML filter is usually exclusive-ish by exact timestamp; include end day until 23:59.
    end_dt = datetime.combine(end, time.max).replace(microsecond=0).isoformat() + ".000-00:00"
    orders: list[dict[str, Any]] = []
    metadata = {"pages_requested": 0, "limit": ORDER_LIMIT, "truncated": False}
    for offset in range(0, ORDER_LIMIT * MAX_PAGES, ORDER_LIMIT):
        params = {
            "seller": conn.seller_id,
            "order.date_created.from": start_dt,
            "order.date_created.to": end_dt,
            "limit": ORDER_LIMIT,
            "offset": offset,
        }
        data = _ml_get(f"{ML_BASE_URL}/orders/search", token, params=params)
        page = data.get("results") or []
        metadata["pages_requested"] += 1
        orders.extend(page)
        paging = data.get("paging") or {}
        total = int(paging.get("total") or len(orders))
        if not page or len(orders) >= total:
            metadata["total_reported"] = total
            break
    else:
        metadata["truncated"] = True
    return orders, metadata


def _extract_order_amounts(order: dict[str, Any]) -> dict[str, Any]:
    gross = _decimal(order.get("total_amount") or order.get("paid_amount"))
    status = str(order.get("status") or "").lower()
    tags = [str(t).lower() for t in (order.get("tags") or [])]
    payments = order.get("payments") or []
    shipping = order.get("shipping") or {}

    payment_total = _sum([p.get("total_paid_amount") or p.get("transaction_amount") for p in payments])
    if gross is None:
        gross = payment_total

    fee_values: list[Any] = []
    shipping_values: list[Any] = []
    refund_values: list[Any] = []
    chargeback_values: list[Any] = []
    disputed = bool(order.get("claim_id") or "claim" in tags or "dispute" in tags)

    for payment in payments:
        fee_values.append(payment.get("marketplace_fee"))
        fee_values.append(payment.get("coupon_amount"))
        shipping_values.append(payment.get("shipping_cost"))
        # refunds may be list or aggregated values depending on API scope.
        refund_values.append(payment.get("refunded_amount"))
        refund_values.append(payment.get("amount_refunded"))
        if str(payment.get("status") or "").lower() in {"refunded", "cancelled"}:
            refund_values.append(payment.get("transaction_amount"))
        if str(payment.get("status_detail") or "").lower().find("chargeback") >= 0:
            chargeback_values.append(payment.get("transaction_amount"))

    shipping_values.append(_safe_get(shipping, "cost"))

    fees = _sum(fee_values)
    shipping_costs = _sum(shipping_values)
    refunds = _sum(refund_values)
    chargebacks = _sum(chargeback_values)
    refunded = status in {"cancelled", "refunded"} or (refunds is not None and refunds > 0)
    return {
        "gross": gross,
        "fees": fees,
        "shipping_costs": shipping_costs,
        "refunds": refunds,
        "chargebacks": chargebacks,
        "refunded": refunded,
        "disputed": disputed,
        "status": status,
        "payment_fields_found": len(payments),
    }


def _quality(missing: list[str], orders: list[dict[str, Any]], api_meta: dict[str, Any]) -> tuple[str, list[str]]:
    notes: list[str] = []
    if not orders:
        return "insufficient", ["Nenhum pedido retornado pela API no período."]
    if api_meta.get("truncated"):
        notes.append("Resultado truncado pelo limite do MVP; reduza o período para maior precisão.")
    missing_unique = sorted(set(missing))
    if not missing_unique:
        return "complete", notes
    if len(missing_unique) <= 2:
        return "partial", notes + ["Alguns campos financeiros não foram retornados pela API ML."]
    return "insufficient", notes + ["A API retornou pedidos, mas faltam campos financeiros importantes para reconciliação completa."]


def _alerts(summary: dict[str, Any], data_quality: dict[str, Any]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    if data_quality.get("status") != "complete":
        alerts.append({
            "type": "DATA_INCOMPLETE",
            "severity": "info",
            "title": "Dados financeiros incompletos",
            "description": "Algumas métricas não foram retornadas pela API Mercado Livre para este período.",
            "recommended_action": "Use a qualidade dos dados para entender as limitações antes de tomar decisão financeira.",
        })
    diff = _float(summary.get("reconciliation_difference"))
    if diff is not None and abs(diff) >= 10:
        alerts.append({
            "type": "RECONCILIATION_DIFFERENCE",
            "severity": "warning" if abs(diff) < 100 else "critical",
            "title": "Diferença de reconciliação encontrada",
            "description": f"Diferença entre receita líquida ML e valor recebido informado: R$ {diff:.2f}.",
            "recommended_action": "Conferir repasses, estornos, devoluções e datas de liquidação.",
        })
    gross = _float(summary.get("gross_revenue")) or 0
    fees = _float(summary.get("ml_fees"))
    if gross > 0 and fees is not None and fees / gross > 0.22:
        alerts.append({
            "type": "HIGH_FEES",
            "severity": "warning",
            "title": "Taxas elevadas no período",
            "description": "As tarifas estimadas representam mais de 22% da receita bruta.",
            "recommended_action": "Revisar categoria, tipo de anúncio, frete e política comercial.",
        })
    refunds = _float(summary.get("refunds_amount")) or 0
    if gross > 0 and refunds / gross > 0.10:
        alerts.append({
            "type": "REFUND_SPIKE",
            "severity": "warning",
            "title": "Devoluções acima do esperado",
            "description": "Devoluções/estornos representam mais de 10% da receita bruta.",
            "recommended_action": "Investigar produtos, logística, descrição do anúncio e reclamações.",
        })
    net = _float(summary.get("net_revenue"))
    if net is not None and net < 0:
        alerts.append({
            "type": "NEGATIVE_NET_REVENUE",
            "severity": "critical",
            "title": "Receita líquida negativa",
            "description": "Após taxas/devoluções/fretes identificados, o período ficou negativo.",
            "recommended_action": "Revisar custos, campanhas, devoluções e política de frete imediatamente.",
        })
    return alerts


def _dre(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"label": "Receita bruta", "amount": summary.get("gross_revenue"), "type": "positive"},
        {"label": "(-) Taxas Mercado Livre", "amount": summary.get("ml_fees"), "type": "negative"},
        {"label": "(-) Frete", "amount": summary.get("shipping_costs"), "type": "negative"},
        {"label": "(-) Devoluções/estornos", "amount": (_float(summary.get("refunds_amount")) or 0) + (_float(summary.get("chargebacks_amount")) or 0), "type": "negative"},
        {"label": "(=) Receita líquida estimada", "amount": summary.get("net_revenue"), "type": "result"},
    ]


def _latest_manual_bank(db: Session, tenant_id: str, start: date, end: date) -> Decimal | None:
    row = db.query(FinancialReconciliationSnapshot).filter(
        FinancialReconciliationSnapshot.tenant_id == tenant_id,
        FinancialReconciliationSnapshot.period_start == start,
        FinancialReconciliationSnapshot.period_end == end,
        FinancialReconciliationSnapshot.bank_received_amount.isnot(None),
    ).order_by(FinancialReconciliationSnapshot.created_at.desc()).first()
    return _decimal(row.bank_received_amount) if row else None


def _persist(db: Session, tenant_id: str, conn: MarketplaceConnection | None, start: date, end: date, summary: dict[str, Any], data_quality: dict[str, Any], raw: dict[str, Any]) -> FinancialReconciliationSnapshot:
    row = FinancialReconciliationSnapshot(
        tenant_id=tenant_id,
        marketplace_connection_id=str(conn.id) if conn else None,
        period_start=start,
        period_end=end,
        gross_revenue=summary.get("gross_revenue"),
        ml_fees=summary.get("ml_fees"),
        shipping_costs=summary.get("shipping_costs"),
        refunds_amount=summary.get("refunds_amount"),
        chargebacks_amount=summary.get("chargebacks_amount"),
        net_revenue=summary.get("net_revenue"),
        bank_received_amount=summary.get("bank_received_amount"),
        reconciliation_difference=summary.get("reconciliation_difference"),
        orders_count=summary.get("orders_count") or 0,
        refunded_orders_count=summary.get("refunded_orders_count") or 0,
        disputed_orders_count=summary.get("disputed_orders_count") or 0,
        data_quality_status=data_quality.get("status"),
        raw_payload_json=raw,
        generated_at=_now(),
    )
    db.add(row)
    return row


def _persist_signals(db: Session, tenant_id: str, alerts: list[dict[str, Any]], period_label: str) -> None:
    for alert in alerts:
        db.add(OperationalEvent(
            tenant_id=tenant_id,
            event_type=alert["type"],
            category="financial_reconciliation",
            severity=alert.get("severity", "info"),
            title=alert.get("title", "Alerta financeiro"),
            description=alert.get("description"),
        ))
        if alert["type"] in {"RECONCILIATION_DIFFERENCE", "HIGH_FEES", "REFUND_SPIKE", "NEGATIVE_NET_REVENUE"}:
            db.add(ActionRecommendation(
                tenant_id=tenant_id,
                category="finance",
                priority="HIGH" if alert.get("severity") == "critical" else "MEDIUM",
                origin="Financial Reconciliation Engine",
                title=f"{alert.get('title')} — {period_label}",
                explanation=alert.get("description"),
                recommended_action=alert.get("recommended_action"),
                next_best_action=alert.get("recommended_action"),
                confidence=0.70,
                status="pending",
            ))
        try:
            from services.alert_dispatcher import dispatch_alert
            if alert["type"] in {"RECONCILIATION_DIFFERENCE", "HIGH_FEES", "NEGATIVE_NET_REVENUE"}:
                dispatch_alert(
                    db,
                    tenant_id=tenant_id,
                    alert_type=alert["type"],
                    severity=alert.get("severity", "warning"),
                    title=alert.get("title", "Alerta financeiro"),
                    message=f"SellerOS — Reconciliação Financeira\nPeríodo: {period_label}\n{alert.get('description')}\nAção sugerida: {alert.get('recommended_action')}",
                    dedupe_key=f"finance:{tenant_id}:{period_label}:{alert['type']}",
                )
        except Exception as exc:  # pragma: no cover
            log.warning("financial_alert_dispatch_failed", extra={"tenant_id": str(tenant_id), "error_type": type(exc).__name__})


def build_reconciliation(db: Session, tenant_id: str, start_date: str | date | None, end_date: str | date | None, *, persist: bool = True) -> dict[str, Any]:
    start, end = _validate_period(start_date, end_date)
    conn = get_connection(db, tenant_id)
    if not conn:
        raise FinancialReconciliationError("Seller Mercado Livre não conectado.")

    try:
        orders, api_meta = _fetch_orders(db, tenant_id, conn, start, end)
    except MLTokenServiceError as exc:
        raise FinancialReconciliationError(str(exc)) from exc

    order_metrics = [_extract_order_amounts(o) for o in orders]
    missing: list[str] = []
    gross = _sum([m["gross"] for m in order_metrics])
    fees = _sum([m["fees"] for m in order_metrics])
    shipping = _sum([m["shipping_costs"] for m in order_metrics])
    refunds = _sum([m["refunds"] for m in order_metrics])
    chargebacks = _sum([m["chargebacks"] for m in order_metrics])
    for field, value in [("gross_revenue", gross), ("ml_fees", fees), ("shipping_costs", shipping), ("refunds_amount", refunds), ("chargebacks_amount", chargebacks)]:
        if value is None:
            missing.append(field)

    net = None
    if gross is not None:
        net = gross
        for deduction in [fees, shipping, refunds, chargebacks]:
            if deduction is not None:
                net -= deduction
        net = net.quantize(Decimal("0.01"))

    bank = _latest_manual_bank(db, tenant_id, start, end)
    difference = None
    if bank is not None and net is not None:
        difference = (bank - net).quantize(Decimal("0.01"))

    status, notes = _quality(missing, orders, api_meta)
    summary = {
        "gross_revenue": _float(gross),
        "ml_fees": _float(fees),
        "shipping_costs": _float(shipping),
        "refunds_amount": _float(refunds),
        "chargebacks_amount": _float(chargebacks),
        "net_revenue": _float(net),
        "estimated_margin": None,  # custo por pedido ainda não está disponível neste MVP.
        "bank_received_amount": _float(bank),
        "reconciliation_difference": _float(difference),
        "orders_count": len(orders),
        "refunded_orders_count": len([m for m in order_metrics if m["refunded"]]),
        "disputed_orders_count": len([m for m in order_metrics if m["disputed"]]),
    }
    data_quality = {"status": status, "missing_fields": sorted(set(missing)), "notes": notes}
    alerts = _alerts(summary, data_quality)
    raw = {
        "api_meta": api_meta,
        "orders_sample": [
            {"id": o.get("id"), "status": o.get("status"), "date_created": o.get("date_created"), "total_amount": o.get("total_amount"), "payments_count": len(o.get("payments") or [])}
            for o in orders[:25]
        ],
        "calculation_note": "Snapshot não armazena cartão/dados bancários sensíveis. bank_received_amount é manual.",
    }
    if persist:
        _persist(db, tenant_id, conn, start, end, summary, data_quality, raw)
        db.add(OperationalEvent(
            tenant_id=tenant_id,
            event_type="financial_reconciliation_generated",
            category="financial_reconciliation",
            severity="info" if status != "insufficient" else "warning",
            title="Reconciliação financeira gerada",
            description=f"Período {start.isoformat()} a {end.isoformat()} analisado com status {status}.",
        ))
        _persist_signals(db, tenant_id, alerts, f"{start.isoformat()}:{end.isoformat()}")
        db.commit()

    return {
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "summary": summary,
        "dre": _dre(summary),
        "alerts": alerts,
        "data_quality": data_quality,
        "generated_at": _iso(_now()),
        "disclaimer": "Reconciliação MVP baseada nos dados retornados pela API Mercado Livre. Não inclui integração bancária automática.",
    }


def save_manual_bank_received(db: Session, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    start, end = _validate_period(payload.get("start_date"), payload.get("end_date"))
    amount = _decimal(payload.get("bank_received_amount"))
    if amount is None or amount < 0:
        raise FinancialReconciliationError("bank_received_amount deve ser um número positivo.")
    conn = get_connection(db, tenant_id)
    if not conn:
        raise FinancialReconciliationError("Seller Mercado Livre não conectado.")

    latest = db.query(FinancialReconciliationSnapshot).filter(
        FinancialReconciliationSnapshot.tenant_id == tenant_id,
        FinancialReconciliationSnapshot.period_start == start,
        FinancialReconciliationSnapshot.period_end == end,
    ).order_by(FinancialReconciliationSnapshot.created_at.desc()).first()

    net = _decimal(latest.net_revenue) if latest else None
    diff = (amount - net).quantize(Decimal("0.01")) if net is not None else None
    row = FinancialReconciliationSnapshot(
        tenant_id=tenant_id,
        marketplace_connection_id=str(conn.id),
        period_start=start,
        period_end=end,
        gross_revenue=latest.gross_revenue if latest else None,
        ml_fees=latest.ml_fees if latest else None,
        shipping_costs=latest.shipping_costs if latest else None,
        refunds_amount=latest.refunds_amount if latest else None,
        chargebacks_amount=latest.chargebacks_amount if latest else None,
        net_revenue=latest.net_revenue if latest else None,
        bank_received_amount=amount,
        reconciliation_difference=diff,
        orders_count=latest.orders_count if latest else 0,
        refunded_orders_count=latest.refunded_orders_count if latest else 0,
        disputed_orders_count=latest.disputed_orders_count if latest else 0,
        data_quality_status=latest.data_quality_status if latest else "manual_only",
        raw_payload_json={"manual_bank_received": True, "previous_snapshot_id": str(latest.id) if latest else None},
        generated_at=_now(),
    )
    db.add(row)
    db.add(OperationalEvent(
        tenant_id=tenant_id,
        event_type="bank_received_amount_saved",
        category="financial_reconciliation",
        severity="info",
        title="Valor recebido no banco informado",
        description=f"Valor manual de R$ {amount} salvo para {start.isoformat()} a {end.isoformat()}.",
    ))
    db.commit()
    return {
        "ok": True,
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "bank_received_amount": _float(amount),
        "reconciliation_difference": _float(diff),
        "message": "Valor recebido salvo. Recarregue a reconciliação para comparar com a receita líquida ML.",
    }
