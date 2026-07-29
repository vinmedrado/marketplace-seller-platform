"""services/insight_service.py — inteligência comercial para tornar a demo vendável."""
from __future__ import annotations
from statistics import median, pstdev
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.orm import Product, PricingResult, CompetitorOffer, CompetitorSearch, PublishLog, BackgroundJob, Organization


def _f(v, default=0.0):
    try:
        return float(v or default)
    except Exception:
        return default


def competitor_analytics(db: Session, cliente_id: str, product_id: str | None = None) -> dict:
    q = db.query(CompetitorOffer).join(CompetitorSearch, CompetitorOffer.search_id == CompetitorSearch.id).filter(CompetitorOffer.cliente_id == cliente_id)
    if product_id:
        q = q.filter(CompetitorSearch.product_id == product_id)
    offers = q.order_by(CompetitorOffer.preco.asc()).limit(300).all()
    prices = [_f(o.preco) for o in offers if _f(o.preco) > 0]
    sellers = {}
    for o in offers:
        seller = o.vendedor or "Seller não identificado"
        sellers.setdefault(seller, {"seller": seller, "offers": 0, "min_price": None, "avg_price": 0, "free_shipping": 0, "sales": 0})
        item = sellers[seller]
        price = _f(o.preco)
        item["offers"] += 1
        item["sales"] += int(o.vendas or 0)
        item["free_shipping"] += 1 if o.frete_gratis else 0
        item["min_price"] = price if item["min_price"] is None else min(item["min_price"], price)
        item["avg_price"] += price
    ranking = []
    for item in sellers.values():
        item["avg_price"] = round(item["avg_price"] / max(item["offers"], 1), 2)
        item["aggressiveness_score"] = round((item["offers"] * 0.25) + (item["sales"] / 400) + (item["free_shipping"] * 0.35), 2)
        ranking.append(item)
    ranking.sort(key=lambda x: (x["aggressiveness_score"], -(x["min_price"] or 0)), reverse=True)
    return {
        "count": len(offers),
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
        "median_price": round(median(prices), 2) if prices else None,
        "avg_price": round(sum(prices) / len(prices), 2) if prices else None,
        "price_dispersion": round(pstdev(prices), 2) if len(prices) > 1 else 0,
        "aggressive_alert": bool(prices and min(prices) < (sum(prices) / len(prices)) * 0.90),
        "last_collection_status": "monitorado" if offers else "sem_coleta",
        "ranking": ranking[:10],
    }


def pricing_scenarios(db: Session, cliente_id: str, product_id: str) -> dict:
    p = db.query(Product).filter_by(id=product_id, cliente_id=cliente_id).first()
    if not p:
        raise ValueError("Produto não encontrado")
    comp = competitor_analytics(db, cliente_id, product_id)
    cost = _f(p.custo)
    base = _f(p.preco_base) or cost * 2
    min_margin = _f(p.margem_minima, 0.18)
    comp_min = comp.get("min_price") or base
    comp_med = comp.get("median_price") or base

    def scenario(name, price, note):
        gross_profit = price - cost
        margin = gross_profit / price if price > 0 else 0
        position = "abaixo da mediana" if price < comp_med else "acima da mediana" if price > comp_med else "na mediana"
        risk = "margem negativa" if margin < 0 else "margem baixa" if margin < min_margin else "saudável"
        return {"name": name, "price": round(price, 2), "margin_pct": round(margin * 100, 2), "estimated_profit": round(gross_profit, 2), "competitive_position": position, "risk": risk, "recommendation": note}

    protected = max(cost / max(1 - min_margin, 0.01), base * 0.97)
    scenarios = [
        scenario("conservador", max(protected, comp_med * 1.04), "Prioriza margem e evita guerra de preço."),
        scenario("competitivo", max(protected, comp_med * 0.99), "Fica próximo da mediana sem sacrificar margem mínima."),
        scenario("agressivo", max(protected, comp_min * 0.995), "Pressiona concorrentes mantendo piso de margem."),
        scenario("margem protegida", protected, "Preço mínimo saudável para não vender no prejuízo."),
    ]
    best = max(scenarios, key=lambda x: (x["margin_pct"] >= min_margin * 100, x["estimated_profit"]))
    return {"product_id": product_id, "current_base_price": base, "competitor": comp, "scenarios": scenarios, "recommended": best}


