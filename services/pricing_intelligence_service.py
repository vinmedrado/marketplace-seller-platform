"""Pricing Intelligence Scanner Freemium.

PATCH 5/10 — ferramenta pública que consulta anúncios reais do Mercado Livre
via API pública e calcula distribuição, concorrentes e preço sugerido.

Não depende de login, não usa mock/fake data e mantém cache em memória com TTL
curto para reduzir chamadas repetidas durante testes/demos.
"""
from __future__ import annotations

import logging
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime
from statistics import mean, median
from typing import Any
from urllib.parse import quote_plus

import requests

from config.settings import ML_BASE_URL

log = logging.getLogger("msp.pricing.scanner")

REQUEST_TIMEOUT = 12
MAX_ANALYZED_ITEMS = 50
CACHE_TTL_SECONDS = 300
COMMISSION_RATE = 0.14
TAX_RATE = 0.06
MIN_QUERY_LEN = 3

_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


class PricingScanError(Exception):
    """Erro controlado do scanner público."""


@dataclass(frozen=True)
class NormalizedOffer:
    id: str
    title: str
    price: float
    currency_id: str | None
    available_quantity: int
    sold_quantity: int
    condition: str | None
    permalink: str | None
    thumbnail: str | None
    free_shipping: bool
    listing_type_id: str | None
    category_id: str | None
    seller_reputation: str | None


def _sanitize_query(query: str) -> str:
    cleaned = re.sub(r"\s+", " ", (query or "").strip())
    cleaned = re.sub(r"[^\w\s\-.,+/áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]", "", cleaned)
    if len(cleaned) < MIN_QUERY_LEN:
        raise PricingScanError("Informe pelo menos 3 caracteres para pesquisar no Mercado Livre.")
    return cleaned[:120]


def _cost_key(cost: float | None) -> str:
    return "none" if cost is None else f"{round(float(cost), 2):.2f}"


def _cache_key(query: str, cost: float | None) -> str:
    return f"{query.lower()}::{_cost_key(cost)}"


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 2)
    k = (len(ordered) - 1) * percentile
    floor = math.floor(k)
    ceil = math.ceil(k)
    if floor == ceil:
        return round(ordered[int(k)], 2)
    return round(ordered[floor] * (ceil - k) + ordered[ceil] * (k - floor), 2)


def _seller_reputation(item: dict[str, Any]) -> str | None:
    seller = item.get("seller") or {}
    seller_rep = seller.get("seller_reputation") or {}
    transactions = seller_rep.get("transactions") or {}
    level = seller_rep.get("level_id") or seller_rep.get("power_seller_status")
    completed = transactions.get("completed")
    if level and completed:
        return f"{level} · {completed} vendas concluídas"
    if level:
        return str(level)
    if completed:
        return f"{completed} vendas concluídas"
    return None


def _normalize_offer(item: dict[str, Any]) -> NormalizedOffer | None:
    try:
        price = float(item.get("price") or 0)
    except (TypeError, ValueError):
        return None
    if price <= 0:
        return None
    shipping = item.get("shipping") or {}
    return NormalizedOffer(
        id=str(item.get("id") or ""),
        title=str(item.get("title") or "Produto sem título"),
        price=price,
        currency_id=item.get("currency_id"),
        available_quantity=int(item.get("available_quantity") or 0),
        sold_quantity=int(item.get("sold_quantity") or 0),
        condition=item.get("condition"),
        permalink=item.get("permalink"),
        thumbnail=item.get("thumbnail"),
        free_shipping=bool(shipping.get("free_shipping")),
        listing_type_id=item.get("listing_type_id"),
        category_id=item.get("category_id"),
        seller_reputation=_seller_reputation(item),
    )


def _strengths_and_weaknesses(offer: NormalizedOffer, p25: float | None, med: float | None) -> tuple[list[str], list[str]]:
    strengths: list[str] = []
    weaknesses: list[str] = []
    if offer.sold_quantity >= 50:
        strengths.append("Alto volume vendido")
    elif offer.sold_quantity <= 3:
        weaknesses.append("Poucas vendas")
    if offer.free_shipping:
        strengths.append("Frete grátis")
    else:
        weaknesses.append("Sem frete grátis")
    if p25 is not None and offer.price <= p25:
        strengths.append("Preço abaixo do mercado")
    if med is not None and offer.price > med:
        weaknesses.append("Preço acima da mediana")
    if offer.seller_reputation:
        strengths.append("Reputação disponível")
    title_words = len(offer.title.split())
    if title_words >= 6:
        strengths.append("Título descritivo")
    else:
        weaknesses.append("Título pouco específico")
    return strengths[:4], weaknesses[:4]


