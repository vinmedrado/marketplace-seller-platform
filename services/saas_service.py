"""Serviços SaaS comerciais: onboarding, planos, usuários, alertas e integração marketplace."""
from datetime import datetime, timedelta
import secrets
from typing import Any
from sqlalchemy.orm import Session
from config.settings import DEBUG, FRONTEND_URL
from models.orm import (
    Cliente, Organization, User, Product, BackgroundJob, MarketplaceAccount, MarketplaceConnection,
    PlanSubscription, OnboardingState, InternalAlert, UserInvite
)
from services.auth_service import hash_password
from services.email_service import send_invite_email

PLANS = {
    "starter": {"name": "Starter", "price_label": "R$ 99/mês", "limits": {"products": 100, "users": 1, "jobs_per_month": 500, "monitored_products": 50}, "features": ["OAuth Mercado Livre", "Sync de catálogo", "Dashboard operacional", "Alertas básicos"]},
    "growth": {"name": "Growth", "price_label": "R$ 199/mês", "limits": {"products": 500, "users": 3, "jobs_per_month": 5000, "monitored_products": 500}, "features": ["Questions AI", "Account Health", "Buy Box Score", "Alertas avançados"]},
    "professional": {"name": "Professional", "price_label": "R$ 399/mês", "limits": {"products": 10000, "users": 10, "jobs_per_month": 50000, "monitored_products": 5000}, "features": ["Catálogo em escala", "Inteligência completa", "Prioridade operacional"]},
}
ROLES = {"owner", "admin", "operator", "viewer"}
ROLE_RANK = {"viewer": 1, "operator": 2, "admin": 3, "owner": 4}

def _is_expired(value: datetime | None) -> bool:
    if value is None:
        return False
    now = datetime.now(value.tzinfo) if value.tzinfo else datetime.utcnow()
    return value < now

def require_role(user: User, allowed: set[str]):
    if user.role not in allowed:
        raise PermissionError("Permissão insuficiente para esta ação.")

def _subscription(db: Session, tenant_id: str) -> PlanSubscription:
    sub = db.query(PlanSubscription).filter_by(cliente_id=tenant_id).first()
    if not sub:
        plan = PLANS["growth"]
        sub = PlanSubscription(cliente_id=tenant_id, plan_key="growth", limits_json=plan["limits"], features_json={"enabled": plan["features"]})
        db.add(sub); db.commit(); db.refresh(sub)
    return sub

def list_plans(db: Session, user: User) -> dict[str, Any]:
    sub = _subscription(db, user.cliente_id)
    product_count = db.query(Product).filter_by(cliente_id=user.cliente_id).count()
    job_count = db.query(BackgroundJob).filter_by(tenant_id=user.cliente_id).count()
    return {"current_plan": sub.plan_key, "status": sub.status, "usage": {"products": product_count, "jobs": job_count}, "plans": PLANS}

def update_plan(db: Session, user: User, plan_key: str) -> dict[str, Any]:
    require_role(user, {"owner", "admin"})
    if plan_key not in PLANS: raise ValueError("Plano inválido")
    sub = _subscription(db, user.cliente_id)
    sub.plan_key = plan_key; sub.limits_json = PLANS[plan_key]["limits"]; sub.features_json = {"enabled": PLANS[plan_key]["features"]}
    db.commit()
    return list_plans(db, user)

def get_onboarding(db: Session, user: User) -> dict[str, Any]:
    row = db.query(OnboardingState).filter_by(cliente_id=user.cliente_id).first()
    if not row:
        row = OnboardingState(cliente_id=user.cliente_id, completed=False, current_step=1, data_json={})
        db.add(row); db.commit(); db.refresh(row)
    return {"completed": row.completed, "current_step": row.current_step, "data": row.data_json or {}}

def save_onboarding(db: Session, user: User, payload: dict[str, Any]) -> dict[str, Any]:
    row = db.query(OnboardingState).filter_by(cliente_id=user.cliente_id).first() or OnboardingState(cliente_id=user.cliente_id)
    db.add(row)
    row.current_step = int(payload.get("current_step") or payload.get("step") or row.current_step or 1)
    row.completed = bool(payload.get("completed", row.completed))
    row.data_json = {**(row.data_json or {}), **payload.get("data", payload)}
    cliente = db.query(Cliente).filter_by(id=user.cliente_id).first()
    org = db.query(Organization).filter_by(id=user.organization_id).first()
    data = row.data_json or {}
    if cliente:
        cfg = cliente.config or {}; cfg.update({"onboarding": data, "onboarding_completed": row.completed})
        cliente.config = cfg
    if org and data.get("company_name"):
        org.nome = data["company_name"]
    db.commit(); db.refresh(row)
    return get_onboarding(db, user)

