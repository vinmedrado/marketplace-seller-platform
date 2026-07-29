"""PATCH 8/10 — Buy Box Probability Score interno MarketPlace Seller Platform.

Heurística transparente: não usa ML treinado, não promete Buy Box e não representa
métrica oficial Mercado Livre. O objetivo é transformar sinais operacionais em
uma probabilidade interna estimada e comparável por cenário de preço.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value: Any) -> bool:
    return bool(value) if value is not None else False


def _clamp(v: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, v))


def _status_factor(status: str | None) -> tuple[float, str, str]:
    s = (status or "").lower()
    if s == "active":
        return 1.0, "positive", "Anúncio ativo"
    if s == "paused":
        return 0.15, "negative", "Anúncio pausado reduz chance operacional"
    return 0.55, "missing", "Status do anúncio pouco conclusivo"


def _reputation_factor(health: dict[str, Any] | None) -> tuple[float, str, str]:
    if not health:
        return 0.70, "missing", "Saúde da conta indisponível; confiança reduzida"
    score = _float(health.get("score"), 70.0)
    if score >= 90:
        return 1.0, "positive", "Conta com score interno excelente"
    if score >= 75:
        return 0.88, "positive", "Conta com score interno bom"
    if score >= 60:
        return 0.68, "warning", "Conta em atenção no score interno"
    if score >= 40:
        return 0.45, "negative", "Conta em faixa de risco operacional"
    return 0.25, "negative", "Conta crítica no score interno"


def _health_factor(product: dict[str, Any]) -> tuple[float, str, str]:
    h = product.get("health")
    if h is None:
        return 0.68, "missing", "Health do anúncio indisponível"
    value = _float(h)
    if value > 1:
        value = value / 100
    if value >= 0.85:
        return 1.0, "positive", "Health do anúncio forte"
    if value >= 0.60:
        return 0.78, "warning", "Health do anúncio aceitável, mas pode melhorar"
    return 0.42, "negative", "Health do anúncio baixo"


def _listing_factor(listing_type: str | None) -> tuple[float, str, str]:
    lt = (listing_type or "").lower()
    if "gold_pro" in lt or "premium" in lt:
        return 0.92, "positive", "Tipo de anúncio com boa exposição"
    if "gold_special" in lt or "gold" in lt:
        return 0.82, "positive", "Tipo de anúncio competitivo"
    if not lt:
        return 0.68, "missing", "Tipo de anúncio não informado"
    return 0.58, "warning", "Tipo de anúncio pode limitar competitividade"


def _price_factor(price: float, p25: float | None, median: float | None) -> tuple[float, str, str]:
    if not median or median <= 0:
        return 0.65, "missing", "Referência de mercado insuficiente"
    rel_med = price / median
    if p25 and p25 > 0:
        rel_p25 = price / p25
    else:
        rel_p25 = None
    if rel_p25 is not None and rel_p25 <= 1.03:
        return 1.0, "positive", "Preço próximo ao primeiro quartil do mercado"
    if rel_med <= 0.98:
        return 0.90, "positive", "Preço abaixo da mediana do mercado"
    if rel_med <= 1.06:
        return 0.74, "warning", "Preço próximo da mediana"
    if rel_med <= 1.15:
        return 0.50, "negative", "Preço acima da mediana"
    return 0.32, "negative", "Preço muito acima da mediana"


def _stock_factor(qty: int) -> tuple[float, str, str]:
    if qty <= 0:
        return 0.05, "negative", "Sem estoque disponível"
    if qty <= 3:
        return 0.55, "warning", "Estoque baixo"
    return 0.88, "positive", "Estoque disponível"


def _sales_factor(sold: int) -> tuple[float, str, str]:
    if sold >= 100:
        return 1.0, "positive", "Histórico de vendas forte"
    if sold >= 20:
        return 0.82, "positive", "Histórico de vendas positivo"
    if sold > 0:
        return 0.65, "warning", "Poucas vendas acumuladas"
    return 0.50, "warning", "Sem vendas registradas no payload sincronizado"


def _estimate_probability(product: dict[str, Any], account_health: dict[str, Any] | None, market_reference: dict[str, Any] | None, price: float) -> tuple[float, list[dict[str, Any]], int]:
    p25 = _float((market_reference or {}).get("p25"), 0) or None
    med = _float((market_reference or {}).get("median"), 0) or None
    factors_raw = [
        ("price", 0.30, *_price_factor(price, p25, med)),
        ("account_health", 0.20, *_reputation_factor(account_health)),
        ("listing_health", 0.14, *_health_factor(product)),
        ("free_shipping", 0.10, (0.92 if _bool(product.get("free_shipping")) else 0.56), ("positive" if _bool(product.get("free_shipping")) else "warning"), ("Frete grátis ativo" if _bool(product.get("free_shipping")) else "Sem frete grátis informado")),
        ("stock", 0.10, *_stock_factor(int(_float(product.get("available_quantity") or product.get("estoque"), 0)))),
        ("status", 0.08, *_status_factor(product.get("status"))),
        ("sales_history", 0.05, *_sales_factor(int(_float(product.get("sold_quantity"), 0)))),
        ("listing_type", 0.03, *_listing_factor(product.get("listing_type_id"))),
    ]
    score = 0.0
    factors: list[dict[str, Any]] = []
    missing = 0
    for name, weight, factor, polarity, reason in factors_raw:
        score += weight * factor * 100
        if polarity == "missing":
            missing += 1
        factors.append({"name": name, "weight": weight, "score": round(factor * 100, 1), "polarity": polarity, "reason": reason})
    confidence = int(_clamp(88 - missing * 10 + (8 if med else -12), 35, 92))
    return round(_clamp(score), 1), factors, confidence


def _scenario_recommendation(prob: float, current_prob: float, variation: float) -> str:
    delta = prob - current_prob
    if variation < 0 and delta >= 8:
        return "Ajuste pode elevar bastante o score interno; avaliar margem antes de aplicar."
    if variation < 0 and delta >= 3:
        return "Ajuste melhora o score interno, mas valide margem líquida."
    if variation > 0 and delta < -4:
        return "Aumento pode reduzir competitividade de Buy Box; aplicar com cautela."
    return "Cenário neutro; monitorar concorrência e margem."


def score_buybox(product: dict[str, Any], account_health: dict[str, Any] | None = None, market_reference: dict[str, Any] | None = None, cost: float | None = None) -> dict[str, Any]:
    current_price = _float(product.get("price") or product.get("preco_base"), 0)
    current_prob, factors, confidence = _estimate_probability(product, account_health, market_reference, current_price)
    scenarios = []
    for variation in [0, -0.03, -0.05, -0.08, 0.03]:
        price = round(current_price * (1 + variation), 2)
        prob, _, _ = _estimate_probability(product, account_health, market_reference, price)
        margin_impact = None
        if cost is not None and cost > 0:
            current_margin = current_price - cost
            scenario_margin = price - cost
            margin_impact = round(scenario_margin - current_margin, 2)
        scenarios.append({
            "variation_percent": round(variation * 100, 2),
            "price": price,
            "estimated_probability": prob,
            "estimated_margin_impact": margin_impact if margin_impact is not None else round(variation * 100, 2),
            "margin_note": None if margin_impact is not None else "Impacto exibido em percentual porque custo do produto não está disponível.",
            "recommendation": _scenario_recommendation(prob, current_prob, variation),
        })
    best = max(scenarios, key=lambda s: (s["estimated_probability"], -abs(s["variation_percent"])))
    negatives = [f for f in factors if f["polarity"] == "negative"]
    positives = [f for f in factors if f["polarity"] == "positive"]
    if current_prob < 45:
        rec = "Baixa probabilidade interna estimada. Priorize preço, estoque, frete e health antes de aumentar investimento."
    elif best["variation_percent"] < 0 and best["estimated_probability"] - current_prob >= 4:
        rec = f"Reduzir {abs(best['variation_percent'])}% pode melhorar o score interno, desde que a margem continue saudável."
    elif current_prob >= 75:
        rec = "Score interno forte. Evite cortes agressivos de preço e monitore concorrência."
    else:
        rec = "Score intermediário. Avalie pequenos ajustes e melhore sinais operacionais do anúncio."
    return {
        "probability": current_prob,
        "confidence": confidence,
        "factors": factors,
        "positive_factors": positives,
        "negative_factors": negatives,
        "recommendation": rec,
        "simulated_prices": scenarios,
        "best_scenario": best,
        "disclaimer": "Score interno MarketPlace Seller Platform baseado em sinais operacionais e mercado. Não é métrica oficial do Mercado Livre.",
    }