def _estimated_shipping_cost(suggested_price: float, competitors: list[NormalizedOffer]) -> float:
    free_shipping_ratio = sum(1 for c in competitors if c.free_shipping) / max(len(competitors), 1)
    if free_shipping_ratio >= 0.5:
        return round(max(18.0, min(45.0, suggested_price * 0.06)), 2)
    return 0.0


def _competitiveness_position(suggested_price: float, prices: list[float]) -> str:
    if not prices:
        return "sem base suficiente"
    cheaper_or_equal = sum(1 for p in prices if suggested_price <= p)
    pct = round((cheaper_or_equal / len(prices)) * 100)
    if pct >= 70:
        return f"ficaria entre os {pct}% mais competitivos da amostra"
    if pct >= 40:
        return "ficaria em faixa intermediária competitiva"
    return "ficaria acima da maior parte dos preços analisados"


def _build_suggestion(prices: list[float], competitors: list[NormalizedOffer], cost: float | None) -> dict[str, Any]:
    p25 = _percentile(prices, 0.25)
    med = round(median(prices), 2) if prices else None
    if med is None:
        return {
            "price": None,
            "reasoning": "Não há anúncios suficientes para sugerir preço.",
            "estimated_margin": None,
            "margin_percent": None,
            "competitiveness_position": "sem base suficiente",
        }

    top_by_sales = sorted(competitors, key=lambda x: (x.sold_quantity, -x.price), reverse=True)[:5]
    top_sales_prices = [x.price for x in top_by_sales] or prices
    sales_reference = median(top_sales_prices)
    if p25 is None:
        base_price = med
    else:
        base_price = (float(p25) * 0.55) + (float(min(med, sales_reference)) * 0.45)
    suggested = round(base_price, 2)

    estimated_shipping = _estimated_shipping_cost(suggested, competitors)
    margin_value = None
    margin_percent = None
    reasoning_parts = ["Sugestão baseada na faixa entre p25 e mediana dos anúncios reais encontrados."]

    if cost is not None:
        cost = float(cost)
        min_viable = cost / max(1 - COMMISSION_RATE - TAX_RATE, 0.01)
        if estimated_shipping:
            min_viable = (cost + estimated_shipping) / max(1 - COMMISSION_RATE - TAX_RATE, 0.01)
        if suggested < min_viable:
            suggested = round(max(min_viable, p25 or min_viable), 2)
            reasoning_parts.append("A sugestão foi ajustada para evitar margem líquida negativa com o custo informado.")
        commission = suggested * COMMISSION_RATE
        tax = suggested * TAX_RATE
        margin_value = round(suggested - cost - commission - tax - estimated_shipping, 2)
        margin_percent = round((margin_value / suggested) * 100, 2) if suggested else None
        reasoning_parts.append("Comissão e imposto foram estimados em 14% e 6%. Frete grátis usa heurística conservadora quando relevante.")
    else:
        reasoning_parts.append("Como o custo não foi informado, a margem depende do custo real de aquisição e operação.")

    return {
        "price": suggested,
        "reasoning": " ".join(reasoning_parts),
        "estimated_margin": margin_value,
        "margin_percent": margin_percent,
        "competitiveness_position": _competitiveness_position(suggested, prices),
        "estimated_shipping": estimated_shipping if cost is not None else None,
        "commission_rate": COMMISSION_RATE if cost is not None else None,
        "tax_rate": TAX_RATE if cost is not None else None,
    }


def _build_insights(prices: list[float], competitors: list[NormalizedOffer], suggestion: dict[str, Any], cost: float | None) -> list[str]:
    if not competitors:
        return ["Nenhum anúncio válido encontrado para análise."]
    insights: list[str] = []
    med = round(median(prices), 2)
    p25 = _percentile(prices, 0.25)
    p75 = _percentile(prices, 0.75)
    free_shipping_count = sum(1 for c in competitors if c.free_shipping)
    high_sales = sorted(competitors, key=lambda c: c.sold_quantity, reverse=True)[:3]
    insights.append(f"A mediana do mercado analisado está em R$ {med:.2f}.")
    if p25 is not None and p75 is not None:
        insights.append(f"A faixa central de preços vai aproximadamente de R$ {p25:.2f} a R$ {p75:.2f}.")
    if free_shipping_count:
        insights.append(f"{free_shipping_count} de {len(competitors)} anúncios analisados oferecem frete grátis.")
    if high_sales and high_sales[0].sold_quantity > 0:
        insights.append(f"O anúncio com maior volume na amostra registra {high_sales[0].sold_quantity} vendas informadas.")
    if cost is not None and suggestion.get("estimated_margin") is not None:
        margin = float(suggestion["estimated_margin"])
        if margin < 0:
            insights.append("Com o custo informado, a margem estimada ficaria negativa no preço sugerido.")
        elif suggestion.get("margin_percent") is not None:
            insights.append(f"Margem líquida estimada: {suggestion['margin_percent']:.2f}%.")
    return insights[:6]


