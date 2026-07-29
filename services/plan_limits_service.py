"""Limites comerciais do SellerOS por plano.

PATCH 10/10 — camada SaaS monetizável. Os limites são soft-first: retornam
warnings e flags para bloqueios graduais, sem derrubar login/dashboard.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from models.orm import Product, User

PLAN_CONFIG: dict[str, dict[str, Any]] = {
    "STARTER": {
        "name": "Starter",
        "monthly_price_cents": 9900,
        "product_limit": 100,
        "user_limit": 1,
        "features": ["OAuth Mercado Livre", "Sync de catálogo", "Dashboard operacional", "Alertas básicos"],
    },
    "GROWTH": {
        "name": "Growth",
        "monthly_price_cents": 19900,
        "product_limit": 500,
        "user_limit": 3,
        "features": ["Tudo do Starter", "Questions AI", "Account Health", "Buy Box Score", "Alertas avançados"],
    },
    "PROFESSIONAL": {
        "name": "Professional",
        "monthly_price_cents": 39900,
        "product_limit": 10000,
        "user_limit": 10,
        "features": ["Catálogo ilimitado", "Inteligência completa", "Prioridade operacional", "Camadas premium futuras"],
    },
}

BLOCKED_BILLING_STATUSES = {"past_due", "unpaid", "canceled", "cancelled", "expired", "failed"}
ACTIVE_BILLING_STATUSES = {"active", "paid", "trial", "trialing", "pending"}


@dataclass
class LimitCheck:
    allowed: bool
    warning: bool
    reason: str | None
    usage: dict[str, Any]
    limits: dict[str, Any]


def normalize_plan(plan_code: str | None) -> str:
    code = str(plan_code or "STARTER").upper()
    return code if code in PLAN_CONFIG else "STARTER"


def serialize_plan(code: str) -> dict[str, Any]:
    normalized = normalize_plan(code)
    cfg = PLAN_CONFIG[normalized]
    return {
        "code": normalized,
        "name": cfg["name"],
        "monthly_price_cents": cfg["monthly_price_cents"],
        "monthly_price": round(cfg["monthly_price_cents"] / 100, 2),
        "limits": {"products": cfg["product_limit"], "users": cfg["user_limit"]},
        "features": cfg["features"],
    }


def list_plans() -> list[dict[str, Any]]:
    return [serialize_plan(code) for code in ("STARTER", "GROWTH", "PROFESSIONAL")]


def get_usage(db: Session, tenant_id: str) -> dict[str, int]:
    products = db.query(Product.id).filter(Product.cliente_id == tenant_id).count()
    users = db.query(User.id).filter(User.cliente_id == tenant_id, User.ativo == True).count()  # noqa: E712
    return {"products": int(products or 0), "users": int(users or 0)}


def check_limits(db: Session, tenant_id: str, plan_code: str | None, *, action: str = "generic") -> LimitCheck:
    plan = normalize_plan(plan_code)
    cfg = PLAN_CONFIG[plan]
    usage = get_usage(db, tenant_id)
    product_limit = cfg["product_limit"]
    user_limit = cfg["user_limit"]
    warnings: list[str] = []
    hard_block = False

    if product_limit is not None and usage["products"] >= product_limit:
        warnings.append(f"Catálogo no limite do plano {plan}: {usage['products']}/{product_limit} produtos.")
        if action in {"catalog_sync", "premium_action"}:
            hard_block = True
    if user_limit is not None and usage["users"] >= user_limit:
        warnings.append(f"Usuários no limite do plano {plan}: {usage['users']}/{user_limit} usuários.")
        if action in {"invite_user", "premium_action"}:
            hard_block = True

    return LimitCheck(
        allowed=not hard_block,
        warning=bool(warnings),
        reason=" ".join(warnings) if warnings else None,
        usage=usage,
        limits={"products": product_limit, "users": user_limit},
    )


def billing_allows_premium(status: str | None) -> bool:
    normalized = str(status or "trial").lower()
    if normalized in BLOCKED_BILLING_STATUSES:
        return False
    return True
