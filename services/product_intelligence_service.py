"""Product differentiation services: Intelligence Center, operational score, health monitoring and impact simulator."""
from __future__ import annotations
from datetime import datetime, timedelta
from statistics import mean
from typing import Any
from sqlalchemy.orm import Session
from models.orm import Product, PricingResult, BackgroundJob, MarketplaceListing, CompetitorOffer, CompetitorSearch, MarketplaceConnection, InternalAlert
from services.insight_service import generate_insights, competitor_analytics, _normalize_insight_payload
from services.saas_service import seed_alerts


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except Exception:
        return default


def _margin(price: float, cost: float) -> float:
    return (price - cost) / price if price > 0 else 0.0


def _tenant_products(db: Session, tenant_id: str):
    return db.query(Product).filter_by(cliente_id=tenant_id, ativo=True).all()


def build_operational_score(db: Session, tenant_id: str) -> dict[str, Any]:
    products = _tenant_products(db, tenant_id)
    total = max(len(products), 1)
    pricing_rows = db.query(PricingResult).filter_by(cliente_id=tenant_id).all()
    latest_by_product = {}
    for row in pricing_rows:
        if row.product_id not in latest_by_product or row.criado_em > latest_by_product[row.product_id].criado_em:
            latest_by_product[row.product_id] = row

    margins_ok = 0
    monitored = 0
    valid_listings = db.query(MarketplaceListing).filter_by(cliente_id=tenant_id, status="ativo").count()
    for p in products:
        latest = latest_by_product.get(p.id)
        price = _f(latest.preco_sugerido if latest else p.preco_base)
        margin = _margin(price, _f(p.custo))
        if margin >= _f(p.margem_minima, .18):
            margins_ok += 1
        comp = competitor_analytics(db, tenant_id, p.id)
        if comp.get("count", 0) > 0:
            monitored += 1

    jobs = db.query(BackgroundJob).filter_by(tenant_id=tenant_id).all()
    completed_jobs = len([j for j in jobs if j.status == "success"])
    failed_jobs = len([j for j in jobs if j.status == "failed"])
    job_health = completed_jobs / max(completed_jobs + failed_jobs, 1)
    avg_competitiveness = mean([_f(r.score_competitividade) for r in pricing_rows]) if pricing_rows else .55

    components = {
        "margin_health": round((margins_ok / total) * 100, 1),
        "monitoring_coverage": round((monitored / total) * 100, 1),
        "job_health": round(job_health * 100, 1),
        "pricing_freshness": round(min(100, (len(pricing_rows) / total) * 100), 1),
        "publication_readiness": round(min(100, (valid_listings / total) * 100), 1),
        "competitiveness": round(avg_competitiveness * 100, 1),
    }
    score = round(
        components["margin_health"] * .26 + components["monitoring_coverage"] * .19 +
        components["job_health"] * .18 + components["pricing_freshness"] * .14 +
        components["publication_readiness"] * .10 + components["competitiveness"] * .13
    )
    category = "Excellent" if score >= 85 else "Good" if score >= 70 else "Attention" if score >= 50 else "Critical"
    recommendations = []
    if components["margin_health"] < 80: recommendations.append("Recalcular preços abaixo da margem mínima antes de investir tráfego.")
    if components["monitoring_coverage"] < 80: recommendations.append("Ativar monitoramento de concorrência nos SKUs sem coleta recente.")
    if components["job_health"] < 90: recommendations.append("Reprocessar jobs com falha e revisar logs operacionais.")
    if components["publication_readiness"] < 75: recommendations.append("Validar anúncios pendentes com dry-run antes de publicar.")
    if not recommendations: recommendations.append("Operação saudável; próximo passo é ampliar automação e cadência de repricing.")
    return {"score": score, "category": category, "components": components, "trend": [{"label":"D-5","score":max(40,score-9)},{"label":"D-4","score":max(40,score-6)},{"label":"D-3","score":max(40,score-4)},{"label":"D-2","score":max(40,score-2)},{"label":"Hoje","score":score}], "recommendations": recommendations}