def generate_insights(db: Session, cliente_id: str, limit: int = 20) -> list[dict]:
    insights = []
    products = db.query(Product).filter_by(cliente_id=cliente_id, ativo=True).all()
    for p in products:
        latest = db.query(PricingResult).filter_by(cliente_id=cliente_id, product_id=p.id).order_by(PricingResult.criado_em.desc()).first()
        comp = competitor_analytics(db, cliente_id, p.id)
        price = _f(latest.preco_sugerido if latest else p.preco_base)
        cost = _f(p.custo)
        margin = ((price - cost) / price) if price > 0 else 0
        min_margin = _f(p.margem_minima, 0.18)
        if p.estoque <= (p.estoque_minimo or 5):
            insights.append(_insight("alta", "estoque_baixo", p, "Estoque baixo pode interromper vendas.", 0, "Repor estoque antes de ampliar tráfego ou publicar novos anúncios."))
        if margin < min_margin:
            impact = max(0, (cost / max(1 - min_margin, 0.01) - price) * max(p.estoque or 1, 1))
            insights.append(_insight("alta", "margem_baixa", p, "Produto abaixo da margem mínima configurada.", impact, "Recalcular preço em cenário margem protegida."))
        if not comp.get("count"):
            insights.append(_insight("media", "sem_monitoramento", p, "Produto sem concorrência monitorada.", 0, "Rodar coleta de concorrência para tomar decisão baseada em mercado."))
        elif comp.get("aggressive_alert"):
            insights.append(_insight("alta", "concorrencia_agressiva", p, "Concorrente agressivo abaixo da faixa normal de preço.", max(price * 0.08, 0), "Avaliar cenário competitivo sem comprometer margem."))
        elif comp.get("median_price") and price < comp["median_price"] * 0.93 and margin > min_margin:
            insights.append(_insight("media", "aumento_preco", p, "Há espaço para aumento de preço sem perder competitividade.", (comp["median_price"] - price) * max(p.estoque or 1, 1), "Simular cenário conservador e capturar margem adicional."))
    failed_jobs = db.query(BackgroundJob).filter_by(cliente_id=cliente_id, status="failed").count()
    if failed_jobs:
        insights.append(_normalize_insight_payload({"priority":"alta","type":"job_falha","title":"Jobs com falha operacional","description":f"{failed_jobs} job(s) falharam e exigem revisão.","impact_estimated":0,"action":"Abrir tela de jobs e analisar logs expansíveis.","product_id":None}))
    order = {"alta": 0, "media": 1, "baixa": 2}
    insights.sort(key=lambda x: (order.get(x["priority"], 9), -x.get("impact_estimated", 0)))
    return insights[:limit]


def dashboard_market_ready(db: Session, cliente_id: str) -> dict:
    products = db.query(Product).filter_by(cliente_id=cliente_id, ativo=True).all()
    insights = generate_insights(db, cliente_id, 6)
    pricing_rows = db.query(PricingResult).filter_by(cliente_id=cliente_id).all()
    avg_margin = sum(_f(r.margem_real_pct) for r in pricing_rows) / max(len(pricing_rows), 1)
    dry_runs = db.query(PublishLog).filter_by(cliente_id=cliente_id).count()
    jobs_count = db.query(BackgroundJob).filter_by(cliente_id=cliente_id).count()
    risk_margin = 0
    below_ideal = 0
    no_comp = 0
    increase = 0
    potential_revenue = 0
    protected_margin_value = 0
    for p in products:
        latest = db.query(PricingResult).filter_by(cliente_id=cliente_id, product_id=p.id).order_by(PricingResult.criado_em.desc()).first()
        price = _f(latest.preco_sugerido if latest else p.preco_base)
        cost = _f(p.custo)
        potential_revenue += price * max(int(p.estoque or 0), 1)
        margin = ((price - cost) / price) if price else 0
        if margin < _f(p.margem_minima, 0.18):
            risk_margin += 1
            protected_margin_value += max(0, (cost / max(1 - _f(p.margem_minima, 0.18), 0.01)) - price)
        comp = competitor_analytics(db, cliente_id, p.id)
        if not comp.get("count"):
            no_comp += 1
        if comp.get("median_price") and price < comp["median_price"] * .95:
            increase += 1
        if latest and _f(latest.score_competitividade) < .45:
            below_ideal += 1
    return {"commercial_kpis": {"estimated_potential_revenue": round(potential_revenue, 2), "protected_margin_value": round(protected_margin_value, 2), "avg_protected_margin_pct": round(avg_margin * 100, 2), "products_at_margin_risk": risk_margin, "products_below_ideal_price": below_ideal, "products_without_competition": no_comp, "price_increase_opportunities": increase, "strategic_reduction_opportunities": max(0, below_ideal), "jobs_executed": jobs_count, "dry_run_publications": dry_runs, "critical_alerts": len([i for i in insights if i["priority"] == "alta"])}, "commercial_insights": insights}


