"""Billing Pagar.me + SaaS monetization layer.

Integração real com Pagar.me v5 quando PAGARME_API_KEY está configurada.
Sem chave, as rotas retornam provider_unavailable de forma amigável sem fingir
cobrança em produção.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta
import hashlib
import hmac
import logging
from typing import Any

import requests
from sqlalchemy.orm import Session

from config.settings import BILLING_TRIAL_DAYS, PAGARME_API_KEY, PAGARME_BASE_URL, PAGARME_WEBHOOK_SECRET
from models.orm import BillingEvent, BillingSubscription, Cliente, OperationalEvent
from services.plan_limits_service import PLAN_CONFIG, check_limits, list_plans, normalize_plan, serialize_plan
from services.email_service import send_billing_confirmation_email

log = logging.getLogger("msp.billing")
TIMEOUT = 20


def _now() -> datetime:
    return datetime.utcnow()


def _provider_available() -> bool:
    return bool(PAGARME_API_KEY)


def provider_status() -> dict[str, Any]:
    return {"provider": "pagarme", "configured": _provider_available(), "base_url": PAGARME_BASE_URL}


def _auth_header() -> dict[str, str]:
    raw = f"{PAGARME_API_KEY}:".encode("utf-8")
    token = base64.b64encode(raw).decode("ascii")
    return {"Authorization": f"Basic {token}", "Accept": "application/json", "Content-Type": "application/json"}


def _sanitize_error(exc: Exception) -> str:
    text = str(exc).replace(PAGARME_API_KEY, "[redacted]") if PAGARME_API_KEY else str(exc)
    return text[:400]


def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not _provider_available():
        raise RuntimeError("Pagar.me indisponível: configure PAGARME_API_KEY.")
    url = f"{PAGARME_BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    try:
        res = requests.request(method, url, json=payload, headers=_auth_header(), timeout=TIMEOUT)
        if res.status_code >= 400:
            raise RuntimeError(f"Pagar.me retornou erro HTTP {res.status_code}: {res.text[:300]}")
        return res.json() if res.content else {}
    except requests.RequestException as exc:
        raise RuntimeError(_sanitize_error(exc)) from exc


def _event(db: Session, tenant_id: str, event_type: str, title: str, description: str, severity: str = "info") -> None:
    try:
        db.add(OperationalEvent(tenant_id=tenant_id, event_type=event_type, category="billing", severity=severity, title=title, description=description))
    except Exception:
        pass


def _current_subscription(db: Session, tenant_id: str) -> BillingSubscription | None:
    return db.query(BillingSubscription).filter_by(tenant_id=tenant_id).order_by(BillingSubscription.created_at.desc()).first()


def get_plans() -> dict[str, Any]:
    return {"plans": list_plans(), "provider": provider_status()}


def get_billing_status(db: Session, tenant_id: str) -> dict[str, Any]:
    sub = _current_subscription(db, tenant_id)
    plan_code = normalize_plan(getattr(sub, "plan_code", None) if sub else "STARTER")
    status = getattr(sub, "status", None) or "trial"
    limits = check_limits(db, tenant_id, plan_code)
    return {
        "provider": provider_status(),
        "plan": serialize_plan(plan_code),
        "subscription": {
            "status": status,
            "pagarme_subscription_id": getattr(sub, "pagarme_subscription_id", None),
            "current_period_start": _iso(getattr(sub, "current_period_start", None)),
            "current_period_end": _iso(getattr(sub, "current_period_end", None)),
            "cancel_at_period_end": bool(getattr(sub, "cancel_at_period_end", False)),
            "last_payment_status": getattr(sub, "last_payment_status", None),
            "last_payment_at": _iso(getattr(sub, "last_payment_at", None)),
            "trial_ends_at": _iso(getattr(sub, "trial_ends_at", None)),
        },
        "usage": limits.usage,
        "limits": limits.limits,
        "limit_warning": limits.warning,
        "limit_reason": limits.reason,
    }


def _iso(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        return value
    return value.replace(microsecond=0).isoformat() + "Z"


def _clean_customer(customer: dict[str, Any]) -> dict[str, Any]:
    name = str(customer.get("name") or "").strip()[:120]
    email = str(customer.get("email") or "").strip().lower()[:160]
    document = "".join(ch for ch in str(customer.get("document") or "") if ch.isdigit())[:20]
    phone = "".join(ch for ch in str(customer.get("phone") or "") if ch.isdigit())[:20]
    if not name or not email:
        raise ValueError("Nome e e-mail são obrigatórios para assinatura.")
    payload: dict[str, Any] = {"name": name, "email": email, "type": "individual"}
    if document:
        payload["document"] = document
    if phone:
        payload["phones"] = {"mobile_phone": {"country_code": "55", "area_code": phone[:2] if len(phone) >= 10 else "11", "number": phone[2:] if len(phone) >= 10 else phone}}
    return payload


def _build_subscription_payload(plan_code: str, customer_id: str | None, customer_payload: dict[str, Any], tenant_id: str) -> dict[str, Any]:
    plan = serialize_plan(plan_code)
    item = {
        "description": f"SellerOS {plan['name']} mensal",
        "quantity": 1,
        "pricing_scheme": {"scheme_type": "unit", "price": int(plan["monthly_price_cents"])}
    }
    payload: dict[str, Any] = {
        "code": f"selleros-{tenant_id}-{plan_code.lower()}",
        "interval": "month",
        "interval_count": 1,
        "billing_type": "prepaid",
        "items": [item],
        "metadata": {"tenant_id": str(tenant_id), "plan_code": plan_code, "source": "selleros"},
    }
    if customer_id:
        payload["customer_id"] = customer_id
    else:
        payload["customer"] = customer_payload
    # Sem dados de cartão no SellerOS. O pagamento deve ser concluído via checkout/card_id/token configurado fora desta rota.
    return payload


def subscribe(db: Session, tenant_id: str, plan: str, customer: dict[str, Any]) -> dict[str, Any]:
    plan_code = normalize_plan(plan)
    customer_payload = _clean_customer(customer or {})
    if not _provider_available():
        return {"ok": False, "status": "provider_unavailable", "message": "Pagar.me não configurado. Defina PAGARME_API_KEY para criar assinaturas reais.", "provider": provider_status()}

    try:
        pagarme_customer = _request("POST", "/customers", customer_payload)
        subscription_payload = _build_subscription_payload(plan_code, pagarme_customer.get("id"), customer_payload, tenant_id)
        pagarme_subscription = _request("POST", "/subscriptions", subscription_payload)
    except Exception as exc:
        log.warning("billing_subscribe_failed", extra={"event": "billing_subscribe_failed", "tenant_id": str(tenant_id), "error_type": type(exc).__name__})
        raise RuntimeError(_sanitize_error(exc)) from exc

    sub = _current_subscription(db, tenant_id) or BillingSubscription(tenant_id=tenant_id)
    sub.pagarme_customer_id = pagarme_customer.get("id")
    sub.pagarme_subscription_id = pagarme_subscription.get("id")
    sub.plan_code = plan_code
    sub.status = str(pagarme_subscription.get("status") or "pending")
    sub.current_period_start = _parse_dt(pagarme_subscription.get("current_cycle", {}).get("start_at") or pagarme_subscription.get("start_at"))
    sub.current_period_end = _parse_dt(pagarme_subscription.get("current_cycle", {}).get("end_at") or pagarme_subscription.get("next_billing_at"))
    sub.trial_ends_at = _now() + timedelta(days=max(0, BILLING_TRIAL_DAYS))
    sub.metadata_json = {"customer_email": customer_payload.get("email"), "pagarme_subscription": pagarme_subscription}
    sub.updated_at = _now()
    db.add(sub)
    _event(db, tenant_id, "subscription_created", "Assinatura criada", f"Plano {plan_code} criado no Pagar.me.")
    db.commit()
    plan_snapshot = serialize_plan(plan_code)
    send_billing_confirmation_email(
        to_email=customer_payload.get("email", ""),
        user_name=customer_payload.get("name", ""),
        plan_name=plan_snapshot.get("name", plan_code),
        value_brl=f"R$ {float(plan_snapshot.get('monthly_price') or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
    )
    return {"ok": True, "subscription": get_billing_status(db, tenant_id), "pagarme": {"customer_id": sub.pagarme_customer_id, "subscription_id": sub.pagarme_subscription_id}}


def cancel_subscription(db: Session, tenant_id: str) -> dict[str, Any]:
    sub = _current_subscription(db, tenant_id)
    if not sub:
        raise LookupError("Nenhuma assinatura encontrada para este tenant.")
    if _provider_available() and sub.pagarme_subscription_id:
        try:
            _request("DELETE", f"/subscriptions/{sub.pagarme_subscription_id}")
        except Exception as exc:
            raise RuntimeError(_sanitize_error(exc)) from exc
    sub.cancel_at_period_end = True
    sub.status = "cancel_requested"
    sub.updated_at = _now()
    _event(db, tenant_id, "subscription_cancelled", "Cancelamento solicitado", "A renovação da assinatura foi marcada para cancelamento.", "warning")
    db.commit()
    return get_billing_status(db, tenant_id)


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _extract_provider_event_id(payload: dict[str, Any]) -> str:
    return str(payload.get("id") or payload.get("event_id") or payload.get("code") or hashlib.sha256(str(payload).encode("utf-8")).hexdigest())


def verify_webhook_signature(raw_body: bytes, signature: str | None) -> bool:
    if not PAGARME_WEBHOOK_SECRET:
        return False
    if not signature:
        return False
    expected = hmac.new(PAGARME_WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    candidates = {signature, signature.replace("sha256=", "")}
    return any(hmac.compare_digest(expected, c) for c in candidates)


def process_webhook(db: Session, payload: dict[str, Any], raw_body: bytes = b"", signature: str | None = None) -> dict[str, Any]:
    if not verify_webhook_signature(raw_body, signature):
        raise PermissionError("Assinatura do webhook inválida.")
    event_id = _extract_provider_event_id(payload)
    event_type = str(payload.get("type") or payload.get("event") or payload.get("event_type") or "unknown")
    data = payload.get("data") or payload.get("subscription") or payload.get("charge") or {}
    subscription_obj = data.get("subscription") if isinstance(data, dict) and isinstance(data.get("subscription"), dict) else data
    metadata = subscription_obj.get("metadata", {}) if isinstance(subscription_obj, dict) else {}
    tenant_id = metadata.get("tenant_id") or payload.get("tenant_id")
    subscription_id = subscription_obj.get("id") if isinstance(subscription_obj, dict) else None

    existing = db.query(BillingEvent).filter_by(provider="pagarme", provider_event_id=event_id).first()
    if existing and existing.processed:
        return {"ok": True, "idempotent": True, "event_type": existing.event_type}

    row = existing or BillingEvent(tenant_id=tenant_id, event_type=event_type, provider="pagarme", provider_event_id=event_id, payload_json=payload, processed=False)
    db.add(row)
    db.flush()

    sub = None
    if tenant_id:
        sub = _current_subscription(db, tenant_id)
    if not sub and subscription_id:
        sub = db.query(BillingSubscription).filter_by(pagarme_subscription_id=subscription_id).first()
        tenant_id = getattr(sub, "tenant_id", tenant_id)

    mapped_status, payment_status = _map_event_status(event_type, subscription_obj if isinstance(subscription_obj, dict) else {})
    if sub:
        if mapped_status:
            sub.status = mapped_status
        if payment_status:
            sub.last_payment_status = payment_status
            if payment_status == "paid":
                sub.last_payment_at = _now()
        sub.updated_at = _now()
        if isinstance(subscription_obj, dict):
            sub.current_period_start = _parse_dt(subscription_obj.get("current_cycle", {}).get("start_at")) or sub.current_period_start
            sub.current_period_end = _parse_dt(subscription_obj.get("current_cycle", {}).get("end_at")) or sub.current_period_end
            sub.metadata_json = {**(sub.metadata_json or {}), "last_webhook": payload}

    if tenant_id:
        if payment_status == "paid":
            _event(db, tenant_id, "payment_approved", "Pagamento aprovado", "Webhook Pagar.me confirmou pagamento.")
        elif payment_status == "failed":
            _event(db, tenant_id, "payment_failed", "Pagamento recusado", "Webhook Pagar.me indicou falha ou inadimplência.", "warning")
        elif mapped_status in {"canceled", "cancelled"}:
            _event(db, tenant_id, "subscription_cancelled", "Assinatura cancelada", "Webhook Pagar.me indicou cancelamento.", "warning")
    row.tenant_id = tenant_id
    row.processed = True
    row.processed_at = _now()
    db.commit()
    return {"ok": True, "event_type": event_type, "tenant_id": str(tenant_id) if tenant_id else None, "processed": True}


def _map_event_status(event_type: str, data: dict[str, Any]) -> tuple[str | None, str | None]:
    event = event_type.lower()
    status = str(data.get("status") or "").lower() or None
    if "paid" in event or "payment_succeeded" in event or "charge.paid" in event:
        return status or "active", "paid"
    if "failed" in event or "refused" in event or "past_due" in event or "payment_failed" in event:
        return status or "past_due", "failed"
    if "cancel" in event:
        return status or "canceled", None
    if "subscription" in event and status:
        return status, None
    return None, None
