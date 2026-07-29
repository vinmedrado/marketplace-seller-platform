"""Transparência, direitos do titular e retenção de dados pessoais."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from config.settings import (
    API_LOG_RETENTION_DAYS,
    PRIVACY_CONTACT_EMAIL,
    PRIVACY_REQUEST_RETENTION_DAYS,
    SCRAPING_LOG_RETENTION_DAYS,
)
from models.orm import (
    ApiLog,
    Cliente,
    OAuthState,
    Organization,
    PrivacyRequest,
    RefreshToken,
    ScrapingLog,
    User,
    UserInvite,
)

REQUEST_LABELS = {
    "access": "Confirmação e acesso",
    "correction": "Correção",
    "deletion": "Eliminação",
    "anonymization": "Anonimização ou bloqueio",
    "portability": "Portabilidade",
    "revocation": "Revogação de consentimento",
    "review": "Revisão de decisão automatizada",
}


def privacy_summary() -> dict[str, Any]:
    return {
        "controller": "Operador individual do MarketPlace Seller Platform",
        "contact": PRIVACY_CONTACT_EMAIL or "Configure PRIVACY_CONTACT_EMAIL",
        "scope": "Console pessoal; a demonstração pública não coleta dados pessoais.",
        "purposes": [
            "Autenticação e controle de acesso",
            "Execução das funcionalidades solicitadas pelo usuário",
            "Segurança, prevenção a fraude e diagnóstico operacional",
            "Atendimento de direitos do titular",
        ],
        "legal_bases": [
            "Execução de contrato ou procedimentos solicitados pelo titular",
            "Legítimo interesse, após avaliação e respeitados os direitos do titular",
            "Cumprimento de obrigação legal ou regulatória, quando aplicável",
            "Consentimento somente para tratamentos opcionais identificados",
        ],
        "data_categories": [
            "Identificação e contato: nome e e-mail",
            "Credenciais protegidas: hash de senha e tokens criptografados ou em hash",
            "Vínculo organizacional e perfil de acesso",
            "Registros técnicos mínimos de segurança e operação",
        ],
        "sharing": [
            "Mercado Livre, quando o usuário inicia a integração OAuth",
            "Resend, apenas quando envio transacional de e-mail é configurado",
            "Pagar.me, apenas quando billing é configurado",
        ],
        "rights": list(REQUEST_LABELS.values()),
        "retention": {
            "api_logs_days": API_LOG_RETENTION_DAYS,
            "scraping_logs_days": SCRAPING_LOG_RETENTION_DAYS,
            "privacy_requests_days": PRIVACY_REQUEST_RETENTION_DAYS,
            "account_data": "Enquanto a conta estiver ativa ou pelo prazo necessário à finalidade e obrigações aplicáveis.",
        },
        "automated_decisions": "ML apenas recomenda; nenhuma predição publica ou altera preço sem ação humana.",
    }


def export_user_data(db: Session, user: User) -> dict[str, Any]:
    tenant = db.query(Cliente).filter_by(id=user.cliente_id).first()
    organization = db.query(Organization).filter_by(id=user.organization_id, cliente_id=user.cliente_id).first()
    requests = (
        db.query(PrivacyRequest)
        .filter_by(user_id=user.id, cliente_id=user.cliente_id)
        .order_by(PrivacyRequest.requested_at.asc())
        .all()
    )
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "format_version": "1.0",
        "subject": {
            "id": user.id,
            "name": user.nome,
            "email": user.email,
            "role": user.role,
            "active": user.ativo,
            "last_login_at": user.ultimo_login_em.isoformat() if user.ultimo_login_em else None,
            "created_at": user.criado_em.isoformat() if user.criado_em else None,
        },
        "organization": {
            "id": organization.id if organization else None,
            "name": organization.nome if organization else None,
        },
        "tenant": {
            "id": tenant.id if tenant else None,
            "name": tenant.nome if tenant else None,
            "account_email": tenant.email if tenant else None,
        },
        "privacy_requests": [
            {
                "protocol": row.id,
                "type": row.request_type,
                "status": row.status,
                "requested_at": row.requested_at.isoformat(),
                "deadline_at": row.legal_deadline_at.isoformat(),
                "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
            }
            for row in requests
        ],
        "excluded_security_material": [
            "password hashes",
            "access, refresh and marketplace tokens",
            "OAuth nonces",
        ],
    }


def create_privacy_request(db: Session, user: User, request_type: str, description: str | None) -> dict[str, Any]:
    pending = (
        db.query(PrivacyRequest)
        .filter_by(
            cliente_id=user.cliente_id,
            user_id=user.id,
            request_type=request_type,
            status="pending",
        )
        .first()
    )
    if pending:
        return serialize_request(pending)
    now = datetime.utcnow()
    row = PrivacyRequest(
        cliente_id=user.cliente_id,
        user_id=user.id,
        request_type=request_type,
        description=description,
        status="pending",
        requested_at=now,
        legal_deadline_at=now + timedelta(days=15),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_request(row)


def list_privacy_requests(db: Session, user: User) -> dict[str, Any]:
    rows = (
        db.query(PrivacyRequest)
        .filter_by(cliente_id=user.cliente_id, user_id=user.id)
        .order_by(PrivacyRequest.requested_at.desc())
        .all()
    )
    return {"items": [serialize_request(row) for row in rows]}


def serialize_request(row: PrivacyRequest) -> dict[str, Any]:
    return {
        "protocol": row.id,
        "type": row.request_type,
        "type_label": REQUEST_LABELS.get(row.request_type, row.request_type),
        "status": row.status,
        "requested_at": row.requested_at,
        "deadline_at": row.legal_deadline_at,
        "resolved_at": row.resolved_at,
    }


def cleanup_expired_data(db: Session, *, apply: bool = False) -> dict[str, Any]:
    now = datetime.utcnow()
    targets = {
        "api_logs": db.query(ApiLog).filter(ApiLog.criado_em < now - timedelta(days=API_LOG_RETENTION_DAYS)),
        "scraping_logs": db.query(ScrapingLog).filter(
            ScrapingLog.criado_em < now - timedelta(days=SCRAPING_LOG_RETENTION_DAYS)
        ),
        "expired_oauth_states": db.query(OAuthState).filter(OAuthState.expires_at < now),
        "expired_refresh_tokens": db.query(RefreshToken).filter(RefreshToken.expires_at < now),
        "expired_pending_invites": db.query(UserInvite).filter(
            UserInvite.status == "pending",
            UserInvite.expires_at.isnot(None),
            UserInvite.expires_at < now,
        ),
        "old_privacy_requests": db.query(PrivacyRequest).filter(
            PrivacyRequest.requested_at < now - timedelta(days=PRIVACY_REQUEST_RETENTION_DAYS),
            PrivacyRequest.status.in_(("completed", "rejected", "cancelled")),
        ),
    }
    counts = {name: query.count() for name, query in targets.items()}
    if apply:
        for query in targets.values():
            query.delete(synchronize_session=False)
        db.commit()
    return {"dry_run": not apply, "deleted": counts if apply else {}, "eligible": counts}
