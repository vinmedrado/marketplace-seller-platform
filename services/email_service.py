"""Serviço de e-mail transacional via Resend.

Falha de configuração ou de envio nunca deve quebrar o fluxo principal do
MarketPlace Seller Platform. Todas as funções retornam True/False e sanitizam logs para não expor
chaves ou dados sensíveis.
"""
from __future__ import annotations

import html
import logging
from typing import Any

import requests

from config.settings import RESEND_API_KEY, RESEND_FROM_EMAIL, RESEND_FROM_NAME

log = logging.getLogger("msp.email")
RESEND_EMAILS_URL = "https://api.resend.com/emails"
TIMEOUT_SECONDS = 15


def _configured() -> bool:
    if not RESEND_API_KEY:
        log.warning("resend_not_configured", extra={"event": "resend_not_configured"})
        return False
    return True


def _from_header() -> str:
    name = (RESEND_FROM_NAME or "MarketPlace Seller Platform").strip()
    email = (RESEND_FROM_EMAIL or "noreply@example.invalid").strip()
    return f"{name} <{email}>" if name else email


def _base_html(title: str, body: str, cta_label: str | None = None, cta_url: str | None = None) -> str:
    safe_title = html.escape(title)
    button = ""
    if cta_label and cta_url:
        safe_label = html.escape(cta_label)
        safe_url = html.escape(cta_url, quote=True)
        button = f'''
        <p style="margin:28px 0;">
          <a href="{safe_url}" style="background:#0f172a;color:#ffffff;text-decoration:none;padding:12px 18px;border-radius:10px;display:inline-block;font-weight:700;">
            {safe_label}
          </a>
        </p>
        '''
    return f'''
    <div style="font-family:Inter,Arial,sans-serif;background:#f8fafc;padding:32px;color:#0f172a;">
      <div style="max-width:620px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:18px;padding:28px;">
        <div style="font-size:14px;font-weight:800;letter-spacing:.08em;color:#2563eb;text-transform:uppercase;">MarketPlace Seller Platform</div>
        <h1 style="font-size:24px;line-height:1.25;margin:14px 0 12px;">{safe_title}</h1>
        <div style="font-size:15px;line-height:1.65;color:#334155;">{body}</div>
        {button}
        <hr style="border:none;border-top:1px solid #e2e8f0;margin:28px 0;" />
        <p style="font-size:12px;line-height:1.5;color:#64748b;margin:0;">
          Este é um e-mail operacional do MarketPlace Seller Platform. Caso você não reconheça esta ação, ignore esta mensagem.
        </p>
      </div>
    </div>
    '''


def _send_email(to_email: str, subject: str, html_body: str) -> bool:
    if not _configured():
        return False
    to = (to_email or "").strip().lower()
    if not to:
        log.warning("email_missing_recipient", extra={"event": "email_missing_recipient"})
        return False
    payload: dict[str, Any] = {"from": _from_header(), "to": [to], "subject": subject, "html": html_body}
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        response = requests.post(RESEND_EMAILS_URL, json=payload, headers=headers, timeout=TIMEOUT_SECONDS)
        if 200 <= response.status_code < 300:
            return True
        log.warning("resend_send_failed", extra={"event": "resend_send_failed", "status_code": response.status_code, "to": to})
        return False
    except requests.RequestException as exc:
        log.warning("resend_request_failed", extra={"event": "resend_request_failed", "error_type": type(exc).__name__, "to": to})
        return False


def send_invite_email(to_email: str, invite_url: str, org_name: str) -> bool:
    """Envia convite de usuário para a organização."""
    safe_org = html.escape(org_name or "sua organização")
    safe_url = html.escape(invite_url or "", quote=True)
    body = f'''
      <p>Você foi convidado para acessar a organização <strong>{safe_org}</strong> no MarketPlace Seller Platform.</p>
      <p>Use o botão abaixo para aceitar o convite e concluir seu primeiro acesso.</p>
      <p style="font-size:13px;color:#64748b;">Link de convite: <a href="{safe_url}">{safe_url}</a></p>
    '''
    return _send_email(to_email, f"Convite para acessar {org_name or 'MarketPlace Seller Platform'}", _base_html("Convite para o MarketPlace Seller Platform", body, "Aceitar convite", invite_url))


def send_welcome_email(to_email: str, user_name: str, org_name: str) -> bool:
    """Envia boas-vindas após o primeiro acesso."""
    safe_name = html.escape(user_name or "tudo bem")
    safe_org = html.escape(org_name or "sua operação")
    body = f'''
      <p>Olá, <strong>{safe_name}</strong>.</p>
      <p>Seu acesso ao MarketPlace Seller Platform para <strong>{safe_org}</strong> está ativo.</p>
      <p>Você já pode conectar o Mercado Livre, sincronizar o catálogo e acompanhar os principais sinais operacionais.</p>
    '''
    return _send_email(to_email, "Bem-vindo ao MarketPlace Seller Platform", _base_html("Bem-vindo ao MarketPlace Seller Platform", body))


def send_sync_complete_email(to_email: str, user_name: str, total_synced: int) -> bool:
    """Notifica quando a sync do catálogo ML é concluída."""
    safe_name = html.escape(user_name or "seller")
    total = max(0, int(total_synced or 0))
    body = f'''
      <p>Olá, <strong>{safe_name}</strong>.</p>
      <p>A sincronização do catálogo Mercado Livre foi concluída.</p>
      <p><strong>{total}</strong> produto(s) foram processados pelo MarketPlace Seller Platform.</p>
      <p>Agora você pode revisar Buy Box, saúde da conta, perguntas, pricing, forecast e análise de portfólio.</p>
    '''
    return _send_email(to_email, "Sincronização de catálogo concluída", _base_html("Catálogo sincronizado", body))


def send_billing_confirmation_email(to_email: str, user_name: str, plan_name: str, value_brl: str) -> bool:
    """Confirma assinatura de plano após pagamento aprovado."""
    safe_name = html.escape(user_name or "seller")
    safe_plan = html.escape(plan_name or "plano MarketPlace Seller Platform")
    safe_value = html.escape(value_brl or "")
    body = f'''
      <p>Olá, <strong>{safe_name}</strong>.</p>
      <p>Sua assinatura do plano <strong>{safe_plan}</strong> foi registrada com sucesso.</p>
      <p>Valor: <strong>{safe_value}</strong></p>
      <p>Você pode acompanhar status de assinatura, limites e uso na área de Billing do MarketPlace Seller Platform.</p>
    '''
    return _send_email(to_email, "Assinatura MarketPlace Seller Platform confirmada", _base_html("Assinatura confirmada", body))
