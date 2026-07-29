"""Serviço operacional para perguntas Mercado Livre + sugestões com IA.

PATCH 6/10 — busca perguntas abertas reais, gera sugestões seguras e envia
respostas somente após aprovação manual do seller.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import requests
from sqlalchemy.orm import Session

from config.settings import ML_BASE_URL
from models.orm import MarketplaceConnection, OperationalEvent, QuestionsCache
from services.ai_questions_service import build_question_answer_suggestion
from services.ml_token_service import MLTokenServiceError, get_connection, get_valid_access_token

log = logging.getLogger("msp.questions")
MARKETPLACE = "mercadolivre"


class QuestionsServiceError(Exception):
    pass


def _iso(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        return value
    return value.replace(microsecond=0).isoformat() + "Z"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _sanitize_text(text: str, *, min_len: int = 2, max_len: int = 1000) -> str:
    cleaned = " ".join((text or "").replace("\x00", " ").split())
    if len(cleaned) < min_len:
        raise QuestionsServiceError("Texto da resposta é obrigatório.")
    if len(cleaned) > max_len:
        raise QuestionsServiceError(f"Texto muito longo. Limite seguro: {max_len} caracteres.")
    return cleaned


def _record_event(
    db: Session,
    tenant_id: str,
    event_type: str,
    title: str,
    description: str = "",
    *,
    severity: str = "info",
    throttle_seconds: int = 0,
) -> None:
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
        category="questions_ai",
        severity=severity,
        title=title,
        description=description[:500],
    ))


def _extract_questions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("questions", "results", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def _get_item(token: str, item_id: str) -> dict[str, Any]:
    if not item_id:
        return {}
    try:
        resp = requests.get(f"{ML_BASE_URL}/items/{item_id}", headers=_headers(token), timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        log.warning("question_item_fetch_failed", extra={"event": "question_item_fetch_failed", "item_id": item_id, "error_type": type(exc).__name__})
        return {}


def _upsert_cache(
    db: Session,
    tenant_id: str,
    conn: MarketplaceConnection,
    question: dict[str, Any],
    item: dict[str, Any],
    suggestion: Any,
) -> QuestionsCache:
    qid = str(question.get("id") or question.get("question_id") or "")
    if not qid:
        raise QuestionsServiceError("Pergunta Mercado Livre sem id.")
    item_id = str(question.get("item_id") or item.get("id") or "")
    qtext = question.get("text") or question.get("question_text") or ""
    row = db.query(QuestionsCache).filter_by(tenant_id=tenant_id, question_id=qid).first()
    now = datetime.utcnow()
    if not row:
        row = QuestionsCache(
            tenant_id=tenant_id,
            marketplace_connection_id=conn.id,
            question_id=qid,
            created_at=now,
        )
        db.add(row)
    row.marketplace_connection_id = conn.id
    row.item_id = item_id
    row.question_text = qtext
    row.status = question.get("status") or "UNANSWERED"
    row.suggested_answer = suggestion.text
    row.ai_provider = suggestion.ai_provider
    row.confidence = suggestion.confidence
    row.needs_review = suggestion.needs_review
    row.raw_payload_json = {"question": question, "item": item}
    row.updated_at = now
    return row


def _serialize_question(row: QuestionsCache) -> dict[str, Any]:
    raw = row.raw_payload_json or {}
    item = raw.get("item") or {}
    question = raw.get("question") or {}
    return {
        "id": row.question_id,
        "cache_id": str(row.id),
        "item_id": row.item_id,
        "item_title": item.get("title"),
        "item_permalink": item.get("permalink"),
        "item_thumbnail": item.get("thumbnail") or item.get("secure_thumbnail"),
        "question_text": row.question_text,
        "created_at": question.get("date_created") or _iso(row.created_at),
        "status": row.status,
        "suggested_answer": row.suggested_answer,
        "ai_provider": row.ai_provider,
        "ai_available": bool(row.ai_provider and row.ai_provider != "fallback"),
        "confidence": float(row.confidence or 0),
        "needs_review": bool(row.needs_review),
        "answered_at": _iso(row.answered_at),
    }


def fetch_pending_questions(db: Session, tenant_id: str, *, limit: int = 30) -> dict[str, Any]:
    conn = get_connection(db, tenant_id)
    if not conn:
        raise QuestionsServiceError("Conecte uma conta Mercado Livre antes de consultar perguntas.")
    try:
        token = get_valid_access_token(db, tenant_id)
    except MLTokenServiceError as exc:
        raise QuestionsServiceError(str(exc)) from exc

    params = {"status": "UNANSWERED", "limit": min(max(limit, 1), 50), "sort_fields": "date_created", "sort_types": "DESC"}
    try:
        log.info("questions_pending_fetch_started", extra={"event": "questions_pending_fetch_started", "tenant_id": str(tenant_id)})
        resp = requests.get(f"{ML_BASE_URL}/my/received_questions/search", headers=_headers(token), params=params, timeout=20)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:
        log.warning("questions_pending_fetch_failed", extra={"event": "questions_pending_fetch_failed", "tenant_id": str(tenant_id), "error_type": type(exc).__name__})
        raise QuestionsServiceError("Não foi possível buscar perguntas abertas no Mercado Livre agora.") from exc

    rows: list[QuestionsCache] = []
    for question in _extract_questions(payload)[:limit]:
        item_id = str(question.get("item_id") or "")
        item = _get_item(token, item_id)
        suggestion = build_question_answer_suggestion(question_text=question.get("text") or "", item=item)
        row = _upsert_cache(db, tenant_id, conn, question, item, suggestion)
        rows.append(row)
        try:
            created_raw = question.get("date_created") or question.get("created_at")
            created_dt = None
            if isinstance(created_raw, str):
                created_dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00")).replace(tzinfo=None)
            if created_dt and datetime.utcnow() - created_dt > timedelta(hours=2):
                from services.alerts_service import create_alert
                create_alert(
                    db,
                    tenant_id,
                    alert_type="QUESTION_PENDING_TOO_LONG",
                    severity="warning",
                    title="Pergunta aberta há mais de 2h",
                    message=f"Pergunta no produto {item.get('title') or item_id}: {row.question_text[:180]}",
                    dedupe_key=f"question:{row.question_id}:QUESTION_PENDING_TOO_LONG",
                )
        except Exception:
            log.warning("question_pending_alert_failed_soft", extra={"event": "question_pending_alert_failed_soft", "tenant_id": str(tenant_id)})
        if suggestion.ai_provider == "fallback":
            _record_event(db, tenant_id, "ai_fallback_used", "Fallback seguro usado", "GROQ indisponível ou não configurado.", throttle_seconds=300)

    _record_event(db, tenant_id, "questions_pending_fetched", "Perguntas abertas consultadas", f"{len(rows)} perguntas abertas processadas.", throttle_seconds=120)
    db.commit()
    return {"questions": [_serialize_question(r) for r in rows], "total": len(rows), "generated_at": _iso(datetime.utcnow())}


def suggest_answer(db: Session, tenant_id: str, question_id: str, *, custom_context: str | None = None) -> dict[str, Any]:
    row = db.query(QuestionsCache).filter_by(tenant_id=tenant_id, question_id=str(question_id)).first()
    if not row:
        # Tenta preencher cache antes de falhar para cobrir uso direto do endpoint.
        fetch_pending_questions(db, tenant_id, limit=50)
        row = db.query(QuestionsCache).filter_by(tenant_id=tenant_id, question_id=str(question_id)).first()
    if not row:
        raise QuestionsServiceError("Pergunta não encontrada para este seller.")

    item = (row.raw_payload_json or {}).get("item") or {}
    suggestion = build_question_answer_suggestion(question_text=row.question_text, item=item, custom_context=custom_context)
    row.suggested_answer = suggestion.text
    row.ai_provider = suggestion.ai_provider
    row.confidence = suggestion.confidence
    row.needs_review = True
    row.updated_at = datetime.utcnow()
    _record_event(db, tenant_id, "question_suggestion_generated", "Sugestão de resposta gerada", f"Pergunta {row.question_id} recebeu nova sugestão.")
    if suggestion.ai_provider == "fallback":
        _record_event(db, tenant_id, "ai_fallback_used", "Fallback seguro usado", "Sugestão heurística retornada.", throttle_seconds=300)
    db.commit()
    db.refresh(row)
    return _serialize_question(row)


def send_approved_answer(db: Session, tenant_id: str, question_id: str, *, text: str) -> dict[str, Any]:
    answer_text = _sanitize_text(text, min_len=2, max_len=1000)
    row = db.query(QuestionsCache).filter_by(tenant_id=tenant_id, question_id=str(question_id)).first()
    if not row:
        raise QuestionsServiceError("Pergunta não encontrada para este seller. Atualize a lista antes de responder.")
    if row.status and row.status.upper() not in {"UNANSWERED", "PENDING"}:
        raise QuestionsServiceError("Esta pergunta não está aberta para resposta.")

    try:
        token = get_valid_access_token(db, tenant_id)
        resp = requests.post(
            f"{ML_BASE_URL}/answers",
            headers=_headers(token),
            json={"question_id": row.question_id, "text": answer_text},
            timeout=20,
        )
        resp.raise_for_status()
        ml_response = resp.json() if resp.content else {}
    except Exception as exc:
        db.rollback()
        _record_event(db, tenant_id, "question_answer_failed", "Falha ao enviar resposta", f"Pergunta {question_id}: erro Mercado Livre.", severity="warning")
        db.commit()
        log.warning("question_answer_failed", extra={"event": "question_answer_failed", "tenant_id": str(tenant_id), "question_id": str(question_id), "error_type": type(exc).__name__})
        raise QuestionsServiceError("Não foi possível enviar a resposta ao Mercado Livre agora.") from exc

    row.status = "ANSWERED"
    row.answered_at = datetime.utcnow()
    row.suggested_answer = answer_text
    row.updated_at = datetime.utcnow()
    raw = row.raw_payload_json or {}
    raw["answer_response"] = ml_response
    row.raw_payload_json = raw
    _record_event(db, tenant_id, "question_answer_sent", "Resposta enviada ao Mercado Livre", f"Pergunta {row.question_id} respondida manualmente pelo seller.")
    db.commit()
    db.refresh(row)
    return {"status": "sent", "question": _serialize_question(row), "sent_at": _iso(row.answered_at)}