def _fetch_public_search(query: str) -> list[dict[str, Any]]:
    url = f"{ML_BASE_URL}/sites/MLB/search"
    params = {"q": query, "limit": MAX_ANALYZED_ITEMS}
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT, headers={"Accept": "application/json"})
    if response.status_code in {429, 500, 502, 503, 504}:
        raise PricingScanError("Mercado Livre indisponível ou limitando requisições. Tente novamente em alguns minutos.")
    response.raise_for_status()
    data = response.json()
    results = data.get("results") or []
    if not isinstance(results, list):
        return []
    return results[:MAX_ANALYZED_ITEMS]


def market_scan(query: str, cost: float | None = None) -> dict[str, Any]:
    sanitized_query = _sanitize_query(query)
    if cost is not None and float(cost) < 0:
        raise PricingScanError("O custo não pode ser negativo.")

    key = _cache_key(sanitized_query, cost)
    cached = _CACHE.get(key)
    now = time.time()
    if cached and now - cached[0] <= CACHE_TTL_SECONDS:
        return {**cached[1], "cache": {"hit": True, "ttl_seconds": CACHE_TTL_SECONDS}}

    log.info("market_scan_started", extra={"event": "market_scan_started", "query_len": len(sanitized_query), "has_cost": cost is not None})
    try:
        raw_items = _fetch_public_search(sanitized_query)
    except PricingScanError:
        log.warning("market_scan_failed", extra={"event": "market_scan_failed", "reason": "controlled_error"})
        raise
    except Exception as exc:  # noqa: BLE001
        log.exception("market_scan_failed", extra={"event": "market_scan_failed"})
        raise PricingScanError(f"Erro ao consultar Mercado Livre: {exc}") from exc

    offers = [offer for item in raw_items if (offer := _normalize_offer(item))]
    prices = sorted([o.price for o in offers])
    if not offers:
        log.info("no_results_found", extra={"event": "no_results_found", "query_len": len(sanitized_query)})

    p25 = _percentile(prices, 0.25)
    p75 = _percentile(prices, 0.75)
    dist = {
        "min": round(min(prices), 2) if prices else None,
        "max": round(max(prices), 2) if prices else None,
        "avg": round(mean(prices), 2) if prices else None,
        "median": round(median(prices), 2) if prices else None,
        "p25": p25,
        "p75": p75,
    }
    ranked = sorted(offers, key=lambda o: (o.sold_quantity, o.free_shipping, -abs(o.price - (dist["median"] or o.price))), reverse=True)[:5]
    top_competitors = []
    for offer in ranked:
        strengths, weaknesses = _strengths_and_weaknesses(offer, p25, dist["median"])
        top_competitors.append({
            "title": offer.title,
            "price": round(offer.price, 2),
            "currency_id": offer.currency_id,
            "sold_quantity": offer.sold_quantity,
            "available_quantity": offer.available_quantity,
            "permalink": offer.permalink,
            "thumbnail": offer.thumbnail,
            "free_shipping": offer.free_shipping,
            "condition": offer.condition,
            "seller_reputation": offer.seller_reputation,
            "listing_type_id": offer.listing_type_id,
            "category_id": offer.category_id,
            "strengths": strengths,
            "weaknesses": weaknesses,
        })

    suggestion = _build_suggestion(prices, offers, None if cost is None else float(cost))
    result = {
        "query": sanitized_query,
        "cost": None if cost is None else round(float(cost), 2),
        "total_found": len(raw_items),
        "analyzed_count": len(offers),
        "price_distribution": dist,
        "top_competitors": top_competitors,
        "suggested_price": suggestion,
        "insights": _build_insights(prices, offers, suggestion, None if cost is None else float(cost)),
        "generated_at": datetime.utcnow().isoformat(),
        "source": "mercadolivre_public_search",
        "cache": {"hit": False, "ttl_seconds": CACHE_TTL_SECONDS},
    }
    _CACHE[key] = (now, result)
    log.info("market_scan_completed", extra={"event": "market_scan_completed", "analyzed_count": len(offers), "has_cost": cost is not None})
    return result