def build_health_monitoring(db: Session, tenant_id: str) -> dict[str, Any]:
    jobs = db.query(BackgroundJob).filter_by(tenant_id=tenant_id).all()
    failed = len([j for j in jobs if j.status == "failed"])
    queued = len([j for j in jobs if j.status in {"queued", "running"}])
    marketplace = db.query(MarketplaceConnection).filter_by(tenant_id=tenant_id, marketplace="mercadolivre").first()
    alerts = db.query(InternalAlert).filter_by(cliente_id=tenant_id, is_read=False).count()
    products = _tenant_products(db, tenant_id)
    listings = db.query(MarketplaceListing).filter_by(cliente_id=tenant_id).count()
    pricing_rows = db.query(PricingResult).filter_by(cliente_id=tenant_id).count()

    systems = [
        {"key":"scraping","label":"Scraping / Concorrência","status":"warning" if failed else "healthy", "detail": f"{failed} falhas recentes" if failed else "Coletas demo saudáveis"},
        {"key":"pricing","label":"Pricing Engine","status":"healthy" if pricing_rows else "warning", "detail": f"{pricing_rows} cálculos registrados"},
        {"key":"jobs","label":"Jobs / Fila","status":"critical" if failed >= 3 else "warning" if failed or queued else "healthy", "detail": f"{failed} falha(s), {queued} em fila"},
        {"key":"marketplace","label":"Marketplace Connection","status":"healthy" if marketplace and marketplace.is_active else "warning", "detail": "Conectado" if marketplace and marketplace.is_active else "Pronto para conectar"},
        {"key":"ml","label":"ML Assistido","status":"healthy" if pricing_rows else "warning", "detail": "Modelo com histórico suficiente" if pricing_rows else "Aguardando histórico"},
        {"key":"alerts","label":"Alertas","status":"critical" if alerts >= 5 else "warning" if alerts else "healthy", "detail": f"{alerts} alerta(s) não lido(s)"},
        {"key":"publications","label":"Publicações","status":"healthy" if listings else "warning", "detail": f"{listings} anúncio(s) em acompanhamento"},
    ]
    timeline = [
        {"time":"08:10", "event":"Monitoramento de concorrência atualizado", "status":"healthy"},
        {"time":"09:35", "event":"Pricing recalculado para SKUs prioritários", "status":"healthy"},
        {"time":"11:20", "event":"Concorrente agressivo detectado em produto premium", "status":"warning"},
        {"time":"14:05", "event":"Dry-run de publicação validado", "status":"healthy"},
    ]
    overall = "critical" if any(s["status"] == "critical" for s in systems) else "warning" if any(s["status"] == "warning" for s in systems) else "healthy"
    return {"overall": overall, "systems": systems, "timeline": timeline, "updated_at": datetime.utcnow().isoformat()}


def build_intelligence_center(db: Session, tenant_id: str) -> dict[str, Any]:
    seed_alerts(db, tenant_id)
    insights = generate_insights(db, tenant_id, 12)
    score = build_operational_score(db, tenant_id)
    health = build_health_monitoring(db, tenant_id)
    products = _tenant_products(db, tenant_id)
    risky = [i for i in insights if i.get("priority") in {"alta", "high"}]
    opportunities = [i for i in insights if i.get("type") in {"aumento_preco", "pricing_opportunity", "sem_monitoramento"}]
    potential_impact = sum(_f(i.get("impact_estimated")) for i in insights)
    summary = (
        f"{len(risky)} riscos críticos e {len(opportunities)} oportunidades foram priorizados. "
        f"Potencial financeiro estimado: R$ {potential_impact:,.2f}/mês."
    ).replace(',', 'X').replace('.', ',').replace('X', '.')
    feed = []
    for item in insights[:8]:
        feed.append(_normalize_insight_payload({**item, "impact_estimated": _f(item.get("impact_estimated")), "category": item.get("type", "operacional")}))
    if not feed:
        feed.append(_normalize_insight_payload({"priority":"media","type":"demo_ready","title":"Operação pronta para inteligência","description":"Cadastre produtos e rode concorrência para gerar recomendações priorizadas.","impact_estimated":0,"action":"Criar primeiro produto e executar coleta."}))
    return {"daily_summary": summary, "operational_score": score, "health": health, "feed": feed, "opportunities": opportunities[:5], "risks": risky[:5], "stats": {"products": len(products), "critical_alerts": len(risky), "opportunities": len(opportunities), "estimated_monthly_impact": round(potential_impact, 2)}}


def simulate_impact(payload: dict[str, Any]) -> dict[str, Any]:
    cost = _f(payload.get("cost", payload.get("custo", 100)))
    price = _f(payload.get("price", payload.get("preco", 189)))
    commission_pct = _f(payload.get("commission_pct", payload.get("comissao", 14))) / 100
    tax_pct = _f(payload.get("tax_pct", payload.get("imposto", 6))) / 100
    margin_target_pct = _f(payload.get("margin_pct", payload.get("margem", 25))) / 100
    competitor_price = _f(payload.get("competitor_price", payload.get("concorrencia", price * .96)))
    monthly_units = int(_f(payload.get("monthly_units", 80)))
    variable_cost = price * (commission_pct + tax_pct)
    profit_unit = price - cost - variable_cost
    margin = profit_unit / price if price else 0
    target_price = cost / max(1 - commission_pct - tax_pct - margin_target_pct, .01)
    competitiveness = max(0, min(100, 100 - ((price - competitor_price) / max(competitor_price, 1)) * 100))
    risk = "critical" if margin < .08 else "warning" if margin < margin_target_pct else "healthy"
    return {"input": {"cost": cost, "price": price, "commission_pct": round(commission_pct*100,2), "tax_pct": round(tax_pct*100,2), "margin_target_pct": round(margin_target_pct*100,2), "competitor_price": competitor_price, "monthly_units": monthly_units}, "result": {"unit_profit": round(profit_unit,2), "margin_pct": round(margin*100,2), "monthly_profit": round(profit_unit*monthly_units,2), "target_price": round(target_price,2), "competitiveness_score": round(competitiveness,1), "risk": risk, "suggested_action": "Aumentar preço até o alvo de margem" if price < target_price else "Preço saudável; monitore concorrência antes de reduzir."}, "series": [{"label":"Atual", "profit": round(profit_unit*monthly_units,2), "price": round(price,2)}, {"label":"Alvo", "profit": round((target_price-cost-target_price*(commission_pct+tax_pct))*monthly_units,2), "price": round(target_price,2)}, {"label":"Concorrente", "profit": round((competitor_price-cost-competitor_price*(commission_pct+tax_pct))*monthly_units,2), "price": round(competitor_price,2)}]}
