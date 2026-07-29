"""AI assistant seguro para perguntas do Mercado Livre.

PATCH 6/10 — gera SUGESTÕES de resposta. Nunca envia automaticamente e nunca
inventa estoque, prazo, desconto ou compatibilidade.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests

from config.settings import GROQ_API_KEY, GROQ_MODEL

log = logging.getLogger("msp.questions.ai")
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


@dataclass
class QuestionSuggestion:
    text: str
    ai_provider: str
    ai_available: bool
    confidence: float
    needs_review: bool = True


def _fallback_answer() -> QuestionSuggestion:
    return QuestionSuggestion(
        text="Olá! Obrigado pela pergunta. Vou confirmar essa informação e retorno em seguida.",
        ai_provider="fallback",
        ai_available=False,
        confidence=0.35,
        needs_review=True,
    )


def _safe_trim(text: str, max_len: int = 900) -> str:
    cleaned = " ".join((text or "").replace("\x00", " ").split())
    return cleaned[:max_len].strip()


def build_question_answer_suggestion(
    *,
    question_text: str,
    item: dict[str, Any] | None = None,
    custom_context: str | None = None,
) -> QuestionSuggestion:
    """Gera sugestão com Groq quando configurado, senão fallback explícito.

    A saída é sempre tratada como sugestão revisável pelo seller.
    """
    item = item or {}
    if not GROQ_API_KEY:
        log.info("ai_fallback_used", extra={"event": "ai_fallback_used", "reason": "missing_groq_key"})
        return _fallback_answer()

    product_context = {
        "title": item.get("title"),
        "status": item.get("status"),
        "available_quantity": item.get("available_quantity"),
        "condition": item.get("condition"),
        "permalink": item.get("permalink"),
        "shipping": item.get("shipping"),
        "attributes": item.get("attributes"),
    }
    system = (
        "Você é um assistente operacional para vendedores do Mercado Livre no Brasil. "
        "Gere uma resposta curta, educada e objetiva em português do Brasil. "
        "Use SOMENTE as informações fornecidas. Não invente estoque, compatibilidade, desconto, prazo, garantia ou política. "
        "Se faltar informação, peça para o seller confirmar antes de responder. "
        "Não diga que a compra está garantida. Não prometa disponibilidade futura. "
        "Retorne apenas o texto da resposta sugerida ao comprador."
    )
    user = (
        f"Pergunta do comprador: {_safe_trim(question_text, 500)}\n"
        f"Dados conhecidos do anúncio: {product_context}\n"
        f"Contexto adicional do seller: {_safe_trim(custom_context or '', 500) or 'nenhum'}"
    )
    try:
        resp = requests.post(
            GROQ_CHAT_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
                "max_tokens": 220,
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        text = _safe_trim(data.get("choices", [{}])[0].get("message", {}).get("content", ""), 900)
        if not text:
            return _fallback_answer()
        return QuestionSuggestion(
            text=text,
            ai_provider=f"groq:{GROQ_MODEL}",
            ai_available=True,
            confidence=0.78,
            needs_review=True,
        )
    except Exception as exc:
        log.warning("ai_fallback_used", extra={"event": "ai_fallback_used", "reason": "groq_error", "error_type": type(exc).__name__})
        return _fallback_answer()