def _insight(priority, type_, p, description, impact, action):
    return _normalize_insight_payload({"priority": priority, "type": type_, "title": f"{p.sku} · {p.titulo}", "description": description, "impact_estimated": round(float(impact or 0), 2), "action": action, "product_id": p.id})


def publish_preview(db: Session, cliente_id: str, product_id: str) -> dict:
    p = db.query(Product).filter_by(id=product_id, cliente_id=cliente_id).first()
    if not p:
        raise ValueError("Produto não encontrado")
    scenarios = pricing_scenarios(db, cliente_id, product_id)
    price = scenarios["recommended"]["price"]
    checklist = [
        {"label": "Título com tamanho comercial", "ok": len(p.titulo or "") >= 20, "risk": "título muito curto"},
        {"label": "Preço preserva margem", "ok": scenarios["recommended"]["margin_pct"] >= _f(p.margem_minima, .18) * 100, "risk": "preço abaixo da margem"},
        {"label": "Estoque suficiente", "ok": (p.estoque or 0) > (p.estoque_minimo or 5), "risk": "estoque baixo"},
        {"label": "GTIN informado", "ok": bool(p.gtin), "risk": "sem GTIN"},
        {"label": "Categoria definida", "ok": bool(p.categoria_id or p.categoria_nome), "risk": "categoria não definida"},
    ]
    payload = {"title": p.titulo_otimizado or p.titulo, "category_id": p.categoria_id, "price": price, "available_quantity": p.estoque, "seller_custom_field": p.sku, "condition": "new", "dry_run": True}
    return {"product_id": product_id, "checklist": checklist, "risks": [x["risk"] for x in checklist if not x["ok"]], "recommendations": ["Corrigir itens críticos antes de publicar em produção."] if any(not x["ok"] for x in checklist) else ["Anúncio pronto para simulação segura."], "preview": {"title": payload["title"], "price": price, "stock": p.estoque, "category": p.categoria_nome}, "technical_payload": payload, "status": "ready_with_warnings" if any(not x["ok"] for x in checklist) else "ready"}


def get_settings(db: Session, user) -> dict:
    org = db.query(Organization).filter_by(id=user.organization_id).first()
    defaults = {"company_profile": {"name": org.nome if org else "Seller Demo Premium", "market": "marketplace", "segment": "operação de sellers"}, "margin_rules": {"minimum_margin_pct": 18, "target_margin_pct": 28}, "default_commission_pct": 14, "default_tax_pct": 6, "mode": "demo", "marketplace_credentials": {"mercadolivre": "not_configured"}, "alert_preferences": {"margin_risk": True, "job_failure": True, "aggressive_competitor": True}, "pricing_policy": "proteger margem antes de competir por preço", "email_verification_enabled": False}
    saved = org.settings if org and org.settings else {}
    return {**defaults, **saved}


def save_settings(db: Session, user, payload: dict) -> dict:
    org = db.query(Organization).filter_by(id=user.organization_id).first()
    if not org:
        raise ValueError("Organização não encontrada")
    current = org.settings or {}
    current.update(payload or {})
    org.settings = current
    db.commit()
    return get_settings(db, user)


def _normalize_insight_payload(item: dict) -> dict:
    """Mantém contrato novo e compatibilidade com telas antigas."""
    impact = item.get("impact_estimated", item.get("impact_estimate", 0))
    action = item.get("action", item.get("recommended_action", "Revisar oportunidade."))
    item["impact_estimated"] = impact
    item["impact_estimate"] = impact
    item["action"] = action
    item["recommended_action"] = action
    return item
