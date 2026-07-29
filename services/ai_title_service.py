"""PATCH 13/15 — IA segura para otimização de títulos Mercado Livre.

Camada isolada para Groq/LLM com fallback heurístico. Nunca altera anúncios e
nunca inventa atributos: só usa título, atributos internos e termos observados
em concorrentes públicos.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import requests

from config.settings import GROQ_API_KEY, GROQ_MODEL

log = logging.getLogger("msp.title.ai")

PROHIBITED_TERMS = {
    "garantido", "milagroso", "100%", "melhor do mercado", "número 1", "original"  # original só deve vir se já existir nos dados
}
MAX_TITLE_LEN = 60


@dataclass
class TitleSuggestion:
    title: str
    reasoning: str
    expected_impact: str
    risk_notes: str


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-ZÀ-ÿ0-9]+", (text or "").lower())


def _safe_attributes(attributes: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(attributes, dict):
        return {}
    allowed: dict[str, Any] = {}
    for key, value in attributes.items():
        if value in (None, "", [], {}):
            continue
        key_l = str(key).lower()
        if any(x in key_l for x in ["token", "secret", "auth", "password"]):
            continue
        if isinstance(value, (str, int, float, bool)):
            allowed[str(key)] = value
        elif isinstance(value, dict):
            name = value.get("name") or value.get("value_name") or value.get("value")
            if name:
                allowed[str(key)] = name
    return allowed


def _sanitize_title(title: str, source_terms: set[str]) -> str:
    title = _normalize_space(title)
    title = re.sub(r"[!]{2,}", "!", title)
    title = title.replace("🔥", "").replace("⭐", "")
    words = title.split()
    clean_words = []
    for word in words:
        base = re.sub(r"[^a-zA-ZÀ-ÿ0-9]", "", word).lower()
        if base in {"garantido", "milagroso"}:
            continue
        clean_words.append(word)
    title = _normalize_space(" ".join(clean_words))
    if len(title) > MAX_TITLE_LEN:
        # corta em fronteira de palavra para respeitar o padrão do ML sem quebrar texto
        title = title[:MAX_TITLE_LEN].rsplit(" ", 1)[0]
    return title


def _validate_no_invention(title: str, original_title: str, attributes: dict[str, Any], competitor_terms: list[str]) -> tuple[bool, list[str]]:
    """Validação conservadora: bloqueia claims sensíveis não presentes no contexto."""
    warnings: list[str] = []
    context = " ".join([original_title, json.dumps(attributes, ensure_ascii=False), " ".join(competitor_terms)]).lower()
    title_l = title.lower()
    sensitive_terms = [
        "original", "genuíno", "oficial", "premium", "profissional", "compatível", "kit", "novo", "importado",
        "couro", "algodão", "inox", "madeira", "preto", "branco", "azul", "vermelho", "xl", "gg", "p", "m", "g",
    ]
    for term in sensitive_terms:
        if re.search(rf"\b{re.escape(term)}\b", title_l) and not re.search(rf"\b{re.escape(term)}\b", context):
            warnings.append(f"Termo removido/bloqueado por não estar nos dados disponíveis: {term}")
            return False, warnings
    return True, warnings


def fallback_title_suggestions(
    *,
    original_title: str,
    attributes: dict[str, Any] | None,
    competitor_terms: list[str],
    max_suggestions: int = 3,
) -> list[dict[str, str]]:
    attrs = _safe_attributes(attributes)
    source_terms = set(_tokenize(original_title)) | set(_tokenize(" ".join(map(str, attrs.values())))) | set(competitor_terms)
    base_parts: list[str] = []
    for field in ["brand", "marca", "BRAND", "Marca", "model", "modelo", "MODEL", "Modelo"]:
        if attrs.get(field) and str(attrs[field]).lower() not in _tokenize(original_title):
            base_parts.append(str(attrs[field]))
    base_parts.append(original_title)
    strong_terms = [t.title() for t in competitor_terms[:8] if t not in _tokenize(original_title) and len(t) > 2]

    candidates = []
    variants = [
        base_parts + strong_terms[:2],
        base_parts + strong_terms[:3],
        [original_title] + strong_terms[:4],
    ]
    seen = set()
    for parts in variants:
        title = _sanitize_title(" ".join([str(p) for p in parts if p]), source_terms)
        ok, notes = _validate_no_invention(title, original_title, attrs, competitor_terms)
        if not ok:
            title = _sanitize_title(original_title, source_terms)
        if title.lower() in seen:
            continue
        seen.add(title.lower())
        candidates.append({
            "title": title,
            "reasoning": "Sugestão heurística usando o título atual, atributos internos disponíveis e termos recorrentes observados nos anúncios concorrentes.",
            "expected_impact": "Pode melhorar clareza e cobertura de termos de busca sem prometer ganho de ranking.",
            "risk_notes": "Revise antes de aplicar. O sistema não altera o anúncio automaticamente e não adiciona atributos ausentes.",
        })
        if len(candidates) >= max_suggestions:
            break
    return candidates or [{
        "title": _sanitize_title(original_title, source_terms),
        "reasoning": "Título atual preservado por ausência de termos seguros suficientes para otimização.",
        "expected_impact": "Baixo impacto esperado até haver mais atributos ou concorrentes relevantes.",
        "risk_notes": "Inclua marca/modelo/atributos reais no catálogo para sugestões melhores.",
    }]


def generate_titles_with_ai(
    *,
    original_title: str,
    attributes: dict[str, Any] | None,
    category_id: str | None,
    competitor_terms: list[str],
    top_competitors: list[dict[str, Any]],
) -> dict[str, Any]:
    attrs = _safe_attributes(attributes)
    if not GROQ_API_KEY:
        return {
            "ai_provider": "fallback",
            "ai_available": False,
            "suggestions": fallback_title_suggestions(original_title=original_title, attributes=attrs, competitor_terms=competitor_terms),
        }

    prompt = {
        "role": "user",
        "content": (
            "Você é especialista em SEO para Mercado Livre Brasil. Responda em JSON válido. "
            "Gere até 3 sugestões de título. Regras obrigatórias: não invente marca, modelo, compatibilidade, tamanho, cor, material, condição ou claims. "
            "Use somente dados fornecidos. Não prometa ranking. Não use termos enganosos. Título objetivo, no máximo 60 caracteres. "
            "Formato: {\"suggestions\":[{\"title\":\"...\",\"reasoning\":\"...\",\"expected_impact\":\"...\",\"risk_notes\":\"...\"}]}\n\n"
            f"Título atual: {original_title}\nCategoria: {category_id or ''}\nAtributos internos: {json.dumps(attrs, ensure_ascii=False)}\n"
            f"Termos recorrentes de concorrentes: {json.dumps(competitor_terms[:20], ensure_ascii=False)}\n"
            f"Top concorrentes públicos: {json.dumps(top_competitors[:8], ensure_ascii=False)}"
        ),
    }
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": "Você retorna apenas JSON válido e segue regras rígidas de compliance para marketplace."},
                    prompt,
                ],
                "temperature": 0.2,
                "max_tokens": 900,
            },
            timeout=25,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        raw_suggestions = parsed.get("suggestions") or []
        suggestions: list[dict[str, str]] = []
        validation_warnings: list[str] = []
        for item in raw_suggestions[:3]:
            title = _sanitize_title(str(item.get("title") or original_title), set(competitor_terms))
            ok, notes = _validate_no_invention(title, original_title, attrs, competitor_terms)
            validation_warnings.extend(notes)
            if not ok:
                continue
            suggestions.append({
                "title": title,
                "reasoning": str(item.get("reasoning") or "Sugestão baseada nos dados fornecidos."),
                "expected_impact": str(item.get("expected_impact") or "Pode melhorar clareza do título, sem garantia de ranking."),
                "risk_notes": str(item.get("risk_notes") or "Revise antes de aplicar."),
            })
        if not suggestions:
            suggestions = fallback_title_suggestions(original_title=original_title, attributes=attrs, competitor_terms=competitor_terms)
            return {"ai_provider": "groq+fallback_validation", "ai_available": True, "suggestions": suggestions, "warnings": validation_warnings}
        return {"ai_provider": "groq", "ai_available": True, "suggestions": suggestions, "warnings": validation_warnings}
    except Exception as exc:
        log.warning("Groq indisponível para otimização de título: %s", exc)
        return {
            "ai_provider": "fallback",
            "ai_available": False,
            "suggestions": fallback_title_suggestions(original_title=original_title, attributes=attrs, competitor_terms=competitor_terms),
            "warnings": ["IA Groq indisponível; fallback heurístico seguro utilizado."],
        }
