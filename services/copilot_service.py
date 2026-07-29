"""Operational Intelligence layer: AI Operations Copilot, timeline, recommendations and market radar.

The current MVP uses deterministic heuristics over tenant data. This keeps the demo safe,
repeatable and production-friendly while presenting the UX of an AI operations platform.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from statistics import mean
from typing import Any
from sqlalchemy.orm import Session
from models.orm import Product, PricingResult, BackgroundJob, InternalAlert, CompetitorOffer, CompetitorSearch, MarketplaceConnection, MarketplaceListing
from services.insight_service import generate_insights, competitor_analytics, _normalize_insight_payload
from services.product_intelligence_service import build_operational_score, build_health_monitoring, simulate_impact


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except Exception:
        return default


def _money(value: float) -> str:
    return (f"R$ {value:,.2f}").replace(',', 'X').replace('.', ',').replace('X', '.')


def _products(db: Session, tenant_id: str):
    return db.query(Product).filter_by(cliente_id=tenant_id, ativo=True).all()


def _latest_pricing(db: Session, tenant_id: str, product_id: str):
    return db.query(PricingResult).filter_by(cliente_id=tenant_id, product_id=product_id).order_by(PricingResult.criado_em.desc()).first()


def build_smart_alerts(db: Session, tenant_id: str) -> dict[str, Any]:
    raw = generate_insights(db, tenant_id, 40)
    grouped: dict[str, dict[str, Any]] = {}
    for item in raw:
        item = _normalize_insight_payload(item)
        category = item.get('type', 'operational')
        priority = item.get('priority', 'media')
        impact = _f(item.get('impact_estimated'))
        group = grouped.setdefault(category, {
            'category': category,
            'priority': priority,
            'count': 0,
            'impact_estimated': 0.0,
            'title': _category_title(category),
            'context': [],
            'recommended_action': _category_action(category),
        })
        group['count'] += 1
        group['impact_estimated'] += impact
        if len(group['context']) < 3:
            group['context'].append(item.get('title'))
        if priority in {'alta', 'high'}:
            group['priority'] = 'high'
    items = sorted(grouped.values(), key=lambda x: ({'high': 0, 'alta': 0, 'medium': 1, 'media': 1, 'low': 2, 'baixa': 2}.get(x['priority'], 9), -x['impact_estimated']))
    for item in items:
        item['impact_estimated'] = round(item['impact_estimated'], 2)
        item['summary'] = f"{item['count']} ocorrência(s) em {item['category']} · impacto potencial {_money(item['impact_estimated'])}/mês."
    return {'total': len(items), 'critical': len([i for i in items if i['priority'] in {'high', 'alta'}]), 'items': items}


def build_recommended_actions(db: Session, tenant_id: str) -> dict[str, Any]:
    actions = []
    for item in generate_insights(db, tenant_id, 25):
        item = _normalize_insight_payload(item)
        pr = 'HIGH' if item.get('priority') in {'alta', 'high'} else 'MEDIUM' if item.get('priority') in {'media', 'medium'} else 'LOW'
        actions.append({
            'id': f"rec-{len(actions)+1}",
            'priority': pr,
            'category': item.get('type', 'operational'),
            'title': item.get('title', 'Recomendação operacional'),
            'suggested_action': item.get('recommended_action'),
            'impact_estimated': round(_f(item.get('impact_estimated')), 2),
            'justification': item.get('description', 'Ação gerada a partir do contexto operacional do tenant.'),
            'product_id': item.get('product_id'),
            'cta': 'Simular impacto' if item.get('type') in {'margem_baixa', 'aumento_preco', 'concorrencia_agressiva'} else 'Revisar operação',
        })
    if not actions:
        actions.append({'id': 'rec-demo', 'priority': 'LOW', 'category': 'demo', 'title': 'Ativar primeira rotina de inteligência', 'suggested_action': 'Rode scraping e pricing para liberar recomendações automáticas.', 'impact_estimated': 0, 'justification': 'A operação ainda não possui histórico suficiente.', 'product_id': None, 'cta': 'Criar rotina'})
    return {'items': actions[:12], 'estimated_total_impact': round(sum(_f(a['impact_estimated']) for a in actions), 2)}


def build_operational_timeline(db: Session, tenant_id: str) -> dict[str, Any]:
    health = build_health_monitoring(db, tenant_id)
    alerts = build_smart_alerts(db, tenant_id)['items'][:4]
    jobs = db.query(BackgroundJob).filter_by(tenant_id=tenant_id).order_by(BackgroundJob.created_at.desc()).limit(5).all()
    base = datetime.utcnow().replace(second=0, microsecond=0)
    events = []
    for idx, item in enumerate(alerts):
        events.append({
            'time': (base - timedelta(minutes=8 * (idx + 1))).strftime('%H:%M'),
            'type': 'smart_alert',
            'severity': 'critical' if item['priority'] in {'high', 'alta'} else 'warning',
            'title': item['title'],
            'description': item['summary'],
            'impact_estimated': item['impact_estimated'],
        })
    for idx, job in enumerate(jobs):
        events.append({
            'time': (job.created_at or base - timedelta(minutes=idx*11)).strftime('%H:%M'),
            'type': 'job',
            'severity': 'critical' if job.status == 'failed' else 'healthy' if job.status == 'success' else 'warning',
            'title': f"Job {job.job_type} · {job.status}",
            'description': job.progress_label or 'Evento operacional registrado pela plataforma.',
            'impact_estimated': 0,
        })
    for item in health.get('timeline', []):
        events.append({'time': item.get('time'), 'type': 'system', 'severity': item.get('status'), 'title': item.get('event'), 'description': 'Monitoramento operacional automático.', 'impact_estimated': 0})
    events = sorted(events, key=lambda x: str(x.get('time') or ''), reverse=True)[:14]
    return {'items': events, 'updated_at': datetime.utcnow().isoformat(), 'narrative': 'Timeline operacional viva: concorrência, pricing, alertas, jobs e recomendações em sequência executiva.'}


def build_maturity_score(db: Session, tenant_id: str) -> dict[str, Any]:
    score = build_operational_score(db, tenant_id)
    health = build_health_monitoring(db, tenant_id)
    alerts = build_smart_alerts(db, tenant_id)
    components = dict(score.get('components', {}))
    components['automation'] = round(min(100, (db.query(BackgroundJob).filter_by(tenant_id=tenant_id).count() / max(len(_products(db, tenant_id)), 1)) * 25), 1)
    components['critical_alert_control'] = round(max(0, 100 - alerts['critical'] * 18), 1)
    final_score = round(mean([_f(v) for v in components.values()])) if components else score.get('score', 0)
    category = 'Excellent' if final_score >= 85 else 'Good' if final_score >= 70 else 'Attention' if final_score >= 50 else 'Critical'
    benchmark = [{'label': 'Sellers iniciais', 'value': 54}, {'label': 'Operações maduras', 'value': 76}, {'label': 'Sua operação', 'value': final_score}, {'label': 'Elite operacional', 'value': 91}]
    return {'score': final_score, 'category': category, 'components': components, 'benchmark': benchmark, 'trend': score.get('trend', []), 'recommendations': score.get('recommendations', []) + ['Reduzir alertas críticos aumenta maturidade operacional rapidamente.'], 'health_status': health.get('overall')}


def build_market_radar(db: Session, tenant_id: str) -> dict[str, Any]:
    categories: dict[str, dict[str, Any]] = {}
    for p in _products(db, tenant_id):
        comp = competitor_analytics(db, tenant_id, p.id)
        cat = p.categoria_nome or 'Sem categoria'
        row = categories.setdefault(cat, {'category': cat, 'products': 0, 'offers': 0, 'aggressive_sellers': 0, 'avg_volatility': 0.0, 'opportunity_score': 0.0, 'war_room': False})
        row['products'] += 1
        row['offers'] += int(comp.get('count') or 0)
        row['aggressive_sellers'] += 1 if comp.get('aggressive_alert') else 0
        row['avg_volatility'] += _f(comp.get('price_dispersion'))
        latest = _latest_pricing(db, tenant_id, p.id)
        price = _f(latest.preco_sugerido if latest else p.preco_base)
        med = _f(comp.get('median_price'), price)
        if med and price < med * .95:
            row['opportunity_score'] += 18
    radar = []
    for row in categories.values():
        row['avg_volatility'] = round(row['avg_volatility'] / max(row['products'], 1), 2)
        row['opportunity_score'] = round(min(100, row['opportunity_score'] + row['offers'] * 0.6 + row['aggressive_sellers'] * 12), 1)
        row['war_room'] = row['aggressive_sellers'] >= 2 or row['avg_volatility'] > 90
        row['temperature'] = 'hot' if row['war_room'] else 'warm' if row['opportunity_score'] >= 55 else 'stable'
        radar.append(row)
    radar.sort(key=lambda x: (x['temperature'] == 'hot', x['opportunity_score']), reverse=True)
    sellers = db.query(CompetitorOffer.vendedor, CompetitorOffer.vendas).join(CompetitorSearch, CompetitorOffer.search_id == CompetitorSearch.id).filter(CompetitorOffer.cliente_id == tenant_id).limit(200).all()
    sellers_rank: dict[str, int] = {}
    for seller, sales in sellers:
        sellers_rank[seller or 'Seller não identificado'] = sellers_rank.get(seller or 'Seller não identificado', 0) + int(sales or 0)
    aggressive = [{'seller': s, 'sales_signal': v, 'risk': 'high' if v > 600 else 'medium'} for s, v in sorted(sellers_rank.items(), key=lambda x: x[1], reverse=True)[:8]]
    return {'categories': radar, 'aggressive_sellers': aggressive, 'signals': [{'label': 'Guerra de preços', 'value': len([r for r in radar if r['war_room']])}, {'label': 'Categorias aquecendo', 'value': len([r for r in radar if r['temperature'] == 'hot'])}, {'label': 'Sellers agressivos', 'value': len([s for s in aggressive if s['risk'] == 'high'])}]}


def build_ai_copilot(db: Session, tenant_id: str) -> dict[str, Any]:
    score = build_maturity_score(db, tenant_id)
    recommendations = build_recommended_actions(db, tenant_id)
    alerts = build_smart_alerts(db, tenant_id)
    timeline = build_operational_timeline(db, tenant_id)
    radar = build_market_radar(db, tenant_id)
    total_impact = recommendations['estimated_total_impact']
    intro = f"Operational Score {score['score']}/100 ({score['category']}). {alerts['critical']} grupos críticos e potencial estimado de {_money(total_impact)}/mês em ações priorizadas."
    feed = []
    for action in recommendations['items'][:8]:
        feed.append({
            **action,
            'ai_reasoning': f"Prioridade {action['priority']} porque {action['justification']} A recomendação conecta pricing, margem, concorrência e saúde operacional.",
            'confidence': 0.86 if action['priority'] == 'HIGH' else 0.74 if action['priority'] == 'MEDIUM' else 0.62,
        })
    return {'summary': intro, 'mode': 'heuristic_ai_mvp', 'score': score, 'recommendations': feed, 'smart_alerts': alerts, 'timeline': timeline, 'market_radar': radar, 'quick_actions': ['Simular impacto', 'Revisar produtos em risco', 'Reprocessar jobs', 'Abrir radar de mercado']}


def build_executive_mode(db: Session, tenant_id: str) -> dict[str, Any]:
    copilot = build_ai_copilot(db, tenant_id)
    products = _products(db, tenant_id)
    marketplace = db.query(MarketplaceConnection).filter_by(tenant_id=tenant_id, marketplace='mercadolivre').first()
    listings = db.query(MarketplaceListing).filter_by(cliente_id=tenant_id).count()
    return {
        'headline': copilot['summary'],
        'kpis': [
            {'label': 'Operational Maturity', 'value': copilot['score']['score'], 'suffix': '/100'},
            {'label': 'Produtos ativos', 'value': len(products), 'suffix': ''},
            {'label': 'Alertas críticos', 'value': copilot['smart_alerts']['critical'], 'suffix': ''},
            {'label': 'Publicações monitoradas', 'value': listings, 'suffix': ''},
            {'label': 'Marketplace', 'value': 'Conectado' if marketplace and marketplace.is_active else 'Pronto para conectar', 'suffix': ''},
        ],
        'top_opportunities': copilot['recommendations'][:3],
        'top_risks': copilot['smart_alerts']['items'][:3],
        'market_signals': copilot['market_radar']['signals'],
    }


def simulate_advanced_profit(payload: dict[str, Any]) -> dict[str, Any]:
    base = simulate_impact(payload)
    freight = _f(payload.get('freight', payload.get('frete', 0)))
    monthly_units = int(_f(payload.get('monthly_units', 80)))
    price = _f(payload.get('price', payload.get('preco', 189)))
    competitor = _f(payload.get('competitor_price', payload.get('concorrencia', price * .96)))
    result = base['result']
    adjusted_unit_profit = result['unit_profit'] - freight
    monthly = adjusted_unit_profit * monthly_units
    annual = monthly * 12
    risk_points = 0
    risk_points += 35 if adjusted_unit_profit <= 0 else 15 if result['margin_pct'] < 12 else 0
    risk_points += 25 if price > competitor * 1.08 else 10 if price > competitor * 1.03 else 0
    risk_points += 15 if freight > price * .08 else 0
    operational_impact = max(0, min(100, 100 - risk_points))
    base['advanced'] = {'freight_cost': freight, 'adjusted_unit_profit': round(adjusted_unit_profit, 2), 'monthly_impact': round(monthly, 2), 'annual_impact': round(annual, 2), 'operational_impact_score': round(operational_impact, 1), 'risk_points': risk_points, 'executive_recommendation': 'Revisar preço/frete antes de escalar.' if risk_points >= 35 else 'Cenário saudável para teste controlado.'}
    base['series'].append({'label': 'Com frete', 'profit': round(monthly, 2), 'price': round(price, 2)})
    return base


def _category_title(category: str) -> str:
    return {
        'margem_baixa': 'Produtos abaixo da margem mínima',
        'concorrencia_agressiva': 'Concorrência agressiva detectada',
        'sem_monitoramento': 'Produtos sem monitoramento ativo',
        'aumento_preco': 'Oportunidade de aumento de preço',
        'estoque_baixo': 'Risco de estoque baixo',
        'job_falha': 'Falhas operacionais em jobs',
    }.get(category, category.replace('_', ' ').title())


def _category_action(category: str) -> str:
    return {
        'margem_baixa': 'Aplicar cenário margem protegida e simular impacto.',
        'concorrencia_agressiva': 'Comparar mediana, piso de margem e resposta parcial por SKU.',
        'sem_monitoramento': 'Ativar scraping recorrente nos SKUs sem cobertura.',
        'aumento_preco': 'Testar aumento conservador e acompanhar competitividade.',
        'estoque_baixo': 'Repor estoque antes de ampliar vendas.',
        'job_falha': 'Reprocessar jobs e revisar logs recentes.',
    }.get(category, 'Revisar contexto e priorizar ação operacional.')