def list_users(db: Session, user: User) -> dict[str, Any]:
    users = db.query(User).filter_by(cliente_id=user.cliente_id).order_by(User.criado_em.asc()).all()
    invites = db.query(UserInvite).filter_by(cliente_id=user.cliente_id).order_by(UserInvite.criado_em.desc()).all()
    return {"items": [{"id": u.id, "nome": u.nome, "email": u.email, "role": u.role, "ativo": u.ativo, "ultimo_login_em": u.ultimo_login_em, "criado_em": u.criado_em} for u in users], "invites": [{"id": i.id, "email": i.email, "role": i.role, "status": i.status, "criado_em": i.criado_em} for i in invites]}

def invite_user(db: Session, user: User, payload: dict[str, Any]) -> dict[str, Any]:
    require_role(user, {"owner", "admin"})
    from services.plan_limits_service import check_limits
    cliente = db.query(Cliente).filter_by(id=user.cliente_id).first()
    limit = check_limits(db, user.cliente_id, getattr(cliente, "plano", None), action="invite_user")
    if not limit.allowed:
        raise PermissionError(limit.reason or "Limite de usuários atingido.")
    role = payload.get("role", "viewer")
    if role not in ROLES or role == "owner": raise ValueError("Role inválida para convite")
    email = (payload.get("email") or "").lower().strip()
    if not email: raise ValueError("E-mail obrigatório")
    if db.query(User).filter_by(email=email).first():
        raise ValueError("Já existe um usuário com este e-mail.")
    inv = (
        db.query(UserInvite)
        .filter_by(cliente_id=user.cliente_id, email=email, status="pending")
        .first()
    )
    if not inv:
        inv = UserInvite(cliente_id=user.cliente_id, email=email, role=role, status="pending")
        db.add(inv)
    inv.role = role
    inv.token = secrets.token_urlsafe(32)
    inv.expires_at = datetime.utcnow() + timedelta(days=7)
    db.commit(); db.refresh(inv)
    org = db.query(Organization).filter_by(id=user.organization_id, cliente_id=user.cliente_id).first()
    org_name = getattr(org, "nome", None) or "SellerOS"
    invite_url = f"{FRONTEND_URL.rstrip('/')}/aceitar-convite/{inv.token}"
    email_sent = send_invite_email(to_email=email, invite_url=invite_url, org_name=org_name)
    result = {"id": inv.id, "email": inv.email, "role": inv.role, "status": inv.status, "email_sent": email_sent}
    if DEBUG and not email_sent:
        result["invite_url"] = invite_url
    return result


def get_invite(db: Session, token: str) -> dict[str, Any]:
    inv = db.query(UserInvite).filter_by(token=token, status="pending").first()
    if not inv or _is_expired(inv.expires_at):
        raise LookupError("Convite inválido ou expirado.")
    org = db.query(Organization).filter_by(cliente_id=inv.cliente_id).first()
    return {
        "email": inv.email,
        "role": inv.role,
        "organization": getattr(org, "nome", None) or "SellerOS",
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
    }


