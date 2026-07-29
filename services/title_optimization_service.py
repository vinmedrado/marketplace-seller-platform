"""PATCH 13/15 — Otimização de Título com IA para Mercado Livre.

Consulta concorrentes públicos reais, calcula score interno, gera sugestões
seguras e salva histórico multi-tenant. Este módulo apenas sugere: não altera
anúncios nem chama endpoints de update do Mercado Livre.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import datetime
from typing import Any

import requests
from sqlalchemy.orm import Session

from config.settings import ML_BASE_URL
from models.orm import ActionRecommendation, Product, TitleOptimizationHistory
from services.ai_title_service import generate_titles_with_ai

log = logging.getLogger("msp.title.optimizer")

STOPWORDS = {
    "de", "da", "do", "das", "dos", "com", "sem", "para", "por", "em", "no", "na", "nos", "nas", "e", "ou", "a", "o", "as", "os",
    "novo", "nova", "original", "produto", "kit", "un", "unidade", "mercado", "livre"
}
GENERIC_WORDS = {"produto", "coisa", "item", "varios", "diversos", "top", "promoção", "oferta", "barato"}
MISLEADING_WORDS = {"garantido", "milagroso", "100%", "número 1", "melhor do mercado"}


class TitleOptimizationError(Exception):
    pass


def _now() -> datetime:
    return datetime.utcnow()


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-ZÀ-ÿ0-9]+", (text or "").lower()) if len(t) > 2 and t not in STOPWORDS]


def _clean_query(query: str) -> str:
    q = re.sub(r"\s+", " ", (query or "").strip())
    if len(q) < 3:
        raise TitleOptimizationError("Informe uma busca com pelo menos 3 caracteres.")
    return q[:120]


def _public_search(query: str, limit: int = 20) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    url = f"{ML_BASE_URL.rstrip('/')}/sites/MLB/search"
    params = {"q": _clean_query(query), "limit": min(max(limit, 5), 50)}
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise TitleOptimizationError("Não foi possível consultar anúncios públicos do Mercado Livre agora.") from exc

    competitors: list[dict[str, Any]] = []
    for row in payload.get("results", [])[:limit]:
        title = row.get("title") or ""
        if not title:
            continue
        competitors.append({
            "title": title,
            "price": row.get("price"),
            "sold_quantity": row.get("sold_quantity") or 0,
            "category_id": row.get("category_id"),
            "permalink": row.get("permalink"),
            "thumbnail": row.get("thumbnail"),
            "condition": row.get("condition"),
            "free_shipping": bool((row.get("shipping") or {}).get("free_shipping")),
        })
    return competitors, payload


def _competitor_terms(competitors: list[dict[str, Any]], current_title: str) -> list[str]:
    counter: Counter[str] = Counter()
    for idx, item in enumerate(competitors):
        weight = 3 if idx < 5 else 2 if idx < 10 else 1
        sold = int(item.get("sold_quantity") or 0)
        if sold > 50:
            weight += 2
        elif sold > 10:
            weight += 1
        for token in _tokens(item.get("title") or ""):
            if token not in GENERIC_WORDS:
                counter[token] += weight
    current = set(_tokens(current_title))
    # mantém também termos presentes no título atual quando são recorrentes no mercado
    terms = [term for term, count in counter.most_common(30) if count >= 2]
    return terms[:20]


def _attribute_values(product: Product | None, manual_attrs: dict[str, Any] | None = None) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    if product is not None:
        for source in [getattr(product, "atributos", None), getattr(product, "raw_payload_json", None)]:
            if isinstance(source, dict):
                attrs.update(source.get("attributes") if isinstance(source.get("attributes"), dict) else source)
        if getattr(product, "marca", None):
            attrs.setdefault("marca", product.marca)
        if getattr(product, "condition", None):
            attrs.setdefault("condition", product.condition)
    if isinstance(manual_attrs, dict):
        attrs.update(manual_attrs)
    return attrs


def score_title(title: str, competitor_terms: list[str], attributes: dict[str, Any] | None = None) -> dict[str, Any]:
    title = title or ""
    attrs = attributes or {}
    title_tokens = set(_tokens(title))
    comp_terms = set(competitor_terms[:15])
    strengths: list[str] = []
    weaknesses: list[str] = []
    score = 50

    length = len(title.strip())
    if 35 <= length <= 60:
        score += 14; strengths.append("Tamanho adequado para leitura e busca.")
    elif length < 25:
        score -= 16; weaknesses.append("Título curto demais; pode faltar contexto de busca.")
    elif length > 70:
        score -= 12; weaknesses.append("Título longo demais; pode perder objetividade.")

    if len(title_tokens) >= 4:
        score += 10; strengths.append("Título possui boa especificidade textual.")
    else:
        score -= 12; weaknesses.append("Título genérico, com poucos termos descritivos.")

    brand_model_terms = []
    for key, value in attrs.items():
        if any(k in str(key).lower() for k in ["marca", "brand", "modelo", "model"]):
            brand_model_terms.extend(_tokens(str(value)))
    if brand_model_terms and any(t in title_tokens for t in brand_model_terms):
        score += 12; strengths.append("Marca/modelo disponível aparece no título.")
    elif brand_model_terms:
        score -= 10; weaknesses.append("Marca/modelo existe nos dados, mas não aparece no título.")

    overlap = title_tokens & comp_terms
    if len(overlap) >= 4:
        score += 16; strengths.append("Inclui termos recorrentes dos principais concorrentes.")
    elif len(overlap) >= 2:
        score += 8; strengths.append("Possui alguma aderência aos termos de concorrentes.")
    else:
        score -= 8; weaknesses.append("Pouca aderência aos termos recorrentes do mercado.")

    if title_tokens & GENERIC_WORDS:
        score -= 8; weaknesses.append("Contém palavras genéricas que reduzem clareza.")
    if any(w in title.lower() for w in MISLEADING_WORDS):
        score -= 20; weaknesses.append("Contém promessa potencialmente enganosa ou exagerada.")
    else:
        score += 6; strengths.append("Não contém promessa enganosa evidente.")

    if re.search(r"\d", title):
        score += 4; strengths.append("Possui especificador numérico quando aplicável.")

    score = max(0, min(100, int(score)))
    if score >= 85:
        status = "Excelente"
    elif score >= 70:
        status = "Bom"
    elif score >= 50:
        status = "Atenção"
    else:
        status = "Fraco"
    return {"score": score, "status": status, "strengths": strengths[:6], "weaknesses": weaknesses[:6]}


def _create_action_signals(db: Session, tenant_id: str, product_id: str | None, title: str, score: int, status: str) -> None:
    signals = []
    if score < 50:
        signals.append(("TITLE_WEAK", "Título fraco detectado", "Este produto tem título genérico e pode perder tráfego orgânico. Sugestão: incluir marca/modelo quando disponível."))
    if score < 75:
        signals.append(("TITLE_OPPORTUNITY", "Oportunidade de SEO no título", "Há termos recorrentes nos concorrentes que podem melhorar a clareza do anúncio, sem garantia de ranking."))
    if score < 85:
        signals.append(("SEO_IMPROVEMENT_RECOMMENDED", "Melhoria de SEO recomendada", "Revise o título sugerido antes de aplicar no Mercado Livre. Este patch não altera anúncios automaticamente."))
    for code, action_title, explanation in signals:
        action_id = f"title-{code.lower()}-{product_id or abs(hash(title))}-{_now().strftime('%Y%m%d%H%M')}"
        exists = db.query(ActionRecommendation).filter_by(id=action_id, tenant_id=tenant_id).first()
        if exists:
            continue
        db.add(ActionRecommendation(
            id=action_id,
            tenant_id=tenant_id,
            product_id=product_id,
            category="seo",
            priority="HIGH" if score < 50 else "MEDIUM",
            origin="Title Optimizer AI",
            title=action_title,
            explanation=explanation,
            recommended_action="Abrir Otimização de Título, revisar sugestões e aplicar manualmente apenas se os atributos forem reais.",
            next_best_action="Revisar sugestão de título",
            expected_impact=max(0, 100 - score),
            confidence=0.78 if status in {"Atenção", "Fraco"} else 0.66,
            status="pending",
        ))


def _serialize_history(db: Session, tenant_id: str, product_id: str | None, original_title: str, result: dict[str, Any]) -> None:
    db.add(TitleOptimizationHistory(
        tenant_id=tenant_id,
        product_id=product_id,
        original_title=original_title,
        optimized_titles_json=result.get("optimized_titles") or [],
        score=int((result.get("score") or {}).get("score") or 0),
        competitor_terms_json=result.get("competitor_terms") or [],
        ai_provider=result.get("ai_provider"),
        warnings_json=result.get("warnings") or [],
        raw_payload_json={"top_competitors": result.get("top_competitors") or [], "score": result.get("score") or {}},
        generated_at=_now(),
    ))


def analyze_title(
    db: Session,
    *,
    tenant_id: str,
    current_title: str,
    product: Product | None = None,
    query: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    title = _clean_query(current_title)
    competitors, raw_payload = _public_search(query or title)
    terms = _competitor_terms(competitors, title)
    attrs = _attribute_values(product)
    score = score_title(title, terms, attrs)
    ai = generate_titles_with_ai(
        original_title=title,
        attributes=attrs,
        category_id=getattr(product, "category_id", None) or getattr(product, "categoria_id", None) if product else None,
        competitor_terms=terms,
        top_competitors=competitors,
    )
    warnings = [
        "As sugestões não garantem posição no Mercado Livre. Revise antes de aplicar.",
        "Patch consultivo: nenhuma alteração será enviada ao Mercado Livre.",
    ] + list(ai.get("warnings") or [])
    if not competitors:
        warnings.append("Nenhum concorrente público relevante encontrado para a busca informada.")

    result = {
        "current_title": title,
        "score": score,
        "optimized_titles": ai.get("suggestions") or [],
        "competitor_terms": terms,
        "top_competitors": competitors[:10],
        "warnings": warnings,
        "ai_provider": ai.get("ai_provider", "fallback"),
        "ai_available": bool(ai.get("ai_available")),
        "generated_at": _now().isoformat() + "Z",
    }
    if persist:
        product_id = getattr(product, "id", None) if product else None
        _serialize_history(db, tenant_id, product_id, title, result)
        _create_action_signals(db, tenant_id, product_id, title, int(score["score"]), score["status"])
        db.commit()
    return result


def optimize_product_title(db: Session, tenant_id: str, product_id: str) -> dict[str, Any]:
    product = db.query(Product).filter_by(id=product_id, cliente_id=tenant_id, ativo=True).first()
    if not product:
        raise TitleOptimizationError("Produto não encontrado para este tenant.")
    title = product.title or product.titulo
    return analyze_title(db, tenant_id=tenant_id, current_title=title, product=product, persist=True)


def analyze_manual_query(db: Session, tenant_id: str, query: str) -> dict[str, Any]:
    return analyze_title(db, tenant_id=tenant_id, current_title=query, query=query, product=None, persist=True)