def accept_invite(db: Session, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    inv = db.query(UserInvite).filter_by(token=token, status="pending").first()
    if not inv or _is_expired(inv.expires_at):
        raise LookupError("Convite inválido ou expirado.")
    name = str(payload.get("name") or payload.get("nome") or "").strip()
    password = str(payload.get("password") or payload.get("senha") or "")
    if len(name) < 2:
        raise ValueError("Informe seu nome.")
    if len(password) < 10:
        raise ValueError("A senha deve possuir pelo menos 10 caracteres.")
    if db.query(User).filter_by(email=inv.email).first():
        raise ValueError("Já existe um usuário com este e-mail.")
    org = db.query(Organization).filter_by(cliente_id=inv.cliente_id).first()
    if not org:
        raise LookupError("Organização do convite não encontrada.")
    user = User(
        nome=name,
        email=inv.email,
        cliente_id=inv.cliente_id,
        organization_id=org.id,
        hashed_password=hash_password(password),
        role=inv.role,
        ativo=True,
    )
    db.add(user)
    inv.status = "accepted"
    inv.accepted_at = datetime.utcnow()
    db.commit()
    return {"status": "accepted", "email": user.email, "message": "Convite aceito. Você já pode entrar."}

def update_user_role(db: Session, user: User, target_id: str, role: str) -> dict[str, Any]:
    require_role(user, {"owner", "admin"})
    if role not in ROLES: raise ValueError("Role inválida")
    target = db.query(User).filter_by(id=target_id, cliente_id=user.cliente_id).first()
    if not target: raise LookupError("Usuário não encontrado")
    if target.role == "owner" and user.id != target.id: raise PermissionError("Owner não pode ser alterado por outro usuário")
    if target.id == user.id and target.role == "owner" and role != "owner":
        raise PermissionError("O owner não pode remover a própria função.")
    target.role = role; db.commit()
    return {"id": target.id, "role": target.role}

def remove_user(db: Session, user: User, target_id: str) -> dict[str, Any]:
    require_role(user, {"owner", "admin"})
    if target_id == user.id: raise ValueError("Você não pode remover seu próprio usuário")
    target = db.query(User).filter_by(id=target_id, cliente_id=user.cliente_id).first()
    if not target: raise LookupError("Usuário não encontrado")
    if target.role == "owner": raise PermissionError("Owner não pode ser removido")
    target.ativo = False; db.commit()
    return {"status": "removed"}

def seed_alerts(db: Session, tenant_id: str) -> None:
    if db.query(InternalAlert).filter_by(cliente_id=tenant_id).count() > 0: return
    rows = [
        ("low_margin", "high", "Margem baixa em produtos estratégicos", "7 SKUs estão abaixo da margem mínima definida.", "/app/precificacao"),
        ("aggressive_competition", "high", "Concorrência agressiva detectada", "3 concorrentes reduziram preço nas últimas 24h.", "/app/concorrencia"),
        ("job_failed", "medium", "Job de scraping falhou", "Uma coleta terminou com falha e precisa de reprocessamento.", "/app/jobs"),
        ("pending_publication", "medium", "Publicação pendente", "Há anúncios em dry-run aguardando revisão.", "/app/publicacao"),
        ("pricing_opportunity", "low", "Oportunidade de repricing", "Produtos com margem segura podem ganhar competitividade.", "/app/precificacao"),
    ]
    for t,p,title,desc,url in rows:
        impact = {"low_margin": 4200, "aggressive_competition": 1280, "job_failed": 0, "pending_publication": 640, "pricing_opportunity": 2100}.get(t, 0)
        action = {"low_margin": "Recalcular preço protegido", "aggressive_competition": "Abrir concorrência e comparar mediana", "job_failed": "Reprocessar job", "pending_publication": "Validar dry-run", "pricing_opportunity": "Simular aumento de preço"}.get(t, "Revisar")
        db.add(InternalAlert(cliente_id=tenant_id, type=t, priority=p, title=title, description=desc, target_url=url, metadata_json={"demo": True, "impact_estimated": impact, "recommended_action": action, "category": t}))
    db.commit()

def list_alerts(db: Session, user: User) -> dict[str, Any]:
    seed_alerts(db, user.cliente_id)
    rows = db.query(InternalAlert).filter_by(cliente_id=user.cliente_id).order_by(InternalAlert.criado_em.desc()).limit(50).all()
    return {"unread": sum(1 for r in rows if not r.is_read), "items": [{"id": r.id, "type": r.type, "priority": r.priority, "title": r.title, "description": r.description, "target_url": r.target_url, "is_read": r.is_read, "created_at": r.criado_em, "impact_estimated": (r.metadata_json or {}).get("impact_estimated", 0), "recommended_action": (r.metadata_json or {}).get("recommended_action", "Revisar"), "category": (r.metadata_json or {}).get("category", r.type)} for r in rows]}

def mark_alert_read(db: Session, user: User, alert_id: str) -> dict[str, Any]:
    row = db.query(InternalAlert).filter_by(id=alert_id, cliente_id=user.cliente_id).first()
    if not row: raise LookupError("Alerta não encontrado")
    row.is_read = True; row.lido_em = datetime.utcnow(); db.commit()
    return {"status": "ok"}

def marketplace_status(db: Session, user: User) -> dict[str, Any]:
    conn = db.query(MarketplaceConnection).filter_by(tenant_id=user.cliente_id, marketplace="mercadolivre").first()
    connected = bool(conn and conn.is_active)
    token_valid = bool(conn and conn.access_token_encrypted and (not conn.token_expires_at or conn.token_expires_at > datetime.utcnow()))
    return {"marketplaces": [{
        "key": "mercadolivre",
        "name": "Mercado Livre",
        "connected": connected,
        "status": "connected" if connected else "not_connected",
        "token_valid": token_valid,
        "last_sync": conn.updated_at.isoformat() if conn and conn.updated_at else None,
        "seller_id": conn.seller_id if conn else None,
        "nickname": conn.nickname if conn else None,
        "country_id": conn.country_id if conn else None,
        "connected_at": conn.connected_at.isoformat() if conn and conn.connected_at else None,
        "updated_at": conn.updated_at.isoformat() if conn and conn.updated_at else None,
        "steps": ["Autorizar conta", "Validar token criptografado", "Sincronizar catálogo", "Ativar monitoramento"],
        "mode": "oauth_real" if connected else "oauth_required",
    }]}

def connect_marketplace_demo(db: Session, user: User, marketplace: str) -> dict[str, Any]:
    raise RuntimeError("Conexão demo desativada. Use o OAuth real do Mercado Livre.")
